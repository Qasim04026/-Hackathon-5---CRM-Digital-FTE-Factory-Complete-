# Agent Skills Manifest - Customer Success FTE

## Skill 1: Knowledge Retrieval
- **When to use:** Customer asks product questions
- **Inputs:** query (str), max_results (int)
- **Outputs:** Relevant documentation snippets
- **Fallback:** No results → escalate to human
- **Tool:** search_knowledge_base

## Skill 2: Sentiment Analysis
- **When to use:** EVERY incoming message
- **Inputs:** message text
- **Outputs:** sentiment_score (0.0-1.0), should_escalate, reason
- **Threshold:** Escalate if score < 0.3
- **Tool:** analyze_sentiment

## Skill 3: Escalation Decision
- **When to use:** After generating response
- **Inputs:** message, sentiment_score, context
- **Outputs:** should_escalate (bool), reason, route email
- **Routes:** Legal → legal@ | Billing → billing@ | Other → support-team@
- **Tool:** escalate_to_human

## Skill 4: Channel Adaptation
- **When to use:** Before every send_response
- **Inputs:** response_text, target_channel
- **Outputs:** Channel-formatted response
- **Rules:**
  - Email: Formal + greeting + signature
  - WhatsApp: Max 300 chars, no greeting, emoji ok
  - Web Form: Semi-formal, ticket reference included
- **Tool:** format_response_for_channel

## Skill 5: Customer Identification
- **When to use:** On every incoming message
- **Inputs:** email, phone, name
- **Outputs:** unified customer_id, merged history
- **Logic:** Email first → Phone second → Create new
- **Tool:** get_customer_history

## Skill 6: Response Generation
- **When to use:** After KB search
- **Inputs:** query, kb_results, history, channel
- **Rules:** Acknowledge first → Solve second → Next step

## Skill 7: Ticket Management
- **When to use:** Start of EVERY conversation
- **Inputs:** customer_id, issue, priority, channel
- **Outputs:** ticket_id
- **Rule:** Create ticket FIRST before any other action
- **Tool:** create_ticket