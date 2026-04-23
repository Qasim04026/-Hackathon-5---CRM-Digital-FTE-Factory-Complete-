# Transition Checklist: General → Custom Agent

## 1. Discovered Requirements
- [x] R1: Normalize messages from 3 channels
- [x] R2: Detect customer by email/phone
- [x] R3: Create ticket with channel metadata every time
- [x] R4: KB search
- [x] R5: Channel-appropriate formatting
- [x] R6: Escalation on triggers
- [x] R7: Sentiment tracking
- [x] R8: Cross-channel continuity
- [x] R9: Never answer pricing/refunds
- [x] R10: Auto-escalate on 3rd contact

## 2. Working System Prompt
You are a Customer Success agent for TechFlow SaaS.
[EMAIL] Formal. Numbered steps. Max 400 words.
[WHATSAPP] Max 250 chars. No greeting. Direct.
[WEB FORM] Semi-formal. Max 200 words.
RULES: No pricing, no refunds, acknowledge frustration first.
## 3. Edge Cases (26 documented, all passing)
See tests/test_edge_cases.py

## 4. Response Patterns
- Email: Hi [Name], + steps + Best regards
- WhatsApp: Direct answer + Reply for more help 👋
- Web Form: Thanks for reaching out! + steps + ticket ID

## 5. Escalation Rules Finalized
| Trigger | Route |
|---------|-------|
| legal/lawyer/sue | legal@techflow.io |
| refund | billing@techflow.io |
| pricing | billing@techflow.io |
| human/agent | support-team@techflow.io |
| sentiment < 0.25 | support-team@techflow.io |
| 3rd contact | support-team@techflow.io |

## 6. Performance Baseline
| Metric | Result | Target |
|--------|--------|--------|
| Tests | 31/31 | 100% |
| Escalation rate | 15.4% | <25% |
| Avg processing | 30.9ms | <3000ms |

## Status
- [x] Prototype working
- [x] Edge cases documented
- [x] MCP tools defined (7 tools)
- [x] Channel patterns identified
- [x] Escalation rules finalized
- [x] Performance measured
- [ ] MCP → @function_tool (Part 2)
- [ ] Pydantic validation (Part 2)
- [ ] PostgreSQL schema (Part 2)

## ✅ Ready for Part 2