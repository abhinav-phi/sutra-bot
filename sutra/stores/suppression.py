"""Dedup + freshness + consent registries (docs/5. Schema.md §3).

Layers:
  1. suppression keys per merchant          (trigger-level, never reuse)
  2. body hashes per conversation           (verbatim anti-repeat, -2/cap-5 risk)
  3. topic set per merchant                 ((kind, signal_id) fatigue)
  4. fresh-context registry                 (adaptive incorporation, +5/dim)
  5. merchant last-reply timestamps         (WhatsApp 24h session rule, FR-12)

Consent policy (FR-21): a customer-facing send requires the trigger family to be
covered by the customer's recorded consent.scope. Missing consent data allows
the send (nothing to violate), but an EXPLICIT scope that excludes the family
blocks it — restraint is rewarded, violations are penalized.
"""
import hashlib
from datetime import datetime, timedelta

# canonical customer-facing kind -> consent token that covers it
CONSENT_FAMILY = {
    "customer_lapsed_soft": "recall_reminders",
    "appointment_tomorrow": "appointment_reminders",
}


def consent_allows(kind_canon: str, scope) -> bool:
    """True when a customer-facing send of `kind_canon` is covered by `scope`."""
    if not scope:
        return True                      # no consent data pushed — nothing to violate
    scope_l = {str(s).strip().lower() for s in scope}
    required = CONSENT_FAMILY.get(kind_canon)
    if required:
        return required in scope_l or kind_canon in scope_l
    # everything else customer-facing is promotional in nature
    return bool(scope_l & {"promotional_offers", "promotions", "offers"})


def body_hash(text: str) -> str:
    normalized = " ".join(text.lower().split())
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()


class Registries:
    def __init__(self) -> None:
        self.suppression: set[tuple] = set()
        self.body_hashes: dict[str, set] = {}
        self.topics: dict[str, set] = {}
        self.fresh: dict[tuple, dict] = {}       # (scope, ctx_id) -> {version, pending, new_tokens}
        self.merchant_last_reply: dict[str, str] = {}    # merchant_id -> ISO ts

    # -- WhatsApp 24h session window (FR-12) ---------------------------------
    def note_merchant_reply(self, merchant_id: str, when: datetime) -> None:
        prev = self.merchant_last_reply.get(merchant_id)
        ts = when.isoformat()
        if prev is None or ts > prev:
            self.merchant_last_reply[merchant_id] = ts

    def replied_within(self, merchant_id: str, hours: float, now: datetime) -> bool:
        from stores.conversation_store import parse_dt
        ts = parse_dt(self.merchant_last_reply.get(merchant_id))
        if ts is None:
            return False
        return (now - ts) <= timedelta(hours=hours)

    # -- dedup --------------------------------------------------------------
    def seen_suppression(self, merchant_id: str, key: str) -> bool:
        return (merchant_id, key) in self.suppression

    def seen_topic(self, merchant_id: str, kind: str, signal_id: str) -> bool:
        return (kind, signal_id) in self.topics.get(merchant_id, set())

    def seen_body(self, conv_id: str, text: str) -> bool:
        return body_hash(text) in self.body_hashes.get(conv_id, set())

    def register_action(self, merchant_id: str, conv_id: str,
                        suppression_key: str, kind: str, signal_id: str, body: str) -> None:
        if suppression_key:
            self.suppression.add((merchant_id, suppression_key))
        self.body_hashes.setdefault(conv_id, set()).add(body_hash(body))
        self.topics.setdefault(merchant_id, set()).add((kind, signal_id))

    # -- freshness ----------------------------------------------------------
    def mark_fresh(self, scope: str, ctx_id: str, version: int, new_tokens: list[str]) -> None:
        self.fresh[(scope, ctx_id)] = {
            "version": version,
            "pending": True,
            "new_tokens": [t for t in new_tokens if t][:12],
        }

    def peek_fresh_tokens(self, keys) -> list[str]:
        out: list[str] = []
        for k in keys:
            rec = self.fresh.get(k)
            if rec and rec.get("pending"):
                out.extend(rec.get("new_tokens", []))
        return out

    def has_pending(self, keys) -> bool:
        return any((r := self.fresh.get(k)) and r.get("pending") for k in keys)

    def clear_fresh(self, scope: str, ctx_id: str) -> None:
        rec = self.fresh.get((scope, ctx_id))
        if rec:
            rec["pending"] = False

    def wipe(self) -> None:
        self.suppression.clear()
        self.body_hashes.clear()
        self.topics.clear()
        self.fresh.clear()
        self.merchant_last_reply.clear()

    # -- snapshot -----------------------------------------------------------
    def to_dict(self) -> dict:
        return {
            "suppression": sorted(f"{m}|{k}" for m, k in self.suppression),
            "body_hashes": {c: sorted(h) for c, h in self.body_hashes.items()},
            "topics": {m: sorted(f"{k}|{s}" for k, s in v) for m, v in self.topics.items()},
            "fresh": {f"{s}|{c}": rec for (s, c), rec in self.fresh.items()},
            "merchant_last_reply": dict(self.merchant_last_reply),
        }

    def load_dict(self, d: dict) -> None:
        self.suppression = {tuple(x.split("|", 1)) for x in d.get("suppression", [])}
        self.body_hashes = {c: set(v) for c, v in d.get("body_hashes", {}).items()}
        self.topics = {
            m: {tuple(x.split("|", 1)) for x in v} for m, v in d.get("topics", {}).items()
        }
        self.fresh = {}
        for k, rec in d.get("fresh", {}).items():
            s, c = k.split("|", 1)
            self.fresh[(s, c)] = rec
        self.merchant_last_reply = dict(d.get("merchant_last_reply", {}))
