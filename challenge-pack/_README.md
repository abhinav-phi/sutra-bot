# Challenge Pack — Official magicpin AI Challenge Material

This folder is the **organizer-provided starter kit**, kept as-received:

| Item | What it is |
|---|---|
| `challenge-brief.md` | Official spec — what to build (Vera, 4-context framework, rubric) |
| `challenge-testing-brief.md` | Official HTTP contract — how submissions are tested |
| `engagement-design.md` / `engagement-research.md` | Background design/research docs on production Vera |
| `judge_simulator.py` | The official local LLM-powered judge |
| `dataset/` | Category contexts, seed files, and the deterministic generator |
| `examples/` | Judge↔bot API call examples + 10 scored case studies |

Nothing in here was authored by us; nothing here is imported by the bot at
runtime except read-only reference data (`examples/case-studies.md` feeds the
plagiarism self-check, `judge_simulator.py` is your local gate).

Our own work lives in [`../sutra/`](../sutra) (code), [`../docs/`](../docs)
(formal documentation), and [`../notes/`](../notes) (working notes).
