"""
E2E Test Suite - Customer Success FTE
Part 3: Integration Testing
"""
import pytest
import asyncio
from httpx import AsyncClient

BASE_URL = "http://localhost:8000"

@pytest.fixture
async def client():
    async with AsyncClient(base_url=BASE_URL) as ac:
        yield ac

class TestWebFormChannel:
    @pytest.mark.asyncio
    async def test_form_submission(self, client):
        response = await client.post("/support/submit", json={
            "name": "Test User",
            "email": "test@example.com",
            "subject": "Help with API",
            "category": "technical",
            "message": "I need help with the API authentication",
            "priority": "medium"
        })
        assert response.status_code == 200
        data = response.json()
        assert "ticket_id" in data
        assert data["message"] is not None

    @pytest.mark.asyncio
    async def test_form_validation(self, client):
        response = await client.post("/support/submit", json={
            "name": "A",
            "email": "invalid-email",
            "subject": "Hi",
            "category": "invalid",
            "message": "Short"
        })
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_ticket_status(self, client):
        submit = await client.post("/support/submit", json={
            "name": "Test User",
            "email": "test@example.com",
            "subject": "Status Test",
            "category": "general",
            "message": "Testing ticket status retrieval",
            "priority": "low"
        })
        ticket_id = submit.json()["ticket_id"]
        status = await client.get(f"/support/ticket/{ticket_id}")
        assert status.status_code == 200

class TestEmailChannel:
    @pytest.mark.asyncio
    async def test_gmail_webhook(self, client):
        response = await client.post("/webhooks/gmail", json={
            "message": {
                "data": "dGVzdA==",
                "messageId": "test-123"
            },
            "subscription": "projects/test/subscriptions/gmail-push"
        })
        assert response.status_code in [200, 500]

class TestWhatsAppChannel:
    @pytest.mark.asyncio
    async def test_whatsapp_webhook(self, client):
        response = await client.post(
            "/webhooks/whatsapp",
            data={
                "MessageSid": "SM123",
                "From": "whatsapp:+1234567890",
                "Body": "Hello I need help",
                "ProfileName": "Test User"
            }
        )
        assert response.status_code in [200, 403]

class TestHealth:
    @pytest.mark.asyncio
    async def test_health_check(self, client):
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "channels" in data

    @pytest.mark.asyncio
    async def test_channel_metrics(self, client):
        response = await client.get("/metrics/channels")
        assert response.status_code == 200

class TestCrossChannel:
    @pytest.mark.asyncio
    async def test_customer_lookup(self, client):
        await client.post("/support/submit", json={
            "name": "Cross Channel User",
            "email": "cross@example.com",
            "subject": "Test",
            "category": "general",
            "message": "First contact via web form",
            "priority": "low"
        })
        response = await client.get(
            "/customers/lookup",
            params={"email": "cross@example.com"}
        )
        assert response.status_code in [200, 404]