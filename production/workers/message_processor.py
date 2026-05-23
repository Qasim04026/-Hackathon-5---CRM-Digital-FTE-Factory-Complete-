import asyncio
import json
import os
import uuid
from datetime import datetime

import asyncpg
from dotenv import load_dotenv

from production.agent.customer_success_agent import CustomerSuccessAgent
from production.kafka_client import FTEKafkaConsumer, FTEKafkaProducer

load_dotenv()


class UnifiedMessageProcessor:
    def __init__(self):
        self.db_url = os.getenv("DATABASE_URL")
        self.kafka_consumer = FTEKafkaConsumer(
            topic="fte.tickets.incoming",
            bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS")
        )
        self.kafka_producer = FTEKafkaProducer(
            bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS")
        )
        self.agent = CustomerSuccessAgent()
        self.pool = None

    async def start(self):
        try:
            self.pool = await asyncpg.create_pool(self.db_url)
            await self.kafka_producer.start()
            await self.kafka_consumer.start()
            asyncio.create_task(self._consume_messages())
            print("UnifiedMessageProcessor started successfully.")
        except Exception as e:
            print(f"Error starting UnifiedMessageProcessor: {e}")
            await self.stop()

    async def stop(self):
        if self.kafka_producer:
            await self.kafka_producer.stop()
        if self.kafka_consumer:
            await self.kafka_consumer.stop()
        if self.pool:
            await self.pool.close()
        print("UnifiedMessageProcessor stopped.")

    async def _consume_messages(self):
        print("Starting message consumption loop...")
        try:
            async for message in self.kafka_consumer.consume():
                if message:
                    try:
                        await self.process_message(message)
                    except Exception as e:
                        print(f"Error processing individual message: {e}")
        except asyncio.CancelledError:
            print("Message consumption cancelled.")
        except Exception as e:
            print(f"Critical error in consumption loop: {e}")
            await asyncio.sleep(5)

    async def resolve_customer(self, conn, email: str = None, phone: str = None):
        customer_id = None
        if email:
            customer_id = await conn.fetchval(
                """SELECT c.id FROM customers c
                   JOIN customer_identifiers ci ON c.id = ci.customer_id
                   WHERE ci.identifier_type = 'email' AND ci.identifier_value = $1""",
                email
            )
        if not customer_id and phone:
            customer_id = await conn.fetchval(
                """SELECT c.id FROM customers c
                   JOIN customer_identifiers ci ON c.id = ci.customer_id
                   WHERE ci.identifier_type = 'phone' AND ci.identifier_value = $1""",
                phone
            )
        if customer_id:
            return customer_id

        customer_id = uuid.uuid4()
        await conn.execute(
            """INSERT INTO customers (id, email, phone, created_at, metadata)
               VALUES ($1, $2, $3, NOW(), '{}'::jsonb)""",
            customer_id, email, phone
        )
        if email:
            await conn.execute(
                """INSERT INTO customer_identifiers (id, customer_id, identifier_type, identifier_value, verified)
                   VALUES ($1, $2, $3, $4, TRUE)""",
                uuid.uuid4(), customer_id, 'email', email
            )
        if phone:
            await conn.execute(
                """INSERT INTO customer_identifiers (id, customer_id, identifier_type, identifier_value, verified)
                   VALUES ($1, $2, $3, $4, TRUE)""",
                uuid.uuid4(), customer_id, 'phone', phone
            )
        return customer_id

    async def get_or_create_conversation(self, conn, customer_id: uuid.UUID, channel: str):
        conversation_id = await conn.fetchval(
            """SELECT id FROM conversations
               WHERE customer_id = $1 AND status = 'active' AND initial_channel = $2
               AND started_at > NOW() - INTERVAL '24 hours'
               ORDER BY started_at DESC LIMIT 1""",
            customer_id, channel
        )
        if conversation_id:
            return conversation_id

        conversation_id = uuid.uuid4()
        await conn.execute(
            """INSERT INTO conversations (id, customer_id, initial_channel, started_at, status, metadata)
               VALUES ($1, $2, $3, NOW(), 'active', '{}'::jsonb)""",
            conversation_id, customer_id, channel
        )
        return conversation_id

    async def store_message(self, conn, conversation_id: uuid.UUID, channel: str,
                            direction: str, role: str, content: str,
                            channel_message_id: str = None, delivery_status: str = 'sent',
                            tool_calls: str = None):
        message_id = uuid.uuid4()
        await conn.execute(
            """INSERT INTO messages (id, conversation_id, channel, direction, role, content,
               created_at, delivery_status, channel_message_id, tool_calls)
               VALUES ($1, $2, $3, $4, $5, $6, NOW(), $7, $8, $9)""",
            message_id, conversation_id, channel, direction, role, content,
            delivery_status, channel_message_id,
            json.dumps(json.loads(tool_calls)) if tool_calls else '[]'
        )
        return message_id

    async def load_conversation_history(self, conn, conversation_id: uuid.UUID, limit: int = 10):
        records = await conn.fetch(
            """SELECT role, content FROM messages
               WHERE conversation_id = $1
               ORDER BY created_at DESC LIMIT $2""",
            conversation_id, limit
        )
        role_map = {"agent": "model", "user": "user", "system": "user"}
        return [{"role": role_map.get(r["role"], "user"), "content": r["content"]} for r in records[::-1]]

    async def process_message(self, kafka_message):
        start_time = datetime.now()

        if isinstance(kafka_message, dict):
            message_data = kafka_message
        elif hasattr(kafka_message, 'value'):
            raw = kafka_message.value
            if isinstance(raw, bytes):
                message_data = json.loads(raw.decode('utf-8'))
            elif isinstance(raw, str):
                message_data = json.loads(raw)
            elif isinstance(raw, dict):
                message_data = raw
            else:
                message_data = raw
        else:
            print(f"Unknown message format: {type(kafka_message)}")
            return

        email = message_data.get("customer_email") or message_data.get("email")
        phone = message_data.get("customer_phone") or message_data.get("phone")
        content = message_data.get("content") or message_data.get("message")
        channel = message_data.get("channel", "web_form")
        channel_message_id = message_data.get("channel_message_id") or str(message_data.get("ticket_id", ""))

        if not content or not channel or (not email and not phone):
            print(f"Invalid message data received: {message_data}")
            await self.handle_error(message_data, "Invalid message data")
            return

        async with self.pool.acquire() as conn:
            try:
                customer_id = await self.resolve_customer(conn, email=email, phone=phone)
                conversation_id = await self.get_or_create_conversation(conn, customer_id, channel)

                await self.store_message(
                    conn, conversation_id, channel, 'inbound', 'user', content, channel_message_id
                )

                conversation_history = await self.load_conversation_history(conn, conversation_id)

                agent_response_data = await self.agent.run(
                    content,
                    conversation_history,
                    customer_id=str(customer_id),
                    conversation_id=str(conversation_id),
                    current_channel=channel
                )

                if isinstance(agent_response_data, tuple):
                    agent_response_content, tool_calls = agent_response_data
                    if isinstance(agent_response_content, str):
                        try:
                            parsed = json.loads(agent_response_content)
                            agent_response_content = parsed.get("response", agent_response_content)
                        except:
                            pass
                elif isinstance(agent_response_data, dict):
                    agent_response_content = agent_response_data.get("response", "")
                    tool_calls = agent_response_data.get("tool_calls", [])
                else:
                    agent_response_content = str(agent_response_data)
                    tool_calls = []

                if agent_response_content:
                    await self.store_message(
                        conn, conversation_id, channel, 'outbound', 'agent',
                        agent_response_content,
                        tool_calls=json.dumps(tool_calls) if tool_calls else None
                    )
                    print(f"Agent response stored: {agent_response_content[:100]}")

                end_time = datetime.now()
                latency_ms = (end_time - start_time).total_seconds() * 1000
                await self.publish_latency_metrics(conn, channel, latency_ms)
                print(f"Message processed in {latency_ms:.0f}ms")

            except Exception as e:
                print(f"Error processing message: {e}")
                import traceback
                traceback.print_exc()
                await self.handle_error(message_data, str(e))

    async def handle_error(self, original_message_data: dict, error_message: str):
        await self.kafka_producer.publish("fte.dlq", {
            "original_message": original_message_data,
            "error": error_message,
            "timestamp": datetime.now().isoformat()
        })
        print(f"Message sent to DLQ: {error_message}")

    async def publish_latency_metrics(self, conn, channel: str, latency_ms: float):
        await conn.execute(
            """INSERT INTO agent_metrics (id, metric_name, metric_value, channel, dimensions, recorded_at)
               VALUES ($1, $2, $3, $4, $5, NOW())""",
            uuid.uuid4(), "agent_response_latency", latency_ms, channel, json.dumps({})
        )
        await self.kafka_producer.publish("fte.metrics", {
            "metric_name": "agent_response_latency",
            "metric_value": latency_ms,
            "channel": channel,
            "dimensions": {},
            "recorded_at": datetime.now().isoformat()
        })


if __name__ == "__main__":
    worker_processor = UnifiedMessageProcessor()

    async def main():
        try:
            await worker_processor.start()
            while True:
                await asyncio.sleep(1)
        except Exception as e:
            print(f"Error in main loop: {e}")
            raise e

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopping worker...")
    except Exception as e:
        print(f"Worker crashed: {e}")
    finally:
        print("Executing cleanup...")
        try:
            asyncio.run(worker_processor.stop())
        except Exception as stop_error:
            print(f"Error during shutdown: {stop_error}")