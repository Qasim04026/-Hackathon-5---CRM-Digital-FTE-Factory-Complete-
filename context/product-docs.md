# TechFlow Product Documentation

## 1. Getting Started

### 1.1 Account Setup
- Sign up at techflow.io/signup with your work email
- Verify email within 24 hours (check spam folder)
- Create your first workspace: Dashboard → New Workspace → Enter name
- Invite team members: Settings → Members → Invite by email

### 1.2 Password Reset
- Go to techflow.io/login → Click "Forgot Password"
- Enter your registered email address
- Check inbox for reset link (valid for 2 hours)
- If no email received: check spam, or contact support

### 1.3 Two-Factor Authentication (2FA)
- Enable: Settings → Security → Enable 2FA
- Supports: Authenticator apps (Google Auth, Authy) and SMS
- Lost 2FA device: Submit identity verification to support

## 2. Core Features

### 2.1 Boards & Tasks
- Create boards: Workspace → + New Board
- Task statuses: To Do, In Progress, Review, Done (customizable)
- Assign tasks: Click task → Assignee dropdown → Select member
- Due dates: Click task → Calendar icon → Pick date
- Subtasks: Open task → Add Subtask button

### 2.2 Automation Rules
- Available on Pro and above plans
- Create rule: Board Settings → Automation → + New Rule
- Example: "When task moved to Done → notify assignee via email"
- Limit: 50 automation rules per workspace (Pro), unlimited (Business+)

### 2.3 Integrations
- **Slack:** Settings → Integrations → Slack → Authorize
- **GitHub:** Settings → Integrations → GitHub → Connect repo
- **Google Drive:** Settings → Integrations → Google Drive → Authorize
- **Zapier:** Available on Pro+, connect at zapier.com/apps/techflow

### 2.4 Storage & File Uploads
- Starter: 5GB total workspace storage
- Pro: 50GB total workspace storage
- Business: 500GB total workspace storage
- Supported formats: Images, PDFs, docs, videos up to 2GB per file

## 3. Account & Billing

### 3.1 Plan Changes
- Upgrade: Settings → Billing → Upgrade Plan (instant)
- Downgrade: Effective at end of current billing cycle
- Pricing questions: Must be directed to billing@techflow.io

### 3.2 Data Export
- Export all data: Settings → Data → Export (CSV + JSON)
- Processing time: Up to 24 hours for large workspaces
- Data retained 30 days after cancellation

### 3.3 SSO (Single Sign-On)
- Available on Business and Enterprise plans only
- Supported: SAML 2.0, Google Workspace, Microsoft Azure AD
- Setup: Settings → Security → SSO Configuration

## 4. Troubleshooting

### 4.1 Login Issues
- Clear browser cache and cookies
- Try incognito/private mode
- Disable browser extensions
- Try different browser (Chrome recommended)
- Check status.techflow.io for outages

### 4.2 Slow Performance
- Check internet connection speed (min 5 Mbps recommended)
- Clear browser cache
- Disable unused integrations
- Check status.techflow.io for known issues

### 4.3 Email Notifications Not Working
- Check spam/junk folder
- Add noreply@techflow.io to contacts
- Settings → Notifications → verify preferences
- Check if email is verified in account settings

### 4.4 Mobile App Issues
- Minimum: iOS 14+ or Android 10+
- Force close and reopen app
- Check for app updates in App Store / Play Store
- Uninstall and reinstall if persistent

## 5. Admin & Enterprise Features

### 5.1 Audit Logs (Business+)
- Access: Admin Panel → Audit Logs
- Tracks: logins, permission changes, data exports, member changes
- Retention: 90 days (Business), 1 year (Enterprise)

### 5.2 Custom Roles & Permissions
- Available on Business+ plans
- Create role: Admin Panel → Roles → + New Role
- Permissions: View, Edit, Comment, Admin

### 5.3 API Access
- API docs: developer.techflow.io
- Generate API key: Settings → Developer → API Keys → Generate
- Rate limit: 1000 req/hour (Pro), 10,000 req/hour (Business+)

## 6. Data & Privacy
- Data stored in AWS us-east-1 (default), EU region available on Enterprise
- GDPR compliant: Data Processing Agreement available on request
- SOC 2 Type II certified
- Data deletion requests: privacy@techflow.io