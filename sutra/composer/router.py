"""Trigger router — (trigger.kind × scope) -> variant config.

15 canonical kinds from the brief; KIND_ALIASES fold generator/harness extras
onto a family so FRESH scenarios still route to a real composition shape
(generalize by kind, never memorize by test_id).
"""
from schemas import enums as E


def _cfg(variant, cta_policy, levers):
    return {"variant": variant, "cta_policy": cta_policy, "levers": levers}


TABLE = {
    # ---- merchant scope ----
    "category_research_digest_release": _cfg("research_cite", "open", ["reciprocity", "curiosity", "effort"]),
    "regulation_change":                _cfg("regulation_cite", "open", ["reciprocity", "specificity"]),
    "category_trend_movement":          _cfg("trend_leverage", "binary", ["social_proof", "curiosity"]),
    "competitor_opened":                _cfg("competitor_alert", "binary", ["loss_aversion", "urgency"]),
    "festival_upcoming":                _cfg("festival_urgency", "binary", ["urgency", "timeliness", "judgment_hook"]),
    "weather_heatwave":                 _cfg("weather_hook", "binary", ["timeliness", "specificity"]),
    "local_news_event":                 _cfg("news_hook", "open", ["curiosity", "timeliness"]),
    "perf_spike":                       _cfg("perf_delta_loss", "binary", ["specificity", "loss_aversion"]),
    "perf_dip":                         _cfg("perf_delta_loss", "binary", ["loss_aversion", "urgency"]),
    "milestone_reached":                _cfg("milestone_celebrate", "binary", ["social_proof", "specificity"]),
    "dormant_with_vera":                _cfg("dormant_reengage", "binary", ["reciprocity", "curiosity"]),
    "review_theme_emerged":             _cfg("review_theme_fix", "binary", ["asking_merchant", "specificity"]),
    "scheduled_recurring":              _cfg("curious_ask", "open", ["asking_merchant", "curiosity"]),
    "renewal_due":                      _cfg("renewal_nudge", "binary", ["loss_aversion", "urgency"]),
    # ---- customer scope ----
    "customer_lapsed_soft":             _cfg("recall_booking", "slot", ["specificity", "effort"]),
    "customer_lapsed_hard":             _cfg("recall_booking", "slot", ["specificity", "effort"]),
    "appointment_tomorrow":             _cfg("appt_confirm", "binary", ["specificity", "urgency"]),
    # ---- seed-dataset kinds (full payload coverage) ----
    "active_planning_intent":           _cfg("planning_draft", "binary", ["effort", "curiosity"]),
    "category_seasonal":                _cfg("seasonal_shift", "binary", ["timeliness", "specificity"]),
    "gbp_unverified":                   _cfg("profile_verify", "binary", ["loss_aversion", "specificity"]),
    "cde_opportunity":                  _cfg("cde_webinar", "open", ["curiosity", "reciprocity"]),
    "winback_eligible":                 _cfg("winback_merchant", "binary", ["loss_aversion", "social_proof"]),
    "wedding_package_followup":         _cfg("bridal_followup", "slot", ["specificity", "urgency"]),
}

GENERIC_MERCHANT = _cfg("generic_notify", "binary", ["specificity", "curiosity"])
GENERIC_CUSTOMER = _cfg("recall_booking", "slot", ["specificity", "effort"])


def route(kind: str, scope: str) -> dict:
    canon = E.KIND_ALIASES.get(kind, kind)
    cfg = TABLE.get(canon)
    if cfg is None:
        cfg = GENERIC_CUSTOMER if scope == "customer" else GENERIC_MERCHANT
    return cfg


def canon_kind(kind: str) -> str:
    return E.KIND_ALIASES.get(kind, kind)
