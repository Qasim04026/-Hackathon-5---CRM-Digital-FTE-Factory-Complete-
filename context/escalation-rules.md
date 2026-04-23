# Escalation Rules - TechFlow Customer Success FTE

## Automatic Escalation Triggers (MUST escalate immediately)

### Legal & Compliance
- Customer mentions: "lawyer", "attorney", "legal", "sue", "lawsuit", "court"
- GDPR deletion requests → legal@techflow.io
- SOC 2 / compliance documentation requests → legal@techflow.io
- Data Processing Agreement requests → legal@techflow.io

### Billing & Financial
- Any pricing negotiation or custom pricing request
- Refund requests (partial or full)
- Non-profit / discount requests
- Enterprise pricing inquiries
- All escalate to → billing@techflow.io

### Emotional / Sentiment
- Profanity or aggressive language
- Sentiment score < 0.3
- Customer explicitly threatens to leave/switch
- Customer mentions this is 2nd or 3rd contact for same issue
- Customer requests human agent (phrases: "human", "agent", "representative", "real person")

### Technical Complexity
- 2FA lockout with identity verification needed
- Cannot resolve after 2 knowledge base searches
- Known outage or data loss reports
- SSO configuration issues (complex setup)

## Escalation Routing

| Category | Route To | Priority |
|----------|----------|----------|
| Legal/GDPR | legal@techflow.io | P1 - Immediate |
| Refunds | billing@techflow.io | P1 - Immediate |
| Pricing negotiation | billing@techflow.io | P2 - Same day |
| Data loss | support-team@techflow.io | P1 - Immediate |
| 2FA lockout | support-team@techflow.io | P1 - Immediate |
| Human requested | support-team@techflow.io | P2 - Within 1 hour |
| Complex technical | support-team@techflow.io | P2 - Within 2 hours |
| Angry customer | support-team@techflow.io | P1 - Immediate |

## What NOT to Escalate
- Password reset (self-service, document steps)
- How-to questions with answers in product docs
- Plan comparison questions (answer from pricing table)
- General feature questions
- Bug reports (create ticket, acknowledge, escalate only if P1)

## Escalation Message Template
When escalating, always include:
1. Customer identifier (email/phone)
2. Channel they contacted from
3. Summary of issue (2-3 sentences)
4. Reason for escalation
5. Sentiment assessment
6. Conversation history link