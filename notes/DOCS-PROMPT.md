# MASTER DOCUMENTATION PROMPT — Generate All 8 Project Docs for Our magicpin AI Challenge Bot

You are an elite documentation team (Principal Architect + Senior AI Engineer + Product Manager + Hackathon Strategist). Your job: **produce the complete, implementation-ready documentation suite for OUR submission to the magicpin AI Challenge** — the "Vera" merchant-AI message-engine competition.

You will create **exactly 8 Markdown files**, mirroring the numbering convention of a reference documentation package (`1. PRD.md` … `8. Rules.md`) whose *structure* you should emulate (numbered sections, dense tables, ASCII diagrams, FR tables, ADR-style tradeoffs, checklists, honesty records):

```
1. PRD.md                  # Product Requirements
2. TechSpec.md             # Technical Architecture & Contracts
3. AppFlow.md              # Every runtime flow, state machine, edge cases
4. Design.md               # Message/conversation design system (NO web UI exists)
5. Schema.md               # Data model: stores, registries, schemas, enums
6. ImplementationPlan.md   # Phased build plan with hours, deps, critical path
7. Tracker.md              # 1:1 task tracker mirroring the plan
8. Rules.md                # Hard constraints for devs + AI coding agents
```

---

# 🚨 CRITICAL INSTRUCTIONS

1. **Produce ONLY these 8 Markdown documents.** No code files, no scripts, no modifications to source files.
2. **Every document must describe the SAME product** (see Consistency Constants below). Zero contradictions between files.
3. **Ground everything in the official challenge package.** Source-of-truth hierarchy: (a) the provided magicpin files (`guidelines.md`, `challenge-brief.md`, `challenge-testing-brief.md`, `examples/api-call-examples.md`, `examples/case-studies.md`, `dataset/*`, `judge_simulator.py`), (b) the locked decisions restated below, (c) anything else you add — which must be explicitly flagged as `[ASSUMPTION]`.
4. **Do NOT plagiarize the challenge's case studies.** Example messages you write must be original in wording while matching the documented shape.
5. Be brutally honest in the docs (the reference package includes honesty records — keep that culture). Never overstate; include a "Known Limitations / Not Yet Done" section where appropriate.
6. Write for two audiences simultaneously: the developers/AI agents who will implement from these docs, and hackathon judges/hiring reviewers who will read them.

---

# ==================================================
# PART A — THE PROJECT (what the docs must describe)
# ==================================================

## A.1 Challenge context (fixed facts)

* **Organizer:** magicpin (~100k merchants, 50+ Indian cities). Their production assistant **Vera** talks to merchants on WhatsApp. Known Vera weaknesses we exploit: auto-reply pollution, intent-handoff failures, generic copy, low engagement frequency.
* **Our deliverable:** ONE public bot URL exposing `GET /v1/healthz`, `GET /v1/metadata`, `POST /v1/context`, `POST /v1/tick`, `POST /v1/reply` (+ optional `POST /v1/teardown`). Judge harness drives everything; there is **no human-facing web UI**.
* **Core function:** deterministic `compose(category, merchant, trigger, customer?) → {body, cta, send_as, suppression_key, rationale}`.
* **The 4 input contexts:** CategoryContext (voice/taboos/offer_catalog/peer_stats/digest/patient_content_library/seasonal_beats/trend_signals/professional_journals/regulatory_authorities), MerchantContext (identity/subscription/performance+7d deltas/offers/conversation_history/customer_aggregate/signals), TriggerContext (15 kinds, external/internal, urgency 1–5, suppression_key, expires_at), CustomerContext (optional; relationship/state new→active→lapsed_soft→lapsed_hard→churned/preferences/consent.scope).
* **Hard limits:** 30s max per call · 10 req/s from judge · 500 KB context payloads · ≤20 actions/tick · 60 simulated minutes window · ticks every 5 sim-minutes · conversations ≤5 turns · healthz polled every 60s, **3 consecutive failures = disqualified** · `/v1/context` idempotent on `(scope, context_id, version)`; higher version replaces atomically; same version = no-op; stale = 409 `stale_version`; malformed = 400.
* **Reply contract:** respond to `/v1/reply` within 30s with exactly one of `send` / `wait` (+`wait_seconds`) / `end` (+rationale).
* **Dataset:** `generate_dataset.py --seed-dir dataset --out expanded` ⇒ 50 merchants · 200 customers · 100 triggers · 30 canonical test pairs. Same seed (20260426) for everyone.
* **Testing lifecycle:** Warmup (255 base contexts pushed, counts verified) → 60-min window with adaptive injections (new digests, shifted metrics, ~15 new triggers, surprise customer scopes) → Replay stage (**top-10 bots only**: auto-reply hell / intent transition / hostile-off-topic, 5 turns each) → score report with per-message rationale.

## A.2 Scoring map (docs must treat points as requirements)

| Source | Points | Notes |
|---|---|---|
| Per message: Specificity · Decision Quality · Category Fit · Merchant Fit · Engagement Compulsion | **5 × /10 = /50** | Hallucinated/unverifiable facts ⇒ cap **5/dim**; research claim without citation ⇒ Specificity cap **7** |
| Adaptive-context incorporation | **up to +5/dim (≈+25/msg)** | Must visibly USE freshly injected context |
| Replay conversations (top-10 gate) | **up to +30** | Auto-reply detect → flag-once → wait → end; intent ⇒ instant action mode; hostile ⇒ graceful exit |
| Penalties | down to **−20 total** | healthz −10 · tick/reply timeout −1 · malformed/empty-body/verbatim-repeat −2 · **URL in body −3 (hard fail)** |

Simulator verdict bands: ≥80% EXCELLENT (our release gate) · ≥60% GOOD · ≥40% NEEDS IMPROVEMENT. Local gate: all `judge_simulator.py` scenarios (`warmup`, `phase2_short`, `auto_reply_hell`, `intent_transition`, `hostile`, `full_evaluation`) plus a smoke-test replaying EVERY example in `examples/api-call-examples.md`.

## A.3 LOCKED architecture decisions (do not relitigate — document them)

1. **Hybrid composer:** LLM core inside deterministic guardrails. Router (`trigger.kind × scope` → one of ~15 prompt variants) → system-prompt assembly (voice profile, language, CTA policy) → LLM call (temperature=0, top_p=1, **hard 25s timeout**) → **13-check validation gate** → response cache keyed by hash of (all four context ids + versions + language) → fallback template on failure.
2. **Facts registry + grounding:** before composing, extract every verifiable token (numbers, dates, citations incl. `professional_journals`/`regulatory_authorities` names, offer prices, names, localities) from CURRENT context versions; post-generation, every number/date/citation/name in output must trace to it; miss ⇒ re-prompt once ⇒ fallback template. Computed numbers (e.g., lapsed-cohort counts from `customer_aggregate`) are pre-computed deterministically and registered.
3. **Validation gate order:** URL scan → facts membership → single CTA → CTA-in-last-sentence → CTA-policy-by-trigger-kind (binary for action triggers; slot-choice only for booking triggers; open-ended/none for pure-info) → taboo-word scan → domain-vocab presence → language match → owner-first-name greeting → ≥4–5 verifiable facts woven around one spine signal → body-hash anti-repetition → similarity-vs-case-studies (<0.6) → rationale-facts ⊆ body-facts.
4. **Tick budget math:** serial LLM composition cannot fit 30s×20 actions ⇒ rank available triggers (`urgency × freshness × suppression-status`), compose **top 3–5 in parallel** (async), cache-first; return `{"actions": []}` freely — restraint rewarded.
5. **Three-tier degradation:** primary frontier model → secondary fast model on a DIFFERENT provider → deterministic fallback templates per `(trigger.kind, scope, category.slug)`. The bot must NEVER go silent because the LLM is down.
6. **Reply brain:** heuristic classifier → `{accept, question, objection, auto_reply, explicit_intent, hostile, off_topic}` → state machine. Auto-reply = verbatim 3× OR signature phrases; explicit_intent ("let's do it", "kar do", "mujhe karna hai") ⇒ action mode immediately (NEVER another qualifying question); hostile ⇒ polite end; off-topic ⇒ decline + redirect.
7. **State model:** in-memory stores (context store keyed `(scope, context_id)` with monotonic versions; conversation store; 3 dedup registries: suppression keys per merchant, body-hash per conversation, topic-set per merchant; fresh-context registry marking entities with unseen versions; response cache; LLM/spend ledger). **Composer always reads current version at call time — never snapshots context into conversation state.** Persist snapshot to disk every 30s (atomic temp-file+rename); recover on startup; healthz counts ALWAYS derived from the live store, never static counters.
8. **Ops posture:** persistent-process hosting (Render/Fly/Railway — never serverless/cold-start), external uptime monitor, bounded `wait_seconds` (1800–3600, never 86400), spend ceiling $25 with soft alert at $20 then fallback-only mode, consent-scope check before any customer-facing send, `expires_at` filter on triggers, urgency→CTA-strength mapping, turn-budget management (wind down by turn 3–4 of 5).
9. **Explicit non-goals (document why):** no vector/RAG over the small dataset, no agentic planner-executor loops, no fine-tuning, no custom dashboard UI, no real database, no multi-LLM ensemble voting, no scraping real magicpin/Google data, no per-merchant voice tuning beyond vertical profiles.

---

# ==================================================
# PART B — REQUIRED CONTENT PER FILE
# ==================================================

Each file below lists its required section skeleton. Keep Reflex-style numbered `##` sections, tables everywhere, ASCII diagrams where useful. Adapt length: deep where it prevents implementation ambiguity, brief where obvious.

### `1. PRD.md`
Product Overview · Executive Summary · Problem Statement (production Vera's 4 weaknesses + why merchants disengage) · Why Now · Why This Challenge Fits Us · Target Users (merchant personas across 5 verticals; merchant's customers; the judge harness as primary system user) · Core User Jobs · Value Proposition · Core User Journey (a Dr. Meera-style narrative: context pushed → digest nudge → engaged reply → drafted patient-ed follow-up) · Product Goals (score targets: ≥80% simulator band, top-10 contention, zero operational penalties) · Non-Goals (from Locked Decision 9, with reasons) · MVP Scope · **Feature Requirements table (FR-01…FR-nn)** — columns: ID · Requirement · Priority P0–P3 · Score impact (points protected/earned) · Acceptance signal · AI Requirements · Agentic Requirements (**justify why deliberately non-agentic**) · Business Metrics (= scoring map operationalized) · Security & Trust Requirements (privacy §23 compliance) · Failure Handling overview · User Stories written from the JUDGE HARNESS perspective ("As the harness, when I push a v3 category mid-conversation, the next composition must cite a v3 fact") · Acceptance Criteria (release gate = full pre-flight checklist) · Future Expansion · Honesty section (known limitations template).

### `2. TechSpec.md`
System Overview · **ASCII Architecture Diagram** (HTTP layer → stores/registries → composer pipeline → validation gate → caches/fallbacks → reply brain) · Technology Stack (Python 3.11+/FastAPI/Pydantic v2/httpx async; LLM SDKs; hosting choice + why not serverless) · Repository Structure (proposed tree) · Backend Architecture: full request/response JSON contracts for ALL 6 endpoints including 200/409/400 paths, payload-size guard, teardown wipe · **AI Architecture subsections:** AI-1 Router + prompt variants (include the full 15-kind routing table: kind × scope → variant, CTA policy, compulsion levers, required signals), AI-2 Facts Registry & Validation Gate (13 checks in enforced order), AI-3 Reply Classifier (pattern table incl. Hindi/Hinglish signatures), AI-4 Model Strategy (primary/secondary/templates, temperature=0, cache, token budgets) · Agent Architecture (ADR: rejected, reasons) · Data Flow happy path (sequence: warmup → push → tick → rank → compose → validate → act → reply → classify → send/wait/end) · External Integrations (LLM providers only; containment rule) · Security Architecture · Failure Modes matrix (trigger → detection → automatic response → point impact avoided) · Observability (structured logs, rejection-rate metric, spend meter, conversation transcript dump) · Testing Strategy (simulator scenarios, synthetic injections using alternate generator seeds, adversarial replay scripts mirroring Phase 4 exactly, determinism byte-equality tests, examples smoke gate as HARD gate) · Deployment Architecture · Performance Targets (tick p99 <25s, context push <100ms, warmup 255 pushes <5s) · Cost Considerations ($25 ceiling mechanics) · **Technical Tradeoffs as ADR-01…ADR-nn** (hybrid vs pure-LLM vs pure-template vs agentic; caching for determinism; top-K selection; in-memory+persistence vs DB).

### `3. AppFlow.md`
Global Application Flow · Warmup Flow (exact ordering, settle wait, count verification, failure ⇒ what we do) · Context Push Flow (version-compare decision tree incl. 409/400/oversize; atomic replace; fresh-context marking) · **Tick Decision Flow** (filter expired triggers → suppression/topic/wait-state checks → signal selection & scoring → top-K ranking → parallel composition → validation → assembly of actions[] ≤20) · Composer Pipeline Flow · Reply Handling Flow (classify → arc per class) · **Replay Scenario Flows as exact turn-by-turn sequences** (auto-reply hell: attempt→flag→wait→end; intent transition: qualifying→action-mode sample; hostile & off-topic) · Success definition · Failure Flows (LLM slow/down ⇒ secondary ⇒ template; quota hit ⇒ fallback-only mode; host restart ⇒ disk recovery) · Edge Cases table (unseen merchant mid-conversation; language switch; expired trigger; wait expiry re-engage; 5-turn cap wind-down; duplicate context push; unknown scope) · State Machines (conversation lifecycle: NEW→ACTIVE→{WAITING|ENDED}; classifier transitions) · Endpoint Map (instead of screen map) · **Flow Verification Matrix** — every flow row mapped to the specific test (simulator scenario / smoke example / synthetic test) that proves it.

### `4. Design.md`
*(No web UI exists — this is the MESSAGE & CONVERSATION design system. Say so explicitly in §1.)*
Design Philosophy ("peer, not promoter"; grounded-only; restraint) · **Message Anatomy** (hook → fact spine → compulsion lever → single CTA in final sentence; length guidance) · **Per-vertical Voice Profiles table** (tone, allowed vocab, taboo vocab, citation sources — dentists clinical-peer/"cure"/"guaranteed"/JIDA-DCI; salons warm-visual; restaurants operator ("covers","AOV"); gyms no-shame coach; pharmacies molecule-precise) · Language System (en / hi / hi-en mix code-switching rules; senior-citizen register) · Emoji & Formatting Policy (sparse, category-appropriate) · First-touch WhatsApp template structures with `{{1}}/{{2}}` params · Compulsion Lever Playbook (8 levers; social proof + asking-the-merchant prioritized as Vera's documented gaps) · Judgment/contrarian-calls policy (when data supports, e.g., event-day reframes; must cite anchor) · Conversation Tone Arcs (greeting → engage → deliver → next-best-step → wind-down → exit wording patterns incl. polite Hindi exits) · Rationale Writing Standard (2–3 sentences; must mirror body facts) · Degradation UX (fallback-template minimum quality bar so degraded ≠ garbage) · Operational Console design (log line formats, transcript export) · Complete **Message Inventory** — one original example shape per trigger kind (15), each annotated with facts used · State coverage from the reader's side (engaged / auto-replied / hostile / waiting / ended).

### `5. Schema.md`
Data Architecture (in-memory first; optional single SQLite/file snapshot for restart recovery — justify) · Store Diagram · **Entities (full field tables with types):** ContextRecord `(scope, context_id, version, payload, received_at)` · ConversationState `(conversation_id, merchant_id, customer_id, send_as, language, turns[], topics_sent, body_hashes, last_merchant_reply_at, ended, ended_reason, wait_until, nudge_count)` · SuppressionRegistry · BodyHashRegistry · TopicRegistry · FreshContextRegistry · FactsRegistryEntry · ResponseCacheEntry · LLMCallLog (prompt hash, tokens, cost, latency) · SnapshotFile format · Relationships & integrity invariants (version monotonicity per key; healthz counts ⇔ store contents; ended conversations immutable; cache keys include all four context versions) · **Enums:** scope · send_as (`vera`|`merchant_on_behalf`) · cta (`open_ended`|`binary_yes_no`|`binary_confirm_cancel`|`multi_choice_slot`|`none`) · customer_state (5) · trigger_kind (15) · classification (7) · bot_action (`send`|`wait`|`end`) · Validation Rules per entity · Data Lifecycle & Privacy (teardown wipes everything; retention = test duration only) · Seed/Demo Data loading from `expanded/` · Deliberate omissions (why no users/payments/multi-tenant tables).

### `6. ImplementationPlan.md`
Phase 0 Setup → Phase 1 Foundation (skeleton endpoints, context store, healthz-from-store, dataset load + count verification) → Phase 2 Deterministic layer (fallback templates per kind×scope×category; facts registry) → Phase 3 Validation gate (13 checks) → Phase 4 LLM composer + router + cache + three-tier fallback → Phase 5 Tick orchestration (top-K, parallelism, restraint, suppression registries, 24h session tracking) → Phase 6 Reply brain + replay-scenario tests → Phase 7 Evaluation loop (simulator to ≥80%, synthetic injection harness, plagiarism checker) → Phase 8 Hardening (persistence+recovery, payload guards, spend ceiling, error paths) → Phase 9 Deploy/monitor/README/metadata/submit + keep-live plan. For EACH phase: goal · task list · dependencies · hour estimate · **exit criteria (verifiable)**. Include: Parallel Workstreams (solo & 2-person variants) · **Critical Path** · **MVP Cut Line** (never-cut list: validation gate, fallback templates, healthz-from-store, atomic context store, suppression registries, URL scan, schema conformance) · Cut-order decision table for time pressure (what to drop 1st…11th, with score impact) · Total hours (~48h full / ~30h solo-cut) · Submission-Day Runbook (deploy → smoke gate → simulator → submit → monitoring handoff).

### `7. Tracker.md`
Mirror ImplementationPlan **1:1** — every task appears as `- [ ] Task — owner — est — depends — status(⬜/🟨/✅)`. Then project-level checklists, all initially unchecked: Definition of Done · Pre-Submission Gate (every api-call-examples.md example passes; simulator ≥80% EXCELLENT; determinism test green; adversarial replays green; plagiarism check green; healthz counts verified post-warmup; public-URL curl sweep; README+metadata done; external monitor on; quota verified) · Security & Privacy Checklist · AI Evaluation Checklist · GitHub Repo Readiness (clean history, README, no secrets committed) · Final Submission Checklist (portal URL, bot kept live ≥7 days, contact email monitored).

### `8. Rules.md`
Hard constraints phrased as enforceable rules for developers AND AI coding agents, grouped like the reference: Determinism Rules (temp=0; no RNG; canonical ordering; cache-first; byte-equality regression test) · Grounding Rules (facts registry mandatory; untraceable number ⇒ reject; computed numbers pre-registered) · Message Safety Rules (NO URLs ever; single CTA last sentence; vertical taboos; language match; owner-name greeting; no verbatim repeats; no case-study wording ≥0.6 similarity) · Contract Rules (Pydantic-validate every outbound response; ≤20 actions; all fields present even when nullable; `customer_id:null` not omitted) · Latency Budget Rules (LLM ≤25s, classifier ≤10s, tick total ≤28s hard; never block `/v1/context` on LLM work) · State Rules (read current context at call time; never snapshot into conversations; ended = immutable; wait_seconds ∈ {900..3600}) · Privacy & Security Rules (payloads only to configured LLM APIs; nothing else leaves; secrets via env vars only; teardown wipes; no scraping real platforms) · Cost Rules (spend meter on; $20 soft-alert; $25 hard fallback-only switch) · Testing Rules (run simulator after ANY prompt/router change; keep examples-smoke green) · Git Rules (feature branches, meaningful commits, no secrets in history) · Demo/Submission Integrity — ZERO TOLERANCE (no fabricated results in README; degraded mode disclosed honestly; submitted URL = tested URL) · **DO-NOT list** (no RAG/embeddings, no agent loops, no serverless, no database server, no UI, no ensembles, no scraping, no per-merchant tuning, no cadence RL, no custom judge) · Enforcement map (which rule is checked by which automated test/gate).

---

# ==================================================
# PART C — CONSISTENCY CONSTANTS (must be identical in every file)
# ==================================================

At the top of your working memory, fix these and reuse verbatim:

* **PRODUCT_NAME:** choose ONE distinct name for our engine now (suggest something like "Sutra", "Disha", "Setu" — NOT plain "Vera"; Vera is magicpin's product). Use it in every title and sentence.
* **TEAM:** `[TEAM_NAME]` placeholder, members `[MEMBER_1]`, `[MEMBER_2]`.
* **ARCHITECTURE_ONE_LINER:** "Hybrid deterministic-guardrail composer: routed LLM core + facts-registry validation gate + three-tier fallback + reply state machine."
* **ENDPOINTS:** the 6 routes listed above. **LIMITS:** 30s / 10rps / 500KB / 20 actions / 60min / 5 turns / 3-strike healthz. **SCORES:** 5×10 base, +5/dim adaptation, +30 replay, −20 penalty floor.
* **MODELS:** Primary frontier model, Secondary fast model on a different provider, Tertiary deterministic templates.
* Any number appearing in multiple docs must match exactly. After writing all 8 files, run a silent self-audit for contradictions and fix before finishing.

---

# ✅ OUTPUT FORMAT

Write the 8 files in order 1 → 8. Each file starts with `# <DocType> — <PRODUCT_NAME>` and a one-line status footer (`Status: Draft v1.0 — pre-implementation`). Use Markdown headers, tables, fenced JSON/ASCII blocks. No apologies, no meta-commentary between files — just the documents. End with a short `---` separated **Consistency Self-Check** confirming: same product name everywhere · endpoint list identical · limits identical · scoring identical · Tracker ↔ Plan 1:1 · no case-study text copied.
