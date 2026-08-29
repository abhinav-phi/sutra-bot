"""Canonical constants for Sutra. Single source of truth (docs/5. Schema.md §5)."""

SCOPES = {"category", "merchant", "customer", "trigger"}

SEND_AS_VERA = "vera"
SEND_AS_MERCHANT_ON_BEHALF = "merchant_on_behalf"

CTA_OPEN_ENDED = "open_ended"
CTA_BINARY_YES_NO = "binary_yes_no"
CTA_BINARY_CONFIRM_CANCEL = "binary_confirm_cancel"
CTA_MULTI_CHOICE_SLOT = "multi_choice_slot"
CTA_NONE = "none"
VALID_CTAS = {
    CTA_OPEN_ENDED,
    CTA_BINARY_YES_NO,
    CTA_BINARY_CONFIRM_CANCEL,
    CTA_MULTI_CHOICE_SLOT,
    CTA_NONE,
}

ACTION_SEND = "send"
ACTION_WAIT = "wait"
ACTION_END = "end"

# Reply-brain classifications (docs TechSpec AI-3)
CLASS_ACCEPT = "accept"
CLASS_QUESTION = "question"
CLASS_OBJECTION = "objection"
CLASS_AUTO_REPLY = "auto_reply"
CLASS_EXPLICIT_INTENT = "explicit_intent"
CLASS_HOSTILE = "hostile"
CLASS_OFF_TOPIC = "off_topic"
ALL_CLASSES = (
    CLASS_ACCEPT,
    CLASS_QUESTION,
    CLASS_OBJECTION,
    CLASS_AUTO_REPLY,
    CLASS_EXPLICIT_INTENT,
    CLASS_HOSTILE,
    CLASS_OFF_TOPIC,
)

# The 15 canonical trigger kinds (challenge-brief §5.3 / PRD routing table)
CATEGORY_SLUGS = ("dentists", "salons", "restaurants", "gyms", "pharmacies")

# Aliases: harness/generator may emit extra kinds; map them onto a canonical
# family so routing generalizes to unseen scenarios (never hallucinate content).
KIND_ALIASES = {
    "research_digest": "category_research_digest_release",
    "seasonal_perf_dip": "perf_dip",
    "supply_alert": "regulation_change",
    "ipl_match_today": "local_news_event",
    "recall_due": "customer_lapsed_soft",
    "chronic_refill_due": "customer_lapsed_soft",
    "bridal_followup": "wedding_package_followup",
    "trial_followup": "customer_lapsed_soft",
    "curious_ask_due": "scheduled_recurring",
    "winback_eligible": "winback_eligible",
}

WAIT_SECONDS_ALLOWED = (900, 1800, 3600)
