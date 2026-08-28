"""LLM spend ledger with soft/hard ceilings (docs/2. TechSpec.md §16; Rules C-01..C-04)."""
import os
import time
from collections import Counter

# USD per 1M tokens (input, output) — conservative defaults, env-overridable.
DEFAULT_PRICES = {
    "anthropic": (3.0, 15.0),
    "openai": (0.15, 0.60),
    "openrouter": (0.0, 0.0),
    "custom": (0.0, 0.0),
    "other": (1.0, 5.0),
}


class Ledger:
    def __init__(self, soft_usd: float = 20.0, hard_usd: float = 25.0) -> None:
        self.soft_usd = float(os.environ.get("SPEND_SOFT_USD", soft_usd))
        self.hard_usd = float(os.environ.get("SPEND_HARD_USD", hard_usd))
        self.calls: Counter = Counter()
        self.tokens: Counter = Counter()
        self.spend_by_provider: dict[str, float] = {}
        self.latencies: list[float] = []

    def log(self, provider: str, prompt_tokens: int, completion_tokens: int,
            latency_s: float) -> float:
        pin, pout = DEFAULT_PRICES.get(provider, DEFAULT_PRICES["other"])
        cost = (prompt_tokens / 1e6) * pin + (completion_tokens / 1e6) * pout
        self.calls[provider] += 1
        self.tokens[f"{provider}:in"] += prompt_tokens
        self.tokens[f"{provider}:out"] += completion_tokens
        self.spend_by_provider[provider] = self.spend_by_provider.get(provider, 0.0) + cost
        self.latencies.append(latency_s)
        return cost

    @property
    def spend(self) -> float:
        return sum(self.spend_by_provider.values())

    def status(self) -> str:
        if self.spend >= self.hard_usd:
            return "hard"
        if self.spend >= self.soft_usd:
            return "soft"
        return "ok"

    def snapshot(self) -> dict:
        avg = sum(self.latencies) / len(self.latencies) if self.latencies else 0.0
        return {
            "spend_usd": round(self.spend, 4),
            "status": self.status(),
            "calls": dict(self.calls),
            "avg_latency_s": round(avg, 2),
        }

    def wipe(self) -> None:
        self.calls.clear()
        self.tokens.clear()
        self.spend_by_provider.clear()
        self.latencies.clear()
