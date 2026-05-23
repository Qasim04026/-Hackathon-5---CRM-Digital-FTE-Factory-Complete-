import asyncio
import os
import json
import hmac
import hashlib
from datetime import datetime, timedelta
import uuid

import asyncpg
from fastapi import FastAPI, Request, Response, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from twilio.request_validator import RequestValidator

from production.kafka_client import FTEKafkaProducer
from production.channels.web_form_handler import router as web_form_router, SupportFormSubmission, SupportFormResponse

load_dotenv()

app = FastAPI(
    title="Customer Success FTE API",
    description="API for managing customer interactions and agent services",
    version="1.0.0",
)

app.include_router(web_form_router)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Environment variables
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://fte_user:fte_password_local@postgres:5432/fte_db"
)
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")

# Kafka Producer
kafka_producer = None

@app.on_event("startup")
async def startup_event():
    global kafka_producer
    print("Starting up FastAPI application...")
    kafka_producer = FTEKafkaProducer(bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS)
    await kafka_producer.start()
    app.state.db_pool = await asyncpg.create_pool(DATABASE_URL)
    print("FastAPI startup complete.")

@app.on_event("shutdown")
async def shutdown_event():
    print("Shutting down FastAPI application...")
    if kafka_producer:
        await kafka_producer.stop()
    if app.state.db_pool:
        await app.state.db_pool.close()
    print("FastAPI shutdown complete.")

# Include routers
app.include_router(web_form_router, prefix="/api")

# Helper to get DB connection
async def get_db_connection():
    async with app.state.db_pool.acquire() as conn:
        yield conn

# Endpoints
@app.get("/health", summary="Health Check", response_model=dict)
async def health_check(conn: asyncpg.Connection = Depends(get_db_connection)):
    try:
        # Check DB connection
        await conn.fetchval("SELECT 1")
        db_status = "ok"
    except Exception as e:
        db_status = f"error: {e}"

    # In a real scenario, you'd also check Kafka, Gemini API, etc.
    # For simplicity, we just check DB and return placeholder channel info.
    channel_info = {
        "email": {"enabled": True, "status": "active"},
        "whatsapp": {"enabled": True, "status": "active"},
        "web_form": {"enabled": True, "status": "active"},
    }
    return {"status": "healthy", "database": db_status, "channels": channel_info}

@app.post("/webhooks/gmail", summary="Handle Gmail Pub/Sub notifications")
async def handle_gmail_webhook(request: Request):
    try:
        notification_data = await request.json()
        print(f"Received Gmail notification: {notification_data}")
        return {"status": "success", "message": "Gmail notification received"}
    except Exception as e:
        print(f"Error processing Gmail webhook: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def validate_twilio_request(request: Request, body: bytes = b''):
    if not TWILIO_AUTH_TOKEN:
        raise HTTPException(status_code=500, detail="Twilio Auth Token not configured.")

    validator = RequestValidator(TWILIO_AUTH_TOKEN)
    url = str(request.url)
    form_params = await request.form()
    params = {k: v for k, v in form_params.items()}
    twilio_signature = request.headers.get("X-Twilio-Signature", '')

    if not validator.validate(url, params, twilio_signature):
        raise HTTPException(status_code=403, detail="Invalid Twilio signature.")
    return params

@app.post("/webhooks/whatsapp", summary="Handle Twilio WhatsApp webhook")
async def handle_whatsapp_webhook(form_params: dict = Depends(validate_twilio_request),
                                  conn: asyncpg.Connection = Depends(get_db_connection),
                                  background_tasks: BackgroundTasks = None):
    try:
        from_number = form_params.get("From")
        message_body = form_params.get("Body")
        message_sid = form_params.get("SmsMessageSid")

        if not from_number or not message_body:
            raise HTTPException(status_code=400, detail="Missing 'From' or 'Body' in Twilio webhook.")

        customer_phone = from_number.replace("whatsapp:", "")
        message_data = {
            "email": None,
            "phone": customer_phone,
            "content": message_body,
            "channel": "whatsapp",
            "channel_message_id": message_sid,
            "original_message": form_params
        }

        # Publish to Kafka for async processing by UnifiedMessageProcessor
        await kafka_producer.publish("fte.tickets.incoming", message_data)

        # Return TwiML response immediately to Twilio (empty <Response/>)
        return Response(content="<Response/>", media_type="application/xml")

    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"Error processing WhatsApp webhook: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")

@app.post("/webhooks/whatsapp/status", summary="Handle Twilio WhatsApp delivery status updates")
async def handle_whatsapp_status_webhook(request: Request):
    try:
        status_data = await request.form()
        print(f"Received WhatsApp status update: {status_data}")
        return {"status": "success", "message": "WhatsApp status update received"}
    except Exception as e:
        print(f"Error processing WhatsApp status webhook: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/conversations/{conversation_id}", summary="Get full conversation history", response_model=dict)
async def get_conversation_history(conversation_id: uuid.UUID, conn: asyncpg.Connection = Depends(get_db_connection)):
    conversation = await conn.fetchrow(
        "SELECT * FROM conversations WHERE id = $1", conversation_id
    )
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    messages = await conn.fetch(
        "SELECT * FROM messages WHERE conversation_id = $1 ORDER BY created_at ASC", conversation_id
    )
    return {"conversation": dict(conversation), "messages": [dict(msg) for msg in messages]}

@app.get("/customers/lookup", summary="Find customer by email or phone", response_model=dict)
async def lookup_customer(email: str = None, phone: str = None, conn: asyncpg.Connection = Depends(get_db_connection)):
    if not email and not phone:
        raise HTTPException(status_code=400, detail="Either email or phone must be provided.")

    customer_id = None
    if email:
        customer_id = await conn.fetchval(
            "SELECT customer_id FROM customer_identifiers WHERE identifier_type = 'email' AND identifier_value = $1",
            email
        )
    if not customer_id and phone:
        customer_id = await conn.fetchval(
            "SELECT customer_id FROM customer_identifiers WHERE identifier_type = 'phone' AND identifier_value = $1",
            phone
        )

    if not customer_id:
        raise HTTPException(status_code=404, detail="Customer not found.")

    customer = await conn.fetchrow(
        "SELECT * FROM customers WHERE id = $1", customer_id
    )
    identifiers = await conn.fetch(
        "SELECT identifier_type, identifier_value FROM customer_identifiers WHERE customer_id = $1", customer_id
    )

    return {"customer": dict(customer), "identifiers": [dict(id) for id in identifiers]}

@app.get("/metrics/channels", summary="Get 24hr metrics by channel", response_model=dict)
async def get_channel_metrics(conn: asyncpg.Connection = Depends(get_db_connection)):
    twenty_four_hours_ago = datetime.now() - timedelta(hours=24)

    metrics = await conn.fetch(
        """
        SELECT
            channel,
            COUNT(CASE WHEN direction = 'inbound' THEN 1 END) AS inbound_messages,
            COUNT(CASE WHEN direction = 'outbound' THEN 1 END) AS outbound_messages,
            AVG(latency_ms) AS avg_latency_ms
        FROM messages
        WHERE created_at >= $1
        GROUP BY channel
        """,
        twenty_four_hours_ago
    )

    agent_metrics = await conn.fetch(
        """
        SELECT
            channel,
            metric_name,
            AVG(metric_value) AS average_value,
            COUNT(id) AS count
        FROM agent_metrics
        WHERE recorded_at >= $1
        GROUP BY channel, metric_name
        """,
        twenty_four_hours_ago
    )

    formatted_metrics = {"channels": {}}
    for row in metrics:
        channel = row["channel"]
        formatted_metrics["channels"].setdefault(channel, {})
        formatted_metrics["channels"][channel]["inbound_messages_24hr"] = row["inbound_messages"]
        formatted_metrics["channels"][channel]["outbound_messages_24hr"] = row["outbound_messages"]
        formatted_metrics["channels"][channel]["avg_message_latency_24hr"] = row["avg_latency_ms"]

    for row in agent_metrics:
        channel = row["channel"]
        metric_name = row["metric_name"]
        formatted_metrics["channels"].setdefault(channel, {})
        formatted_metrics["channels"][channel][f"avg_{metric_name}_24hr"] = row["average_value"]
        formatted_metrics["channels"][channel][f"count_{metric_name}_24hr"] = row["count"]

    return formatted_metrics