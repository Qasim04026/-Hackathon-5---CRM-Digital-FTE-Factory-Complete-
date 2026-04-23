"""
Customer Success FTE - Prototype Agent
Hackathon 5 - Part 1: Incubation Phase
"""
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import anthropic

@dataclass
class CustomerMessage:
    content: str
    channel: str
    customer_id: str
    customer_email: Optional[str]
    customer_phone: Optional[str]
    subject: Optional[str] = None

@dataclass
class AgentResponse:
    message: str
    channel: str
    escalated: bool
    escalation_reason: str
    ticket_id: str
    sentiment_score: float
    customer_id: str

_ticket_counter = 0
_tickets = {}
_customer_state = {}

def make_ticket_id() -> str:
    global _ticket_counter
    _ticket_counter += 1
    return f"TKT-{_ticket_counter:04d}"

def normalize_customer_id(email: str = None, phone: str = None) -> str:
    if email:
        return email.strip().lower()
    if phone:
        return phone.strip().replace(" ", "").replace("-", "")
    return f"unknown-{datetime.utcnow().timestamp()}"

KNOWLEDGE_BASE = """
## Password Reset
- Go to techflow.io/login → Click "Forgot Password" → Enter registered email
- Reset link valid for 2 hours. If no email: check spam folder
- Add noreply@techflow.io to contacts

## Two-Factor Authentication (2FA)
- Enable: Settings → Security → Enable 2FA
- Supports Google Authenticator, Authy, SMS
- LOST DEVICE: Requires identity verification → escalate to human support

## Invite Team Members
- Settings → Members → Invite by email
- Select role for new member

## Automation Rules
- Available on Pro and above plans only
- Create: Board Settings → Automation → New Rule
- Limits: 50 rules (Pro), unlimited (Business+)
- If not triggering: verify email notifications are enabled in Settings

## Storage Limits
- Starter: 5GB | Pro: 50GB | Business: 500GB
- Max file size: 2GB per file

## Slack Integration
- Connect: Settings → Integrations → Slack → Authorize
- Stopped working: Re-authorize the integration

## GitHub Integration
- Connect: Settings → Integrations → GitHub → Connect repo
- Choose specific repos, can auto-create tasks from issues

## Login Issues
- Clear browser cache and cookies
- Try incognito/private mode
- Disable browser extensions
- Chrome recommended
- Check status.techflow.io for outages

## Mobile App Issues
- Minimum: iOS 14+ or Android 10+
- Fix crashes: force close, update app, reinstall

## Data Export
- Settings → Data → Export (CSV + JSON)
- Up to 24 hours for large workspaces

## API Access
- Generate key: Settings → Developer → API Keys → Generate
- Rate limits: 1,000 req/hr (Pro), 10,000 req/hr (Business+)
- 401 Unauthorized: verify key copied correctly

## SSO Configuration
- Available on Business and Enterprise plans
- Supports SAML 2.0, Google Workspace, Azure AD
- Setup: Settings → Security → SSO Configuration

## Subtasks
- Open task → Add Subtask button → Enter name

## Email Notifications Not Working
- Check spam/junk folder
- Add noreply@techflow.io to contacts
- Settings → Notifications → verify preferences

## GDPR / Data Privacy
- GDPR compliant, SOC 2 Type II certified
- Deletion requests: privacy@techflow.io
- DPA available on request
"""

ESCALATION_RULES = {
    "legal_threat": ["lawyer", "attorney", "legal action", "sue ", "lawsuit", "court"],
    "refund_request": ["refund", "money back", "charge back", "chargeback"],
    "billing_inquiry": ["enterprise price", "how much does", "pricing", "cost per", "discount", "non-profit"],
    "human_requested": ["human", "agent", "representative", "real person", "live support"],
    "gdpr_compliance": ["gdpr", "data deletion", "data protection", "dpa", "data processing agreement"],
}

def detect_escalation(message: str) -> tuple:
    msg_lower = message.lower()
    for reason, keywords in ESCALATION_RULES.items():
        if any(kw in msg_lower for kw in keywords):
            return True, reason
    return False, ""

def estimate_sentiment(message: str) -> float:
    msg_lower = message.lower()
    negative = ["angry", "frustrated", "ridiculous", "broken", "terrible",
                "unacceptable", "worst", "useless", "hate", "awful", "horrible"]
    positive = ["thank", "great", "amazing", "helpful", "love", "excellent", "perfect"]
    neg = sum(1 for w in negative if w in msg_lower)
    pos = sum(1 for w in positive if w in msg_lower)
    caps_ratio = sum(1 for c in message if c.isupper()) / max(len(message), 1)
    if caps_ratio > 0.3:
        neg += 2
    score = 0.5 + (pos * 0.1) - (neg * 0.1)
    return max(0.05, min(0.95, score))

def format_for_channel(response: str, channel: str, ticket_id: str) -> str:
    if channel == "email":
        return (
            f"Hi,\n\n{response}\n\n"
            f"If you have any further questions, please reply to this email.\n\n"
            f"Best regards,\nTechFlow Support Team\nReference: {ticket_id}"
        )
    elif channel == "whatsapp":
        short = response[:280] if len(response) > 280 else response
        return f"{short}\n\nReply for more help 👋"
    else:
        return (
            f"Thanks for reaching out!\n\n{response}\n\n"
            f"Need more help? Reply to this message.\nYour ticket ID: {ticket_id}"
        )

def get_or_create_customer_state(customer_id: str) -> dict:
    if customer_id not in _customer_state:
        _customer_state[customer_id] = {
            "contact_count": 0,
            "conversation_history": [],
            "sentiment_trend": [],
            "topics_discussed": [],
            "original_channel": None,
            "channels_used": set(),
            "resolution_status": "open",
        }
    state = _customer_state[customer_id]
    if not isinstance(state["channels_used"], set):
        state["channels_used"] = set(state["channels_used"])
    return state
    [customer_id]

def should_auto_escalate_from_state(state: dict, message: str) -> tuple:
    if state["contact_count"] >= 3:
        return True, "repeat_contact"
    if len(state["sentiment_trend"]) >= 3:
        last_3 = state["sentiment_trend"][-3:]
        if all(s < 0.4 for s in last_3):
            return True, "persistent_negative_sentiment"
    return False, ""

def build_system_prompt(channel: str) -> str:
    channel_instructions = {
        "email": "You are responding via EMAIL. Formal tone. Numbered steps. Max 400 words.",
        "whatsapp": "You are responding via WHATSAPP. Max 250 characters. No formal greetings. Direct and friendly.",
        "web_form": "You are responding via WEB FORM. Semi-formal, clear structure. Max 200 words."
    }
    return f"""You are a Customer Success agent for TechFlow SaaS.

{channel_instructions.get(channel, channel_instructions['email'])}

KNOWLEDGE BASE:
{KNOWLEDGE_BASE}

RULES:
- NEVER discuss pricing or refunds
- NEVER promise features not in the knowledge base
- Acknowledge frustration before solving
- Always end with a clear next step"""

def process_message(msg: CustomerMessage) -> AgentResponse:
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
    customer_id = normalize_customer_id(msg.customer_email, msg.customer_phone)
    state = get_or_create_customer_state(customer_id)
    state["contact_count"] += 1
    if state["original_channel"] is None:
        state["original_channel"] = msg.channel
    state["channels_used"].add(msg.channel)
    ticket_id = make_ticket_id()
    sentiment = estimate_sentiment(msg.content)
    state["sentiment_trend"].append(sentiment)

    should_escalate, reason = detect_escalation(msg.content)
    if not should_escalate and sentiment < 0.25:
        should_escalate, reason = True, "negative_sentiment"
    if not should_escalate:
        should_escalate, reason = should_auto_escalate_from_state(state, msg.content)

    if should_escalate:
        routing = {
            "legal_threat": "our legal team",
            "gdpr_compliance": "our legal team",
            "refund_request": "our billing team",
            "billing_inquiry": "our billing team",
            "human_requested": "a human support agent",
            "negative_sentiment": "a senior support agent",
            "repeat_contact": "a senior support agent",
        }
        route_name = routing.get(reason, "a support specialist")
        escalation_messages = {
            "email": f"I understand your concern. I'm connecting you with {route_name} who will follow up within 1 hour.\n\nYour reference: {ticket_id}",
            "whatsapp": f"Connecting you with {route_name} now. Ref: {ticket_id}",
            "web_form": f"Escalating to {route_name}. You'll receive an email within 1 hour.\n\nTicket: {ticket_id}"
        }
        escalation_msg = escalation_messages.get(msg.channel, escalation_messages["email"])
        final_response = format_for_channel(escalation_msg, msg.channel, ticket_id)
        state["resolution_status"] = "escalated"
        _tickets[ticket_id] = {"status": "escalated", "channel": msg.channel, "customer_id": customer_id, "reason": reason}
        return AgentResponse(message=final_response, channel=msg.channel, escalated=True,
                           escalation_reason=reason, ticket_id=ticket_id,
                           sentiment_score=sentiment, customer_id=customer_id)

    history_messages = []
    for prev in state["conversation_history"][-4:]:
        history_messages.append({"role": prev["role"], "content": prev["content"]})
    history_messages.append({"role": "user", "content": msg.content})

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=600,
            system=build_system_prompt(msg.channel),
            messages=history_messages
        )
        raw_response = response.content[0].text
    except Exception as e:
        raw_response = "I'm having trouble processing your request. Please try again or contact support@techflow.io."

    state["conversation_history"].append({"role": "user", "content": msg.content})
    state["conversation_history"].append({"role": "assistant", "content": raw_response})
    final_response = format_for_channel(raw_response, msg.channel, ticket_id)
    _tickets[ticket_id] = {"status": "resolved", "channel": msg.channel, "customer_id": customer_id}
    state["resolution_status"] = "resolved"

    return AgentResponse(message=final_response, channel=msg.channel, escalated=False,
                        escalation_reason="", ticket_id=ticket_id,
                        sentiment_score=sentiment, customer_id=customer_id)

if __name__ == "__main__":
    print("=" * 60)
    print("PROTOTYPE TEST — set ANTHROPIC_API_KEY first")
    print("=" * 60)
    test = CustomerMessage("how do i reset my password", "whatsapp", "test@user.com", "test@user.com", None)
    result = process_message(test)
    print(f"Ticket: {result.ticket_id}")
    print(f"Escalated: {result.escalated}")
    print(f"Response:\n{result.message}")