"""Hash-keyed response cache — determinism guarantee + cost reduction (ADR-04)."""
import hashlib
import json


class ResponseCache:
    def __init__(self, max_entries: int = 2048) -> None:
        self._data: dict[str, dict] = {}
        self._max = max_entries
        self.hits = 0
        self.misses = 0

    @staticmethod
    def make_key(*parts) -> str:
        canonical = json.dumps(list(parts), sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def get(self, key: str) -> dict | None:
        rec = self._data.get(key)
        if rec is not None:
            self.hits += 1
        else:
            self.misses += 1
        return rec

    def put(self, key: str, value: dict) -> None:
        if len(self._data) >= self._max:
            self._data.pop(next(iter(self._data)))       # FIFO eviction, deterministic
        self._data[key] = value

    def wipe(self) -> None:
        self._data.clear()

    def snapshot(self) -> dict:
        return {"size": len(self._data), "hits": self.hits, "misses": self.misses}
