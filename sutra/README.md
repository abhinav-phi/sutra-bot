# Sutra — magicpin AI Challenge Submission

> Hybrid deterministic-guardrail composer: routed LLM core + facts-registry validation gate + three-tier fallback + reply state machine.

Sutra is our entry for the magicpin AI Challenge: a stateful HTTP bot that plays **Vera**, composing context-grounded WhatsApp messages for merchants (and on-behalf-of-merchant messages to their customers), driven entirely by the judge harness.

Full documentation lives in [`../docs/`](../docs/) (`1. PRD.md` … `8. Rules.md`).

## Quickstart

```bash
cd sutra
python -m venv .venv && . .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env                                 # optional; empty keys => template-only mode
uvicorn bot:app --host 0.0.0.0 --port 8081
```

Then, from the repo root:

```bash
python challenge-pack/dataset/generate_dataset.py --seed-dir challenge-pack/dataset --out expanded
python sutra/scripts/load_dataset.py --dir expanded --url http://localhost:8081
bash sutra/scripts/run_simulator.sh                  # official judge_simulator.py
```

## Endpoints

| Route | Purpose |
|---|---|
| `GET /v1/healthz` | liveness + context counts derived from the live store |
| `GET /v1/metadata` | team identity |
| `POST /v1/context` | idempotent push; higher version replaces atomically; stale ⇒ 409 |
| `POST /v1/tick` | filter → rank → top-K parallel compose → ≤20 grounded actions |
| `POST /v1/reply` | classify → state machine → send / wait(900–3600s) / end |
| `POST /v1/teardown` | wipes every store/registry/cache |

## Architecture highlights

- **Facts registry**: every number/date/citation in an LLM draft must trace to pushed context; miss ⇒ one re-prompt ⇒ deterministic template. Fabrication can't ship.
- **13-check validation gate** in enforced order: URL scan → grounding → single CTA → CTA-in-last-sentence → CTA-policy-per-trigger-kind → taboo words → domain vocab → language match → owner greeting → fact density → anti-repetition → plagiarism-vs-case-studies (<0.6 Jaccard) → rationale grounding.
- **Router over 15 trigger kinds × scope** with aliases so *unseen* harness kinds still route to real shapes — we generalize by kind, never memorize the 30 visible pairs.
- **Three-tier fallback**: primary frontier model → secondary fast model on a different provider → deterministic templates. The bot never goes silent because an LLM did.
- **Determinism**: temperature=0/top_p=1 + hash-keyed response cache (byte-equality test included).
- **Ops floor**: healthz counts derived from the live store, atomic disk snapshot every 30s with startup recovery, bounded waits, $20/$25 spend guardrails.

## Model choice & tradeoffs

- Primary composition on a fast OpenAI-compatible endpoint (Groq qwen3.8-27b with a one-shot gate-repair retry); secondary on a *different provider* (OpenRouter minimax-m3) for outage resilience.
- Replies are regex-first classified and templated — sub-millisecond and fully deterministic (ADR-08).
- Same-version context re-push is answered `409 stale_version` (matches `examples/api-call-examples.md` Example 1.5) while leaving state untouched (the briefs' "no-op").

**Measured model bake-off (2026-09-01, full report [`../docs/9. ModelBench.md`](../docs/9.%20ModelBench.md)):** of the six models on the api.b.ai endpoint, `deepseek-v4-flash` scored **97/100** (JSON-perfect, execution-verified code, 2.91s avg) and is the composer candidate; `qwen3.8-flash` (94/100) is the secondary. Two provider facts are baked into the client: a **~9–10 req/min per-key rate limit** (sequential pacing + 429 backoff) and **reasoning-token burn** (all six are reasoning models — `max_tokens ≥ 2000` or `content` comes back empty, which the pipeline treats as a model failure and falls to the next tier).

## Tests (release gate)

```bash
pytest            # from sutra/
```

Covers: api-call-examples smoke flows (HARD gate), determinism byte-equality across two fresh instances, Phase-4 replay arcs (auto-reply hell / intent transition / hostile / objection / cold-start replay), adaptive injection (fresh digest used, metric shift reflected, nothing hallucinated).

## Honest limitations

- Template mode is deliberately plainer than LLM mode — it exists so degraded ≠ dead.
- Language verification for regional scripts (mr/ta/te/kn) is accept-only; hi/en checks are enforced.
- Top-10 replay bonus depends on harness ranking we don't control; base scores are prioritized first (W3).
