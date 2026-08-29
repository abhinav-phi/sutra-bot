# MASTER PLANNING & STRATEGY PROMPT — magicpin AI Challenge ("Vera" Message Engine)

You are reviewing the complete starter package for the **magicpin AI Challenge**, where participants build **Vera** — magicpin's AI merchant-growth assistant — as a hosted, deterministic message-composition bot.

I am giving you the following source files:

* `challenge-brief.md` — full product spec (Vera, 4-context framework, compose contract, rubric)
* `challenge-testing-brief.md` — HTTP contract (5 endpoints, harness phases, limits, penalties)
* `engagement-design.md` — internal design doc behind the framework
* `engagement-research.md` — research notes on production Vera data access
* `examples/api-call-examples.md` — exact judge↔bot HTTP call examples
* `examples/case-studies.md` — 10 judge-scored anchor compositions (out of 50)
* `dataset/` — 5 category JSONs + seed files + `generate_dataset.py`
* `judge_simulator.py` — official local LLM-powered judge
* `guidelines.md` — consolidated human-readable guide of all of the above

Treat all files together as **the single source of truth** for the competition.

---

# 🚨 ABSOLUTELY CRITICAL INSTRUCTION

**DO NOT write, scaffold, or execute any code.**

**DO NOT build the bot, endpoints, or composer.**

**DO NOT create or modify any project files.**

**DO NOT regenerate or rewrite any of the provided files.**

I am **STRICTLY asking for DEEP STRATEGIC PLANNING ONLY.**

Your entire output must be a **planning & strategy report in normal text/Markdown** covering:

1. What the challenge *actually* rewards (beyond the surface reading)
2. What we should build and why
3. How we should build it (architecture + design decisions, described, not coded)
4. In what order we should work
5. Where every scoring point lives and how we capture each one
6. What will go wrong if we're careless, and how we pre-empt it

I will do the actual building myself later using your plan.

---

# ==================================================
# YOUR ROLE
# ==================================================

Act as a combination of:

* Principal Software Architect
* Senior AI/ML Engineer (LLM systems, prompt engineering, evaluation)
* Agentic AI Architect
* Conversational Product Designer (WhatsApp-first, Indian SMB audiences)
* FinTech-Grade Reliability Engineer (timeouts, idempotency, graceful degradation)
* Data Strategist (context grounding, hallucination prevention)
* Hackathon Judge
* Technical Hiring Evaluator (magicpin explicitly treats this as a hiring filter)

Review the documents as if our submission will actually be built, deployed, judged on unseen scenarios, and read by magicpin's hiring team.

Judge them as:

> **THE BATTLEFIELD MAP OF A COMPETITION WE INTEND TO WIN**

---

# ==================================================
# PRIMARY OBJECTIVE
# ==================================================

Determine whether we can confidently win a top-10 position, and produce the definitive strategy:

> *"What exactly should we build, how should it think, in what order do we build it, and where are the traps that eliminate most teams?"*

Be brutally honest. Do not assume the documented rubric tells the whole story. Read between the lines of the briefs, case studies, and simulator code — the organizers told us exactly how we'll be scored; find the implications they didn't spell out.

---

# ==================================================
# PHASES TO EXECUTE (analysis only — no code)
# ==================================================

## PHASE 1 — CHALLENGE COMPREHENSION AUDIT

Read all files and answer:

* What is the *real* test beneath the stated task? (Hint: the page says "AI scores decisions, not just writing style", and warns that bots that pattern-match the simulator will fail.)
* What does the judge value implicitly that isn't in the rubric?
* What do the 10 case studies reveal about judge psychology (what earned 50s vs what lost points)?
* Which pain points of production Vera (auto-reply pollution, intent-handoff failures, generic copy, low frequency) are secretly the scoring levers?
* What is deliberately left open (extra credit) and is it worth attempting?

## PHASE 2 — SCORING REVERSE-ENGINEERING (where every point lives)

Build the complete points map and a capture strategy per point:

| Source | Points |
|---|---|
| Per-message quality | 50 total: Specificity /10 · Decision Quality /10 · Category Fit /10 · Merchant Fit /10 · Engagement Compulsion /10 |
| Adaptive-context incorporation | up to +5 per dimension |
| Replay conversations (top 10 only) | up to +30 |
| Operational failures | down to −20 (healthz −10 · tick/reply timeouts −1 · malformed/empty/repeat −2 · URL in body −3) |

For each dimension: what earns 9–10, what caps it (no citation ⇒ cap 7; fabrication/repetition ⇒ cap 5/dimension), and what concretely loses points (generic offers, multiple CTAs, buried CTA, ignored language pref, generic "Hi" without owner name, treating customers identically).

Then rank: which points are cheapest to guarantee vs hardest to earn?

## PHASE 3 — ARCHITECTURE DECISION PLANNING

Compare at least 2–3 candidate architectures (described, not coded) and recommend ONE with justification:

* Pure-deterministic rule/template engine vs LLM composer vs hybrid (deterministic guardrails around an LLM core) vs agentic planner-executor
* How routing by `trigger.kind` × scope should shape prompt variants
* Determinism strategy under an LLM (temperature, caching, seeded behavior, fallback templates)
* State management for pushed contexts (versioning, atomic replacement) and conversations
* Latency/cost budget design against the hard limits: 30s per call, 10 req/s, 500 KB payloads, ≤20 actions/tick, 60 simulated minutes
* Failure posture: what happens when the LLM is slow/down mid-window (must never emit garbage)

State single points of failure and how the design survives them.

## PHASE 4 — COMPOSER DESIGN PLANNING

Plan how composition decisions get made:

* Signal-selection logic: how the bot picks THE one driving signal per (category, merchant, trigger, customer?) tuple instead of dumping facts
* Grounding rules: every number/date/citation traceable to pushed context; anti-hallucination validation before send
* Voice engine: per-vertical tone/vocabulary/taboos enforcement (dentists clinical-peer, gyms no-shame coach, pharmacies precise, salons warm, restaurants operator-to-operator)
* Language handling: en / hi / hi-en mix matching per identity fields
* CTA policy: binary default, slot-choice only for booking, none for pure-info; single CTA in the last sentence
* Suppression/dedup logic so topics never repeat
* Restraint logic: when returning zero actions beats sending filler

## PHASE 5 — CONVERSATION BRAIN PLANNING (multi-turn)

Plan the reply-handling state machine:

* Incoming-message classification: accept / question / objection / auto-reply / explicit-intent / hostile / off-topic
* Auto-reply detection heuristic (verbatim repetition 3×+) and correct arc: flag once → wait → end
* Intent transition: "let's do it" ⇒ action mode immediately, never another qualifying question
* Hostile/off-topic: polite decline + redirect, or graceful end
* Anti-repetition memory per conversation; when to stop entirely
* How conversation state interacts with freshly injected context mid-conversation

## PHASE 6 — DATA & CONTEXT EXPLOITATION PLAN

* Map every field of the 4 contexts (category / merchant / trigger / customer) to concrete message moves
* Which signals deserve priority (e.g., `signals[]`, peer-stat gaps, customer_aggregate-derived counts, consent scope)
* How to exploit the dataset generator + 30 canonical pairs for development without overfitting to them
* Handling surprise injections: new digests, shifted metrics, unseen merchants/customers arriving mid-test

## PHASE 7 — EVALUATION STRATEGY

* How to use `judge_simulator.py` properly (config, scenarios: warmup, phase2_short, auto_reply_hell, intent_transition, hostile, all, full_evaluation; verdict bands ≥80/60/40%)
* Build a self-evaluation harness plan BEYOND the visible pairs: synthetic fresh-injection tests, adversarial replies, determinism checks
* Define measurable internal quality bars per rubric dimension

## PHASE 8 — DEPLOYMENT & OPS PLANNING

* Hosting choice reasoning (public URL, `/v1/*`, survives 10 req/s)
* Healthz count accuracy, 409 stale-version path, restart discipline during the window
* Cost ceiling and quota sizing for LLM APIs across the full run
* Post-submission liveness obligation (judges run fresh scenarios after submission)

## PHASE 9 — WORKSTREAM & TIMELINE PLAN

Produce the build order with dependencies and critical path (planning only):

* Setup/dataset → skeleton endpoints → deterministic fallback composer → LLM composer with routing → validation gate → reply brain → self-test loop → hardening → deploy → README/submission
* Parallel tracks if 2+ people; what to cut first if time runs short; demo-day failure contingencies

## PHASE 10 — HIDDEN RISKS REGISTER

Think like a hostile senior engineer. Find non-obvious killers, e.g.:

* Pattern-matching-the-30-pairs trap ⇒ zero generalization on fresh scenarios
* Hallucination under adaptive injection (citing digest items never pushed)
* LLM latency spikes eating the 30s budget mid-tick
* Idempotency/versioning bugs silently composing from stale context
* Healthz counts drifting after version bumps
* Repetition/suppression leaks across ticks
* Cost/quota exhaustion before the window ends
* Replay-stage behaviors never exercised locally until it's too late
* Anything else you find in the docs/code

Each risk: likelihood × impact × mitigation.

## PHASE 11 — JUDGE & HIRING-SIGNAL OPTIMIZATION

* What the rationale field must look like (judge cross-checks it against output)
* README/metadata content that signals seniority to magicpin's hiring team
* Which "open challenges" (auto-reply detection, intent transitions, cadence planning, language switching, knowing when to stop) yield the strongest hiring signal per hour invested

## PHASE 12 — PRIORITIZE EVERY STRATEGY DECISION

Classify every recommendation:

### 🔴 P0 — MUST-HAVE (submission fails or scores poorly without it)
### 🟠 P1 — MAJOR (needed for top-10 contention)
### 🟡 P2 — MODERATE (separates good from great)
### 🟢 P3 — MINOR (polish)

Use this format for EVERY issue/decision:

### [P0/P1/P2/P3] TITLE

**Files/phases involved:** which source docs inform this
**Decision/Problem:** what must be decided or fixed in the plan
**Why it matters:** scoring/hiring impact
**Recommended approach:** the strategy
**When to act:** build-order position

---

# ==================================================
# FINAL RESPONSE STRUCTURE (mandatory)
# ==================================================

# EXECUTIVE VERDICT
Honest overall assessment in a few paragraphs.

Then, in order:

1. **P0 — MUST-HAVE FOUNDATIONS**
2. **P1 — MAJOR STRATEGY ITEMS**
3. **P2 — MODERATE**
4. **P3 — MINOR**
5. **SCORING CAPTURE MAP** (point-by-point: how we earn each of the 50 + bonuses)
6. **ARCHITECTURE RECOMMENDATION & RATIONALE**
7. **COMPOSER & CONVERSATION DESIGN DECISIONS**
8. **RISK REGISTER** (top risks with mitigations)
9. **EVALUATION PLAN**
10. **BUILD ORDER / TIMELINE**
11. **JUDGE & HIRING-SIGNAL MOVES**
12. **WHAT NOT TO BUILD** (over-engineering traps to avoid)
13. **EXACT PRIORITY ORDER** (numbered: do this first, then this…)
14. **FINAL VERDICT** — one of:
    * ✅ STRATEGY CLEAR — START BUILDING
    * ⚠️ MOSTLY CLEAR — RESOLVE THESE DECISIONS FIRST
    * ❌ MAJOR GAPS — RETHINK REQUIRED

Close with three scores:

**Challenge Understanding:** XX/100
**Win-Probability Assessment:** XX/100
**Plan Actionability:** XX/100

---

# 🚨 FINAL REMINDER

I am NOT asking you to write code.
I am NOT asking you to build the bot.
I am NOT asking you to create any files.
I am asking for a **deep strategic plan only**:

> **WHAT MATTERS → WHY IT MATTERS → HOW WE'LL HANDLE IT → WHEN IN THE BUILD ORDER**

Ground every claim in the provided files. Quote the briefs, case studies, and simulator behavior as evidence. Be brutally honest. If something in the package looks like a trap, say so loudly.
