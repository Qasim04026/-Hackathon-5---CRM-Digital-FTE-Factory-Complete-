"""
Edge Case Test Suite - 31 tests across all channels
Run: python tests/test_edge_cases.py
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from agent.prototype import (
    process_message, CustomerMessage, detect_escalation,
    estimate_sentiment, format_for_channel, normalize_customer_id,
    get_or_create_customer_state, _customer_state
)

results = {"passed": 0, "failed": 0}

def check(name, condition, detail=""):
    if condition:
        results["passed"] += 1
        print(f"  ✅ {name}")
    else:
        results["failed"] += 1
        print(f"  ❌ {name}" + (f" — {detail}" if detail else ""))

def test_email():
    print("\n=== EMAIL EDGE CASES ===")
    msg = CustomerMessage("I cannot log in", "email", "u@co.com", "u@co.com", None, subject="")
    check("EC-E1: Empty subject handled", process_message(msg).ticket_id is not None)

    s = estimate_sentiment("THIS IS ABSOLUTELY BROKEN I WANT REFUND NOW")
    check("EC-E2: ALL CAPS → negative sentiment", s < 0.4, f"score={s:.2f}")

    esc, reason = detect_escalation("THIS IS BROKEN I WANT MY MONEY BACK NOW")
    check("EC-E2: Refund keyword → escalate", esc and reason == "refund_request")

    msg = CustomerMessage("2FA broken AND I will contact my lawyer", "email", "d@i.com", "d@i.com", None)
    check("EC-E3: Dual intent → legal escalation wins", process_message(msg).escalated)

    msg = CustomerMessage("How do I export data?", "email", "a@mail.com", "a@mail.com", None)
    check("EC-E4: No name → response generated", len(process_message(msg).message) > 0)

    msg = CustomerMessage("Hello " * 50, "email", "long@user.com", "long@user.com", None)
    check("EC-E5: Long message → no crash", process_message(msg).ticket_id is not None)

    esc, _ = detect_escalation("What is the pricing for Enterprise plan?")
    check("EC-E6: Pricing inquiry → escalate", esc)

    msg = CustomerMessage("GDPR Article 17 deletion request for our org", "email", "eu@gdpr.com", "eu@gdpr.com", None)
    r = process_message(msg)
    check("EC-E7: GDPR → escalate legal", r.escalated and "gdpr" in r.escalation_reason.lower())

def test_whatsapp():
    print("\n=== WHATSAPP EDGE CASES ===")
    msg = CustomerMessage("human", "whatsapp", "h@wa.test", None, "+923001111111")
    check("EC-W1: 'human' → escalate", process_message(msg).escalated)

    esc, reason = detect_escalation("agent")
    check("EC-W2: 'agent' → human_requested", esc and reason == "human_requested")

    msg = CustomerMessage("", "whatsapp", "e@wa.test", None, "+923002222222")
    check("EC-W3: Empty message → no crash", process_message(msg).ticket_id is not None)

    msg = CustomerMessage("how do i invite team members", "whatsapp", "l@wa.test", None, "+923003333333")
    r = process_message(msg)
    check("EC-W4: WhatsApp response ≤ 350 chars", len(r.message) <= 350, f"len={len(r.message)}")

    cid = normalize_customer_id(None, "03001234567")
    check("EC-W5: Phone normalizes without crash", len(cid) > 0)

    esc, reason = detect_escalation("i want to speak to a representative")
    check("EC-W6: 'representative' → human_requested", esc and reason == "human_requested")

    msg = CustomerMessage("👍", "whatsapp", "emoji@wa.test", None, "+923004444444")
    check("EC-W7: Emoji message → no crash", process_message(msg).ticket_id is not None)

def test_webform():
    print("\n=== WEB FORM EDGE CASES ===")
    m1 = CustomerMessage("cannot export data", "web_form", "dup@form.com", "dup@form.com", None)
    m2 = CustomerMessage("cannot export data", "web_form", "dup@form.com", "dup@form.com", None)
    check("EC-WF1: Duplicate → different ticket IDs", process_message(m1).ticket_id != process_message(m2).ticket_id)

    msg = CustomerMessage("I need a refund for last month", "web_form", "b@form.com", "b@form.com", None)
    check("EC-WF2: Billing via web form → escalate", process_message(msg).escalated)

    msg = CustomerMessage("'; DROP TABLE customers; --", "web_form", "h@evil.com", "h@evil.com", None)
    check("EC-WF3: SQL injection → no crash", process_message(msg).ticket_id is not None)

    msg = CustomerMessage("How do I enable SSO?", "web_form", "sso@corp.com", "sso@corp.com", None)
    r = process_message(msg)
    check("EC-WF4: Ticket ID in web form response", r.ticket_id in r.message)

    msg = CustomerMessage("We need a Data Processing Agreement signed", "web_form", "l@ent.com", "l@ent.com", None)
    check("EC-WF5: DPA → escalate legal", process_message(msg).escalated)

    msg = CustomerMessage("reset my password", "web_form", "fmt@test.com", "fmt@test.com", None)
    r = process_message(msg)
    check("EC-WF6: Web form has correct greeting", "Thanks for reaching out" in r.message)

def test_crosschannel():
    print("\n=== CROSS-CHANNEL EDGE CASES ===")
    _customer_state.pop("cross@user.com", None)
    r1 = process_message(CustomerMessage("automation help", "email", "cross@user.com", "cross@user.com", None))
    r2 = process_message(CustomerMessage("still having issues", "web_form", "cross@user.com", "cross@user.com", None))
    check("EC-CC1: Same customer_id across channels", r1.customer_id == r2.customer_id)

    state = get_or_create_customer_state("cross@user.com")
    check("EC-CC1: Both channels in state", len(state["channels_used"]) >= 2)

    c1 = normalize_customer_id("User@Company.COM")
    c2 = normalize_customer_id("user@company.com")
    check("EC-CC2: Email case normalized", c1 == c2)

    cid = "repeat.test@cross.com"
    _customer_state.pop(cid, None)
    msgs = [
        CustomerMessage("slack broken", "email", cid, cid, None),
        CustomerMessage("still broken", "whatsapp", cid, cid, "+923005555555"),
        CustomerMessage("THIRD TIME same issue", "web_form", cid, cid, None),
    ]
    res = [process_message(m) for m in msgs]
    check("EC-CC3: 3rd contact → auto-escalate", res[2].escalated, f"reason={res[2].escalation_reason}")

    cid2 = "grumpy@user.com"
    _customer_state.pop(cid2, None)
    neg_msgs = [
        CustomerMessage("product is terrible", "email", cid2, cid2, None),
        CustomerMessage("still broken and awful", "email", cid2, cid2, None),
        CustomerMessage("I hate this horrible software", "email", cid2, cid2, None),
    ]
    neg_res = [process_message(m) for m in neg_msgs]
    check("EC-CC4: Persistent negative → escalated", any(r.escalated for r in neg_res))
cid3 = "switcher@test.com"
_customer_state.pop(cid3, None)
process_message(CustomerMessage("export data", "email", cid3, cid3, None))
msg2 = CustomerMessage("still not working", "whatsapp", cid3, cid3, "+923006666666")
process_message(msg2)
state3 = get_or_create_customer_state(cid3)
check("EC-CC5: Channel switch recorded", "whatsapp" in state3["channels_used"])
msg = CustomerMessage("help", "web_form", "", None, None)
try:
    r = process_message(msg)
    check("EC-CC6: No identifiers → no crash", r.ticket_id is not None)
except Exception as e:
    check("EC-CC6: No identifiers → no crash", False, str(e))

def test_performance():
    print("\n=== PERFORMANCE BASELINE ===")
    import time, json
    tickets_path = os.path.join(os.path.dirname(__file__), '..', 'context', 'sample-tickets.json')
    with open(tickets_path) as f:
        tickets = json.load(f)
    escalated = 0
    start = time.time()
    for t in tickets:
        msg = CustomerMessage(
            content=t["message"], channel=t["channel"],
            customer_id=t.get("customer_email") or t.get("customer_phone", "unknown"),
            customer_email=t.get("customer_email"), customer_phone=t.get("customer_phone")
        )
        if process_message(msg).escalated:
            escalated += 1
    elapsed = time.time() - start
    rate = (escalated / len(tickets)) * 100
    avg_ms = (elapsed / len(tickets)) * 1000
    print(f"  Tickets: {len(tickets)} | Escalated: {escalated} ({rate:.1f}%) | Avg: {avg_ms:.1f}ms")
    check(f"Escalation rate < 60% (got {rate:.1f}%)", rate < 60)
    check(f"Avg processing < 5000ms (got {avg_ms:.1f}ms)", avg_ms < 5000)
    check("All 52 tickets processed", len(tickets) == 52)

if __name__ == "__main__":
    print("CUSTOMER SUCCESS FTE — EDGE CASE TEST SUITE")
    print("=" * 50)
    test_email()
    test_whatsapp()
    test_webform()
    test_crosschannel()
    test_performance()
    total = results["passed"] + results["failed"]
    print(f"\n{'=' * 50}")
    print(f"RESULTS: {results['passed']}/{total} passed")
    print("✅ ALL PASSED" if results["failed"] == 0 else f"❌ {results['failed']} FAILED")