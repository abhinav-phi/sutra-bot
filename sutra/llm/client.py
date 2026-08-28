"""Multi-provider LLM client: primary Anthropic -> secondary OpenAI -> caller falls back.

Determinism: temperature=0, top_p=1 on every call (Rules D-01). Callers additionally
cache responses by input hash so identical inputs are byte-identical within a run.
"""
import asyncio
import time
from typing import Optional

import httpx


class AllProvidersFailed(Exception):
    pass


class QuotaExceeded(Exception):
    """Raised when the hard spend ceiling is hit; pipeline switches to templates."""


class _Provider:
    def __init__(self, name: str, kind: str, api_key: str, model: str) -> None:
        self.name, self.kind, self.api_key, self.model = name, kind, api_key, model


class LLMClient:
    def __init__(self, settings, ledger) -> None:
        self.settings = settings
        self.ledger = ledger
        self.providers: list[_Provider] = []
        # b.ai custom endpoint — primary (fast, high-quality composition)
        if settings.custom_llm_api_key and settings.custom_llm_base_url:
            self.providers.append(_Provider("custom", "custom",
                                            settings.custom_llm_api_key,
                                            settings.custom_llm_model))
        # OpenRouter — secondary fallback
        if settings.openrouter_api_key:
            self.providers.append(_Provider("openrouter", "openrouter",
                                            settings.openrouter_api_key,
                                            settings.openrouter_model))
        if settings.anthropic_api_key:
            self.providers.append(_Provider("anthropic", "anthropic",
                                            settings.anthropic_api_key, settings.primary_model))
        if settings.openai_api_key:
            self.providers.append(_Provider("openai", "openai",
                                            settings.openai_api_key, settings.secondary_model))

    async def complete(self, system: str, user: str, max_tokens: int = 600,
                       timeout_s: Optional[float] = None) -> str:
        if not self.providers:
            raise AllProvidersFailed("no providers configured")
        if self.ledger.status() == "hard":
            raise QuotaExceeded("spend ceiling reached; fallback-only mode")
        timeout = timeout_s or self.settings.llm_timeout_s
        errors = []
        for p in self.providers:
            # TokenRouter free tier intermittently rejects cold requests
            # (cache_only_cold / 503); one quick retry before falling through.
            attempts = 2 if p.kind == "custom" else 1
            for attempt in range(attempts):
                try:
                    if p.kind == "custom":
                        return await self._call(p, system, user,
                                                self.settings.custom_llm_max_tokens, timeout)
                    return await self._call(p, system, user, max_tokens, timeout)
                except QuotaExceeded:
                    raise
                except Exception as e:                      # noqa: BLE001 — try next tier
                    if attempt + 1 < attempts and ("503" in str(e) or "cache_only" in str(e)
                                                   or "Service Unavailable" in str(e)):
                        await asyncio.sleep(0.5)
                        continue
                    errors.append(f"{p.name}: {e}")
                    break
        raise AllProvidersFailed("; ".join(errors) or "unknown")

    async def _call(self, p: _Provider, system: str, user: str,
                    max_tokens: int, timeout_s: float) -> str:
        t0 = time.monotonic()
        async with httpx.AsyncClient(timeout=timeout_s) as cx:
            if p.kind == "custom":
                base = self.settings.custom_llm_base_url.rstrip("/")
                url = f"{base}/chat/completions"
                if not base.endswith("/chat/completions"):
                    url = f"{base}/chat/completions" if "/chat/completions" not in base else base
                payload = {
                    "model": p.model,
                    "max_tokens": max_tokens,
                    "temperature": 0,
                    "top_p": 1,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                }
                if self.settings.custom_llm_send_thinking:
                    payload["thinking"] = {"type": "disabled"}
                r = await cx.post(url, headers={"Authorization": f"Bearer {p.api_key}",
                                                "Content-Type": "application/json"},
                                  json=payload)
                r.raise_for_status()
                data = r.json()
                text = data["choices"][0]["message"].get("content") or ""
                usage = data.get("usage", {})
                in_toks = usage.get("prompt_tokens", 0)
                out_toks = usage.get("completion_tokens", 0)
            elif p.kind == "openrouter":
                r = await cx.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={"Authorization": f"Bearer {p.api_key}",
                             "Content-Type": "application/json",
                             "HTTP-Referer": "https://github.com/sutra-bot",
                             "X-Title": "Sutra magicpin bot"},
                    json={
                        "model": p.model,
                        "max_tokens": max_tokens,
                        "temperature": 0,
                        "top_p": 1,
                        "messages": [
                            {"role": "system", "content": system},
                            {"role": "user", "content": user},
                        ],
                    },)
                r.raise_for_status()
                data = r.json()
                text = data["choices"][0]["message"]["content"]
                usage = data.get("usage", {})
                in_toks, out_toks = usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)
            elif p.kind == "anthropic":
                r = await cx.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={"x-api-key": p.api_key, "anthropic-version": "2023-06-01"},
                    json={
                        "model": p.model,
                        "max_tokens": max_tokens,
                        "temperature": 0,
                        "top_p": 1,
                        "system": system,
                        "messages": [{"role": "user", "content": user}],
                    },
                )
                r.raise_for_status()
                data = r.json()
                text = "".join(c.get("text", "") for c in data.get("content", []))
                usage = data.get("usage", {})
                in_toks, out_toks = usage.get("input_tokens", 0), usage.get("output_tokens", 0)
            else:
                r = await cx.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {p.api_key}"},
                    json={
                        "model": p.model,
                        "temperature": 0,
                        "top_p": 1,
                        "max_tokens": max_tokens,
                        "messages": [
                            {"role": "system", "content": system},
                            {"role": "user", "content": user},
                        ],
                    },
                )
                r.raise_for_status()
                data = r.json()
                text = data["choices"][0]["message"]["content"]
                usage = data.get("usage", {})
                in_toks = usage.get("prompt_tokens", 0)
                out_toks = usage.get("completion_tokens", 0)
        self.ledger.log(p.name, in_toks, out_toks, time.monotonic() - t0)
        return text or ""
