
import os
import json
import asyncio
import logging
from dotenv import load_dotenv
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
from aiokafka.errors import KafkaConnectionError

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")

class FTEKafkaProducer:
    def __init__(self, bootstrap_servers=None):
        if bootstrap_servers:
            self.bootstrap_servers = bootstrap_servers
        else:
            self.bootstrap_servers = KAFKA_BOOTSTRAP_SERVERS
        self.producer = None
    async def start(self):
        while True:
            try:
                self.producer = AIOKafkaProducer(bootstrap_servers=self.bootstrap_servers)
                await self.producer.start()
                logger.info("Kafka Producer started successfully.")
                break
            except KafkaConnectionError as e:
                logger.error(f"Kafka Producer connection failed: {e}. Retrying in 5 seconds...")
                await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"An unexpected error occurred while starting Kafka Producer: {e}")
                await asyncio.sleep(5)

    async def stop(self):
        if self.producer:
            await self.producer.stop()
            logger.info("Kafka Producer stopped.")

    async def publish(self, topic: str, message: dict):
        try:
            await self.producer.send_and_wait(topic, json.dumps(message).encode("utf-8"))
            logger.info(f"Published message to topic {topic}: {message}")
        except Exception as e:
            logger.error(f"Failed to publish message to topic {topic}: {e}")

class FTEKafkaConsumer:
    def __init__(self, topic=None, topics=None, group_id=None, bootstrap_servers=None):
        self.topic = topic or (topics[0] if topics else "fte.tickets.incoming")
        self.topics = topics or ([topic] if topic else ["fte.tickets.incoming"])
        self.group_id = group_id or "fte-consumer-group"
        self.bootstrap_servers = bootstrap_servers or KAFKA_BOOTSTRAP_SERVERS
        self.consumer = None

    async def start(self):
        while True:
            try:
                self.consumer = AIOKafkaConsumer(
                    *self.topics,
                    bootstrap_servers=self.bootstrap_servers,
                    group_id="fte_group"
                )
                await self.consumer.start()
                logger.info(f"Kafka Consumer for topics {self.topics} started successfully.")
                break
            except KafkaConnectionError as e:
                logger.error(f"Kafka Consumer connection failed: {e}. Retrying in 5 seconds...")
                await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"An unexpected error occurred while starting Kafka Consumer: {e}")
                await asyncio.sleep(5)

    async def stop(self):
        if self.consumer:
            await self.consumer.stop()
            logger.info(f"Kafka Consumer for topics {self.topics} stopped.")

    async def consume(self):
        if not self.consumer:
            logger.warning("Consumer not started. Call start() first.")
            return
        try:
            async for msg in self.consumer:
                yield json.loads(msg.value.decode("utf-8"))
        except Exception as e:
            logger.error(f"Error during Kafka consumption: {e}")


if __name__ == "__main__":
    async def test_kafka_client():
        producer = FTEKafkaProducer()
        await producer.start()

        consumer_topics = [
            "fte.tickets.incoming",
            "fte.channels.email.inbound",
            "fte.channels.whatsapp.inbound",
            "fte.channels.webform.inbound",
            "fte.escalations",
            "fte.metrics",
            "fte.dlq"
        ]
        consumer = FTEKafkaConsumer(*consumer_topics)
        await consumer.start()

        test_message = {"test": "hello", "from": "producer"}
        await producer.publish("fte.tickets.incoming", test_message)

        print("\n--- Consuming messages (will stop after a few seconds or a message is received) ---")
        try:
            async for msg in consumer.consume():
                print(f"Received message: {msg}")
                break # For testing, stop after one message
        except asyncio.CancelledError:
            pass
        finally:
            await producer.stop()
            await consumer.stop()

    asyncio.run(test_kafka_client())
