from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel, Field, EmailStr
from typing import Optional
from uuid import UUID
from datetime import datetime
import asyncpg
import os
from dotenv import load_dotenv
import logging

# Kafka client imports as requested
from production.kafka_client import FTEKafkaProducer, TOPICS

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/support", tags=["support"])

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL not found in .env file")

async def get_db_connection():
    conn = None
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        yield conn
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        raise HTTPException(status_code=500, detail="Database connection failed")
    finally:
        if conn:
            await conn.close()

class SupportFormSubmission(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    email: EmailStr
    subject: str = Field(min_length=5, max_length=500)
    category: str = Field(default="general", description="Category of the support request",
                          pattern="^(general|technical|billing|bug_report|feedback)$")
    priority: str = Field(default="medium", description="Priority of the support request",
                           pattern="^(low|medium|high|urgent)$")
    message: str = Field(min_length=10)

class SupportFormResponse(BaseModel):
    ticket_id: UUID
    message: str
    estimated_response_time: str = "24-48 hours"

@router.post("/submit", response_model=SupportFormResponse)
async def submit_support_form(
    submission: SupportFormSubmission,
    db_conn: asyncpg.Connection = Depends(get_db_connection)
):
    logger.info(f"Received support form submission from {submission.email}")
    try:
        # Find or create customer
        customer_id = await db_conn.fetchval(
            "SELECT id FROM customers WHERE email = $1", submission.email
        )
        if not customer_id:
            customer_id = await db_conn.fetchval(
                "INSERT INTO customers (email, name) VALUES ($1, $2) RETURNING id",
                submission.email, submission.name
            )
            await db_conn.execute(
                "INSERT INTO customer_identifiers (customer_id, identifier_type, identifier_value, verified) VALUES ($1, $2, $3, TRUE)",
                customer_id, "email", submission.email
            )

        # Create a new conversation
        conversation_id = await db_conn.fetchval(
            "INSERT INTO conversations (customer_id, initial_channel, status) VALUES ($1, $2, $3) RETURNING id",
            customer_id, "webform", "open"
        )

        # Create a ticket
        ticket_id = await db_conn.fetchval(
            """INSERT INTO tickets (conversation_id, customer_id, source_channel, category, priority, status, created_at)
               VALUES ($1, $2, $3, $4, $5, $6, $7) RETURNING id""",
            conversation_id, customer_id, "webform", submission.category, submission.priority, "open", datetime.now()
        )

        # Store the initial message
        await db_conn.execute(
            """INSERT INTO messages (conversation_id, channel, direction, role, content, created_at)
               VALUES ($1, $2, $3, $4, $5, $6)""",
            conversation_id, "webform", "inbound", "user", f"Subject: {submission.subject}\n\n{submission.message}", datetime.now()
        )

        # Publish to Kafka for agent processing
        try:
            from production.kafka_client import FTEKafkaProducer, TOPICS
            import os
            producer = FTEKafkaProducer(
                bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
            )
            await producer.start()
            await producer.publish(TOPICS['tickets_incoming'], {
                "ticket_id": str(ticket_id),
                "conversation_id": str(conversation_id),
                "customer_id": str(customer_id),
                "channel": "web_form",
                "customer_email": submission.email,
                "customer_name": submission.name,
                "subject": submission.subject,
                "content": submission.message,
                "category": submission.category,
                "priority": submission.priority
            })
            await producer.stop()
            logger.info(f"Published ticket {ticket_id} to Kafka")
        except Exception as kafka_error:
            logger.error(f"Kafka publish failed: {kafka_error}")

        return SupportFormResponse(
            ticket_id=ticket_id,
            message="Your support request has been received. We will get back to you shortly."
        )
    except asyncpg.exceptions.UniqueViolationError as e:
        logger.error(f"Unique constraint violation: {e}")
        raise HTTPException(status_code=409, detail="A customer with this email already exists.")
    except Exception as e:
        logger.error(f"Error submitting support form: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to submit support request: {e}")

@router.get("/ticket/{ticket_id}")
async def get_ticket_status(
    ticket_id: UUID,
    db_conn: asyncpg.Connection = Depends(get_db_connection)
):
    logger.info(f"Fetching status for ticket ID: {ticket_id}")
    try:
        ticket = await db_conn.fetchrow(
            "SELECT id, status, resolution_notes, created_at, resolved_at FROM tickets WHERE id = $1",
            ticket_id
        )
        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket not found")
        return dict(ticket)
    except Exception as e:
        logger.error(f"Error fetching ticket status: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch ticket status")