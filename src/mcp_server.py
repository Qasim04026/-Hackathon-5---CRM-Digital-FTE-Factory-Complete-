"""
Customer Success FTE - MCP Server
7 tools exposed via Model Context Protocol
"""
from datetime import datetime
from enum import Enum

class Channel(str, Enum):
    EMAIL = "email"
    WHATSAPP = "whatsapp"
    WEB_FORM = "web_form"

_tickets = {}
_customers = {}

KNOWLEDGE_BASE = {
    "password reset": {"title": "Password Reset", "content": "Go to techflow.io/login → Forgot Password → Enter email → Check inbox (link valid 2hrs). Check spam if not received.", "category": "account"},
    "two factor 2fa": {"title": "Two-Factor Authentication", "content": "Enable: Settings → Security → Enable 2FA. Lost device: requires human escalation for identity verification.", "category": "security"},
    "invite team": {"title": "Invite Team Members", "content": "Settings → Members → Invite by email. Select role. Invitation sent immediately.", "category": "team"},
    "slack": {"title": "Slack Integration", "content": "Connect: Settings → Integrations → Slack → Authorize. Not working: re-authorize.", "category": "integrations"},
    "storage": {"title": "Storage Limits", "content": "Starter: 5GB | Pro: 50GB | Business: 500GB. Max file: 2GB.", "category": "account"},
    "automation": {"title": "Automation Rules", "content": "Pro+ only. Create: Board Settings → Automation → New Rule. Limits: 50 (Pro), unlimited (Business+).", "category": "features"},
    "export data": {"title": "Data Export", "content": "Settings → Data → Export (CSV+JSON). Up to 24hrs for large workspaces.", "category": "account"},
    "sso": {"title": "SSO Configuration", "content": "Business/Enterprise only. SAML 2.0, Google Workspace, Azure AD. Setup: Settings → Security → SSO.", "category": "security"},
    "mobile app": {"title": "Mobile App", "content": "Min iOS 14+ / Android 10+. Fix crashes: force close, update, reinstall.", "category": "technical"},
    "api": {"title": "API Access", "content": "Generate: Settings → Developer → API Keys. Rate limits: 1000/hr (Pro), 10000/hr (Business+).", "category": "developer"},
}

def simple_search(query: str, max_results: int = 5) -> list:
    query_lower = query.lower()
    results = []
    for key, doc in KNOWLEDGE_BASE.items():
        score = sum(1 for word in query_lower.split() if word in key or word in doc["content"].lower())
        if score > 0:
            results.append((score, doc))
    results.sort(key=lambda x: x[0], reverse=True)
    return [doc for _, doc in results[:max_results]]

def detect_escalation(message: str) -> tuple:
    msg_lower = message.lower()
    rules = {
        "legal_threat": ["lawyer", "attorney", "sue ", "lawsuit"],
        "human_requested": ["human", "agent", "representative"],
        "billing_inquiry": ["refund", "pricing", "how much", "discount"],
        "gdpr_compliance": ["gdpr", "data deletion", "dpa"],
    }
    for reason, keywords in rules.items():
        if any(kw in msg_lower for kw in keywords):
            return True, reason
    return False, ""

# Tool functions (would be decorated with @server.tool in full MCP setup)

def search_knowledge_base(query: str) -> str:
    """Search product documentation."""
    results = simple_search(query)
    if not results:
        return "No relevant documentation found. Consider escalating to human support."
    return "\n\n---\n\n".join([f"**{r['title']}**\n{r['content']}" for r in results])

def create_ticket(customer_id: str, issue: str, priority: str, channel: str) -> str:
    """Create support ticket with channel tracking."""
    ticket_id = f"TKT-{len(_tickets)+1:04d}"
    _tickets[ticket_id] = {
        "customer_id": customer_id, "issue": issue,
        "priority": priority, "channel": channel,
        "status": "open", "created_at": datetime.utcnow().isoformat()
    }
    return f"Ticket created: {ticket_id} | Channel: {channel} | Priority: {priority}"

def get_customer_history(customer_id: str) -> str:
    """Get customer history across all channels."""
    customer_tickets = [t for t in _tickets.values() if t["customer_id"] == customer_id]
    if not customer_tickets:
        return f"New customer: {customer_id} — No prior history."
    lines = [f"Customer {customer_id} — {len(customer_tickets)} prior contact(s):"]
    for t in customer_tickets[-5:]:
        lines.append(f"  [{t['channel'].upper()}] {t['created_at'][:10]} — {t['issue']} ({t['status']})")
    return "\n".join(lines)

def escalate_to_human(ticket_id: str, reason: str) -> str:
    """Escalate to human support."""
    if ticket_id in _tickets:
        _tickets[ticket_id]["status"] = "escalated"
        _tickets[ticket_id]["escalation_reason"] = reason
    routing = {
        "legal_threat": "legal@techflow.io",
        "gdpr_compliance": "legal@techflow.io",
        "refund_request": "billing@techflow.io",
        "billing_inquiry": "billing@techflow.io",
    }
    route = routing.get(reason, "support-team@techflow.io")
    return f"Escalated {ticket_id} to {route} | Reason: {reason}"

def send_response(ticket_id: str, message: str, channel: str) -> str:
    """Send response via appropriate channel."""
    if channel == "email":
        formatted = f"[EMAIL] Hi,\n\n{message}\n\nBest regards,\nTechFlow Support Team\nRef: {ticket_id}"
    elif channel == "whatsapp":
        short = message[:300] if len(message) > 300 else message
        formatted = f"[WHATSAPP] {short}\n\nReply for more help 👋"
    else:
        formatted = f"[WEB FORM] Thanks for reaching out!\n\n{message}\n\nTicket: {ticket_id}"
    if ticket_id in _tickets:
        _tickets[ticket_id]["status"] = "resolved"
    return f"Response sent via {channel} | Ticket: {ticket_id} | Length: {len(message)} chars"

def analyze_sentiment(message: str) -> str:
    """Analyze message sentiment."""
    msg_lower = message.lower()
    neg_words = ["angry", "frustrated", "ridiculous", "broken", "terrible", "hate"]
    pos_words = ["thank", "great", "amazing", "helpful", "love", "excellent"]
    neg = sum(1 for w in neg_words if w in msg_lower)
    pos = sum(1 for w in pos_words if w in msg_lower)
    caps_ratio = sum(1 for c in message if c.isupper()) / max(len(message), 1)
    if caps_ratio > 0.3:
        neg += 2
    score = max(0.05, min(0.95, 0.5 + (pos * 0.1) - (neg * 0.1)))
    assessment = "NEGATIVE — Consider escalating" if score < 0.3 else "NEUTRAL" if score < 0.7 else "POSITIVE"
    should_esc, reason = detect_escalation(message)
    return f"Sentiment: {score:.2f} | {assessment}\nEscalation needed: {'YES — ' + reason if should_esc else 'No'}"

def format_response_for_channel(response: str, channel: str, customer_name: str = "Customer") -> str:
    """Format response for target channel."""
    if channel == "email":
        return f"Hi {customer_name},\n\n{response}\n\nBest regards,\nTechFlow Support Team"
    elif channel == "whatsapp":
        return f"{response[:280]}\n\nReply for more help 👋"
    else:
        return f"Thanks for reaching out!\n\n{response}\n\nNeed more help? Submit a new request."

if __name__ == "__main__":
    print("MCP Server Tools Test")
    print(search_knowledge_base("password reset"))
    print(create_ticket("user@test.com", "Cannot login", "high", "email"))
    print(analyze_sentiment("I am so ANGRY your product is BROKEN"))