import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

KNOWLEDGE_DATA = [
    {
        "title": "Password Reset",
        "content": "Go to techflow.io/login → Click Forgot Password → Enter registered email → Check inbox for reset link valid 2 hours. If no email check spam folder or add noreply@techflow.io to contacts.",
        "category": "account"
    },
    {
        "title": "Two-Factor Authentication",
        "content": "Enable 2FA: Settings → Security → Enable 2FA. Supports Google Authenticator Authy and SMS. Lost device requires identity verification and human escalation.",
        "category": "security"
    },
    {
        "title": "Invite Team Members",
        "content": "Invite members: Settings → Members → Invite by email. Select role for new member. Invitation email sent immediately.",
        "category": "team"
    },
    {
        "title": "Automation Rules",
        "content": "Available on Pro and above plans only. Create: Board Settings → Automation → New Rule. Limits 50 rules Pro unlimited Business plus. If not triggering verify email notifications enabled in Settings.",
        "category": "features"
    },
    {
        "title": "Storage Limits",
        "content": "Starter 5GB Pro 50GB Business 500GB. Max file size 2GB per file. Approaching limit delete old files or upgrade plan.",
        "category": "account"
    },
    {
        "title": "Slack Integration",
        "content": "Connect: Settings → Integrations → Slack → Authorize. Stopped working re-authorize the integration. Select notification channels after connecting.",
        "category": "integrations"
    },
    {
        "title": "GitHub Integration",
        "content": "Connect: Settings → Integrations → GitHub → Connect repo. Choose specific repos can auto-create tasks from issues.",
        "category": "integrations"
    },
    {
        "title": "Login Issues",
        "content": "Clear browser cache and cookies. Try incognito mode. Disable browser extensions. Chrome recommended. Check status.techflow.io for outages.",
        "category": "technical"
    },
    {
        "title": "Mobile App Issues",
        "content": "Minimum iOS 14 plus or Android 10 plus. Fix crashes force close update app reinstall. Check status.techflow.io for known issues.",
        "category": "technical"
    },
    {
        "title": "Data Export",
        "content": "Settings → Data → Export CSV and JSON format. Up to 24 hours for large workspaces. Data kept 30 days after cancellation.",
        "category": "account"
    },
    {
        "title": "API Access",
        "content": "Generate key: Settings → Developer → API Keys → Generate. Rate limits 1000 per hour Pro 10000 per hour Business plus. 401 Unauthorized verify key copied correctly.",
        "category": "developer"
    },
    {
        "title": "SSO Configuration",
        "content": "Available on Business and Enterprise plans. Supports SAML 2.0 Google Workspace Azure AD. Setup: Settings → Security → SSO Configuration.",
        "category": "security"
    },
    {
        "title": "Subtasks",
        "content": "Create subtask: Open parent task → Add Subtask button → Enter name. Subtasks inherit board and assignee from parent unless changed.",
        "category": "features"
    },
    {
        "title": "Email Notifications Not Working",
        "content": "Check spam folder. Add noreply@techflow.io to contacts. Settings → Notifications verify preferences. Ensure email is verified in account settings.",
        "category": "technical"
    },
    {
        "title": "GDPR and Data Privacy",
        "content": "TechFlow is GDPR compliant SOC 2 Type II certified. Data stored AWS us-east-1 EU region available on Enterprise. Deletion requests privacy@techflow.io. DPA available on request.",
        "category": "legal"
    },
    {
        "title": "Plan Comparison",
        "content": "Starter 19 dollars per month 5 users 5GB storage basic boards. Pro 49 dollars per month 20 users 50GB automation integrations. Business 149 dollars per month 100 users 500GB SSO audit logs. Enterprise custom pricing unlimited users.",
        "category": "billing"
    },
    {
        "title": "Zapier Integration",
        "content": "Available on Pro plus plans. Connect at zapier.com/apps/techflow. Enables automation with thousands of other apps.",
        "category": "integrations"
    },
    {
        "title": "Audit Logs",
        "content": "Available on Business plus plans. Access: Admin Panel → Audit Logs. Tracks logins permission changes data exports member changes. Retention 90 days Business 1 year Enterprise.",
        "category": "security"
    },
    {
        "title": "Custom Roles and Permissions",
        "content": "Available on Business plus plans. Create role: Admin Panel → Roles → New Role. Permissions: View Edit Comment Admin.",
        "category": "features"
    },
    {
        "title": "Google Drive Integration",
        "content": "Connect: Settings → Integrations → Google Drive → Authorize. Not syncing re-authorize and check Drive permissions.",
        "category": "integrations"
    }
]

async def load_knowledge():
    DATABASE_URL = "postgresql://fte_user:fte_password_local@postgres:5432/fte_db"
    
    conn = await asyncpg.connect(DATABASE_URL)
    
    try:
        # Clear existing data
        await conn.execute("DELETE FROM knowledge_base")
        
        # Insert all knowledge
        for item in KNOWLEDGE_DATA:
            await conn.execute("""
                INSERT INTO knowledge_base (title, content, category)
                VALUES ($1, $2, $3)
            """, item["title"], item["content"], item["category"])
        
        count = await conn.fetchval("SELECT COUNT(*) FROM knowledge_base")
        print(f"✅ Knowledge base loaded: {count} entries")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(load_knowledge())