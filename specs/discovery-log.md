# Discovery Log - Customer Success FTE Incubation

## Round 1: Channel Pattern Analysis (52 tickets)

### Email (17 tickets)
- Avg length: 80-150 words, formal salutations
- Pricing/legal inquiries come mostly via email
- Frustrated customers use ALL CAPS in subject

### WhatsApp (18 tickets)
- Avg length: 3-8 words, no punctuation
- Escalation keywords: "human", "representative", "agent"
- Expects instant replies

### Web Form (17 tickets)
- Avg length: 40-80 words, more structured
- IT admins and compliance queries common here
- Customers provide more context upfront

## Round 2: Escalation Patterns

| Trigger | Count | Channel |
|---------|-------|---------|
| Refund request | 3 | Email, Web |
| Legal threat | 2 | Email |
| Human request | 3 | WhatsApp |
| Pricing inquiry | 3 | Email, Web |
| Angry customer | 4 | Email, WhatsApp |
| GDPR/compliance | 3 | Email, Web |

19/52 tickets (36%) required escalation in raw data.
After improving KB coverage: reduced to 15.4%.

## Round 3: Edge Cases (26 found)
See tests/test_edge_cases.py for all 26 cases.

Key discoveries:
- Dual intent (legal + technical) → legal always wins
- 3rd contact same customer → auto-escalate
- WhatsApp "human" single word → immediate escalation
- SQL injection in web form → must not crash

## Round 4: Response Quality

What works:
- Numbered steps for all channels
- Acknowledge frustration first
- One clarifying question max

What fails:
- Long email-style response on WhatsApp
- Generic "we'll look into it" responses
- Missing emotional tone

## Round 5: KB Coverage

| Topic | Covered | Gap |
|-------|---------|-----|
| Password reset | ✅ | None |
| 2FA | ✅ | Recovery needs human |
| Billing/pricing | ⚠️ | By design — escalate |
| Mobile app | ✅ | Error codes missing |
| API | ✅ | Rate limit upgrade path |
| GDPR | ⚠️ | DPA process → escalate |

## Requirements Crystallized

1. Normalize messages from 3 channels
2. Detect customer by email (primary), phone (secondary)
3. Create ticket with channel metadata every time
4. Semantic KB search
5. Channel-appropriate formatting
6. Escalation on triggers
7. Sentiment tracking
8. Cross-channel continuity
9. Never answer pricing/refunds
10. Auto-escalate on 3rd contact

## Performance Baseline
- Escalation rate: 15.4% (target <25%) ✅
- Avg processing: 30.9ms (no LLM) ✅
- Test pass rate: 31/31 ✅