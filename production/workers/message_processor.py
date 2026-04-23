
import asyncio
import json
import os
import uuid
from datetime import datetime, timedelta

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
                """
                SELECT c.id FROM customers c
                JOIN customer_identifiers ci ON c.id = ci.customer_id
                WHERE ci.identifier_type = 'email' AND ci.identifier_value = $1
                """,
                email
            )
        if not customer_id and phone:
            customer_id = await conn.fetchval(
                """
                SELECT c.id FROM customers c
                JOIN customer_identifiers ci ON c.id = ci.customer_id
                WHERE ci.identifier_type = 'phone' AND ci.identifier_value = $1
                """,
                phone
            )

        if customer_id:
            return customer_id
        else:
            customer_id = uuid.uuid4()
            await conn.execute(
                """
                INSERT INTO customers (id, email, phone, created_at, metadata)
                VALUES ($1, $2, $3, NOW(), '{}'::jsonb)
                """,
                customer_id, email, phone
            )
            if email:
                await conn.execute(
                    """
                    INSERT INTO customer_identifiers (id, customer_id, identifier_type, identifier_value, verified)
                    VALUES ($1, $2, $3, $4, TRUE)
                    """,
                    uuid.uuid4(), customer_id, 'email', email
                )
            if phone:
                await conn.execute(
                    """
                    INSERT INTO customer_identifiers (id, customer_id, identifier_type, identifier_value, verified)
                    VALUES ($1, $2, $3, $4, TRUE)
                    """,
                    uuid.uuid4(), customer_id, 'phone', phone
                )
            return customer_id

    async def get_or_create_conversation(self, conn, customer_id: uuid.UUID, channel: str):
        conversation_id = await conn.fetchval(
            """
            SELECT id FROM conversations
            WHERE customer_id = $1 AND status = 'active' AND initial_channel = $2
            AND started_at > NOW() - INTERVAL '24 hours'
            ORDER BY started_at DESC
            LIMIT 1
            """,
            customer_id, channel
        )

        if conversation_id:
            return conversation_id
        else:
            conversation_id = uuid.uuid4()
            await conn.execute(
                """
                INSERT INTO conversations (id, customer_id, initial_channel, started_at, status, metadata)
                VALUES ($1, $2, $3, NOW(), 'active', '{}'::jsonb)
                """,
                conversation_id, customer_id, channel
            )
            return conversation_id

    async def store_message(self, conn, conversation_id: uuid.UUID, channel: str, direction: str, role: str, content: str, channel_message_id: str = None, delivery_status: str = 'sent'):
        message_id = uuid.uuid4()
        await conn.execute(
            """
            INSERT INTO messages (id, conversation_id, channel, direction, role, content, created_at, delivery_status, channel_message_id)
            VALUES ($1, $2, $3, $4, $5, $6, NOW(), $7, $8)
            """,
            message_id, conversation_id, channel, direction, role, content, delivery_status, channel_message_id
        )
        return message_id

    async def load_conversation_history(self, conn, conversation_id: uuid.UUID, limit: int = 10):
        records = await conn.fetch(
            """
            SELECT role, content FROM messages
            WHERE conversation_id = $1
            ORDER BY created_at DESC
            LIMIT $2
            """,
            conversation_id, limit
        )
        return [{"role": r["role"], "content": r["content"]} for r in records[::-1]] # Reverse to get chronological order

    async def process_message(self, kafka_message):
        start_time: datetime = datetime.now()
        message_data = json.loads(kafka_message.value.decode('utf-8'))

        email = message_data.get("email")
        phone = message_data.get("phone")
        content = message_data.get("content")
        channel = message_data.get("channel")
        channel_message_id = message_data.get("channel_message_id")

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

                agent_response_data = await self.agent.run(content, conversation_history)

                agent_response_content = agent_response_data.get("response")
                tool_calls = agent_response_data.get("tool_calls")
                escalated_to_human = agent_response_data.get("escalated_to_human", False)

                if agent_response_content:
                    await self.store_message(
                        conn, conversation_id, channel, 'outbound', 'agent', agent_response_content,
                        tool_calls=json.dumps(tool_calls) if tool_calls else None
                    )
                    # For now, we'll assume send_response will be handled by the API gateway or channel handlers
                    # after the message is stored. For direct replies, this logic would need to be here.
                    # Example: await self.kafka_producer.publish("fte.channels.response", {"conversation_id": str(conversation_id), "message": agent_response_content, "channel": channel})

                if escalated_to_human:
                    await conn.execute(
                        "UPDATE conversations SET status = 'escalated' WHERE id = $1",
                        conversation_id
                    )
                    await self.kafka_producer.publish("fte.escalations", {
                        "conversation_id": str(conversation_id),
                        "reason": "Agent escalated",
                        "timestamp": datetime.now().isoformat()
                    })

                end_time = datetime.now()
                latency_ms = (end_time - start_time).total_seconds() * 1000
                await self.publish_latency_metrics(conn, channel, latency_ms)

            except Exception as e:
                print(f"Error processing message: {e}")
                await self.handle_error(message_data, str(e))

    async def handle_error(self, original_message_data: dict, error_message: str):
        # Publish to DLQ
        await self.kafka_producer.publish("fte.dlq", {
            "original_message": original_message_data,
            "error": error_message,
            "timestamp": datetime.now().isoformat()
        })
        # Optionally send an apology message to the customer if possible (e.g., via a generic channel)
        print(f"Message sent to DLQ: {original_message_data} with error: {error_message}")

    async def publish_latency_metrics(self, conn, channel: str, latency_ms: float):
        await conn.execute(
            """
            INSERT INTO agent_metrics (id, metric_name, metric_value, channel, dimensions, recorded_at)
            VALUES ($1, $2, $3, $4, $5, NOW())
            """,
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
    # 1. Processor object ko yahan create karein taake ye 'finally' block ko mil sakay
    worker_processor = UnifiedMessageProcessor()

    async def main():
        try:
            await worker_processor.start()
            # Worker ko running state mein rakhne ke liye
            while True:
                await asyncio.sleep(1)
        except Exception as e:
            print(f"Error in main loop: {e}")
            raise e

    try:
        # 2. Main function ko run karein
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopping worker due to KeyboardInterrupt...")
    except Exception as e:
        print(f"Worker crashed: {e}")
    finally:
        # 3. Cleanup: 'worker_processor' yahan accessible hai
        print("Executing cleanup...")
        try:
            # Agar asyncio loop pehle hi band ho chuka ho toh naya loop chalayen cleanup ke liye
            asyncio.run(worker_processor.stop())
        except Exception as stop_error:
            print(f"Error during shutdown: {stop_error}")