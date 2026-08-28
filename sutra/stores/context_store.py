"""Context store — single source of truth for pushed contexts.

Version semantics (docs/2. TechSpec.md §5.3):
- higher version or new key  -> atomic replace, "stored"
- equal or lower version     -> state untouched, "stale"
  (examples/api-call-examples.md Example 1.5 shows same-version re-push
   answered with 409 stale_version; the briefs call this a no-op — we keep
   the state no-op and surface it as stale so both readings hold.)
healthz counts are ALWAYS derived from this store at request time.
"""
from datetime import datetime, timezone


class ContextStore:
    def __init__(self) -> None:
        self._data: dict[tuple, dict] = {}

    # -- writes -------------------------------------------------------------
    def put(self, scope: str, context_id: str, version: int, payload: dict,
            received_at: str | None = None) -> tuple[str, dict | None]:
        """Returns (status, previous_record). status in {"stored","stale","invalid"}."""
        if scope not in ("category", "merchant", "customer", "trigger"):
            return "invalid", None
        key = (scope, context_id)
        cur = self._data.get(key)
        if cur is not None and version <= cur["version"]:
            return "stale", cur
        prev = dict(cur) if cur else None
        self._data[key] = {
            "version": int(version),
            "payload": payload,
            "received_at": received_at or datetime.now(timezone.utc).isoformat(),
        }
        return "stored", prev

    def wipe(self) -> None:
        self._data.clear()

    # -- reads --------------------------------------------------------------
    def get(self, scope: str, context_id: str) -> dict | None:
        rec = self._data.get((scope, context_id))
        return rec["payload"] if rec else None

    def get_record(self, scope: str, context_id: str) -> dict | None:
        return self._data.get((scope, context_id))

    def counts(self) -> dict:
        counts = {"category": 0, "merchant": 0, "customer": 0, "trigger": 0}
        for scope, _cid in self._data:
            counts[scope] = counts.get(scope, 0) + 1
        return counts

    def items(self):
        return self._data.items()

    def to_dict(self) -> dict:
        return {f"{s}|{c}": rec for (s, c), rec in self._data.items()}

    def load_dict(self, d: dict) -> None:
        for k, rec in d.items():
            s, c = k.split("|", 1)
            self._data[(s, c)] = rec
