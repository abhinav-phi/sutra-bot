"""Conversation state machine — arcs per classification (docs AppFlow §14).

Every arc respects: one CTA max, bounded waits {900,1800,3600}, graceful ends,
intent => action mode immediately (Pattern-D anti-pattern avoided).
"""
from datetime import datetime, timedelta, timezone

from schemas import enums as E
from stores.conversation_store import utc_now

HINGLISH = (
    "Looks like an auto-reply 😊 Owner ji jab free ho, bas YES likh dijiye — "
    "main turant continue kar dunga."
)
ENGLISH_FLAG = (
    "Looks like an auto-reply 😊 Whenever the owner gets a sec, just reply YES "
    "and I'll pick this right back up."
)


def _is_hinglish(language: str) -> bool:
    return language.startswith("hi")


def _artifact(kind: str) -> str:
    return {
        "category_research_digest_release": "the abstract + a patient-ed WhatsApp draft",
        "perf_dip": "a short diagnosis of the dip + the fix plan",
        "perf_spike": "a capture play to ride this spike",
        "festival_upcoming": "your festival-week campaign draft",
        "competitor_opened": "a profile refresh + retention push plan",
        "customer_lapsed_soft": "the recall booking flow for your patient",
        "regulation_change": "a compliance checklist mapped to your setup",
    }.get(kind, "the next step, ready to go")


def decide(classification: str, state, *, language: str = "en",
           turn_number: int = 0, now: datetime | None = None) -> dict:
    """Returns a /v1/reply response dict; mutates `state`."""
    now = now or utc_now()
    state.last_merchant_reply_at = now.isoformat()
    engaged = classification in (E.CLASS_EXPLICIT_INTENT, E.CLASS_ACCEPT,
                                 E.CLASS_QUESTION)
    if engaged:
        state.nudge_count = 0

    # turn budget — never hit the 5-turn cap awkwardly
    if turn_number >= 4 and classification != E.CLASS_EXPLICIT_INTENT \
            and classification != E.CLASS_HOSTILE and not state.ended:
        state.ended = True
        state.ended_reason = "turn_budget"
        return {"action": E.ACTION_END,
                "rationale": "Turn budget reached; exiting gracefully before the cap."}

    if classification == E.CLASS_HOSTILE:
        state.ended = True
        state.ended_reason = "merchant_opted_out"
        return {"action": E.ACTION_END,
                "rationale": "Merchant frustration explicit; closing politely and suppressing this thread."}

    if classification == E.CLASS_AUTO_REPLY:
        state.auto_reply_count += 1
        n = state.auto_reply_count
        if n == 1:
            state.flagged_auto_reply = True
            state.nudge_count += 1
            return {"action": E.ACTION_SEND,
                    "body": HINGLISH if _is_hinglish(language) else ENGLISH_FLAG,
                    "cta": E.CTA_BINARY_YES_NO,
                    "rationale": "Detected canned auto-reply; one explicit flag for the owner."}
        if n == 2:
            state.wait_until = (now + timedelta(seconds=1800)).isoformat()
            return {"action": E.ACTION_WAIT, "wait_seconds": 1800,
                    "rationale": "Same auto-reply twice — owner likely away; backing off 30 min."}
        state.ended = True
        state.ended_reason = "auto_reply_loop"
        return {"action": E.ACTION_END,
                "rationale": "Auto-reply 3x with zero engagement signal; closing without burning more turns."}

    if classification == E.CLASS_OFF_TOPIC:
        state.off_topic_count += 1
        if state.off_topic_count > 1:
            state.ended = True
            state.ended_reason = "off_topic_repeat"
            return {"action": E.ACTION_END,
                    "rationale": "Second out-of-scope ask; staying on-mission means exiting politely."}
        topic = (state.last_spine or {}).get("summary") or "your account's next best step"
        body = ("That one I'll leave to your CA 🙂 Coming back to where we were — "
                f"{str(topic)[:90]}. Shall we continue with it?")
        state.nudge_count += 1
        return {"action": E.ACTION_SEND, "body": body, "cta": E.CTA_OPEN_ENDED,
                "rationale": "Out-of-scope declined once, redirected to the live thread."}

    if classification == E.CLASS_EXPLICIT_INTENT:
        state.intent_committed = True
        art = _artifact(state.trigger_kind or "")
        body = (f"Great — on it. Drafting {art} now; it'll be ready in ~10 minutes. "
                f"Reply CONFIRM and I fire it as soon as it's set.")
        return {"action": E.ACTION_SEND, "body": body, "cta": E.CTA_BINARY_CONFIRM_CANCEL,
                "rationale": "Explicit merchant commitment honored: switched straight to action mode."}

    if classification == E.CLASS_OBJECTION:
        state.nudge_count += 1
        if state.nudge_count <= 1:
            return {"action": E.ACTION_SEND,
                    "body": ("No problem at all. Want just the 2-line version instead? "
                             "Say YES whenever — otherwise I'll leave you to it."),
                    "cta": E.CTA_BINARY_YES_NO,
                    "rationale": "Softened the ask once after an objection; exit offered either way."}
        state.ended = True
        state.ended_reason = "not_interested"
        return {"action": E.ACTION_END,
                "rationale": "Repeated objection respected; ending cleanly."}

    if classification == E.CLASS_QUESTION:
        anchor = ((state.last_spine or {}).get("summary") or "")[:110]
        body = f"Quick context: {anchor or 'happy to explain'}."\
               .replace("..", ".")
        body += " Want the full breakdown, or should I set up the short version?"
        state.nudge_count += 1
        return {"action": E.ACTION_SEND, "body": body, "cta": E.CTA_OPEN_ENDED,
                "rationale": "Answered with the anchored fact; one open follow-up to keep momentum."}

    if classification == E.CLASS_ACCEPT:
        art = _artifact(state.trigger_kind or "")
        body = f"On it — sending {art}. Anything you'd like tweaked, just say the word."
        state.nudge_count += 1
        return {"action": E.ACTION_SEND, "body": body, "cta": E.CTA_OPEN_ENDED,
                "rationale": "Acceptance acknowledged with immediate delivery + open door."}

    # fallback: treat as light accept
    state.nudge_count += 1
    return {"action": E.ACTION_SEND,
            "body": "Noted! Give me a minute and I'll bring this thread to a useful next step.",
            "cta": E.CTA_OPEN_ENDED,
            "rationale": "Generic acknowledgement keeping the thread alive within budget."}
