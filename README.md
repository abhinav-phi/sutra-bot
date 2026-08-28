# Sutra — magicpin AI Challenge Submission

> *Hybrid deterministic-guardrail composer: routed LLM core + facts-registry validation gate + three-tier fallback + reply state machine.*

**Sutra** is our entry to the [magicpin AI Challenge](challenge-pack/challenge-brief.md): a hosted, deterministic message-composition engine that plays **Vera** — magicpin's merchant-AI assistant — composing context-grounded WhatsApp messages for merchants (and on-behalf-of-merchant messages to their customers), driven entirely by the judge harness over 6 HTTP endpoints.

## Repository map

| Path | What lives here |
|---|---|
| [`sutra/`](sutra/) | 💻 The bot — FastAPI source, tests, scripts ([code README](sutra/README.md)) |
| [`docs/`](docs/) | 📘 Formal documentation suite — PRD · TechSpec · AppFlow · Design · Schema · ImplementationPlan · Tracker · Rules |
| [`challenge-pack/`](challenge-pack/) | 📥 Official organizer-provided material (briefs, dataset, judge simulator, examples) |
| [`notes/`](notes/) | 🧠 Our working notes — full challenge guidelines, planning prompt, docs-generation prompt |

## Quickstart

```bash
cd sutra
pip install -r requirements.txt
uvicorn bot:app --host 0.0.0.0 --port 8081          # empty API keys => deterministic template mode
```

Then from the repo root:

```bash
python challenge-pack/dataset/generate_dataset.py --seed-dir challenge-pack/dataset --out expanded
python sutra/scripts/load_dataset.py --dir expanded --url http://localhost:8081   # warmup rehearsal (355 contexts)
bash sutra/scripts/run_simulator.sh                                              # official local judge*
```

\* set your `LLM_PROVIDER` / `LLM_API_KEY` inside `challenge-pack/judge_simulator.py` first.

Run the release-gate test suite:

```bash
cd sutra && pytest        # 20 tests — smoke gate, determinism, adversarial replays, doc-sync
```

## Why this design (60-second version)

- **Grounding over fluency** — the challenge scores *decisions*, not prose; every number/date/citation in an LLM draft must trace to pushed context or the draft is rejected and re-composed.
- **Never silent, never garbage** — primary frontier model → secondary fast model on a different provider → deterministic templates. LLM outage degrades scores; it never zeroes them.
- **Generalize by trigger kind, never memorize** — routing covers all 15 documented kinds plus aliases, because the real harness injects scenarios the visible 30 pairs never show.
- **Operational floor first** — healthz counts derived from live store, atomic context versioning, anti-repetition registries, bounded waits, spend ceilings: −20 penalty pool stays at zero.

Full rationale: [`docs/2. TechSpec.md`](docs/2.%20TechSpec.md) (ADRs) and [`docs/1. PRD.md`](docs/1.%20PRD.md) (scoring map).

## Status

- ✅ All P0/P1 features implemented; 20/20 release-gate tests passing
- 🟨 Remaining before submission: judge-simulator ≥80% run with a live LLM key, full api-example replay, deploy + external monitor

Honest limitations & tradeoffs: [`sutra/README.md`](sutra/README.md) and [`docs/7. Tracker.md`](docs/7.%20Tracker.md).
