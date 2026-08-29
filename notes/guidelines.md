# magicpin AI Challenge — Complete Guidelines (A to Z)

> **Vera by magicpin · India's Biggest AI Challenge**
> *No Resume | No Interview | No Experience Required*
> Take the AI Challenge & apply to build **India's Largest Retailer AI — VERA**.
>
> This document consolidates the entire official challenge package into one readable guide. Everything here comes directly from the challenge page and the starter zip (`challenge-brief.md`, `challenge-testing-brief.md`, `engagement-design.md`, `engagement-research.md`, `examples/`, `dataset/`, `judge_simulator.py`). Nothing is invented.

---

## Table of Contents

1. [The Challenge at a Glance](#1-the-challenge-at-a-glance)
2. [Background — About magicpin](#2-background--about-magicpin)
3. [About Vera (What You Are Rebuilding)](#3-about-vera-what-you-are-rebuilding)
4. [The Task — Build the Message Engine](#4-the-task--build-the-message-engine)
5. [The 4-Context Framework (Deep Dive)](#5-the-4-context-framework-deep-dive)
6. [Composition Rules & Hard Constraints](#6-composition-rules--hard-constraints)
7. [The Dataset](#7-the-dataset)
8. [What You Submit](#8-what-you-submit)
9. [The API Contract — 5 Endpoints](#9-the-api-contract--5-endpoints)
10. [How Testing Works — The Full Lifecycle](#10-how-testing-works--the-full-lifecycle)
11. [Limits, Timeouts & Rate Caps](#11-limits-timeouts--rate-caps)
12. [Scoring — The 5 Rubric Dimensions](#12-scoring--the-5-rubric-dimensions)
13. [Message Craft — What Wins and What Loses](#13-message-craft--what-wins-and-what-loses)
14. [Compulsion Levers](#14-compulsion-levers)
15. [Anti-Patterns the Judge Penalizes](#15-anti-patterns-the-judge-penalizes)
16. [Real Vera Conversation Patterns (Reference)](#16-real-vera-conversation-patterns-reference)
17. [Case Studies — 10 Judge-Scored Anchors](#17-case-studies--10-judge-scored-anchors)
18. [Cross-Case Patterns That Score 9–10/10](#18-cross-case-patterns-that-score-91010)
19. [Local Self-Test — judge_simulator.py](#19-local-self-test--judge_simulatorpy)
20. [Reference Implementation Skeleton](#20-reference-implementation-skeleton)
21. [Deployment Options](#21-deployment-options)
22. [Failure Modes & Penalties](#22-failure-modes--penalties)
23. [Security, Privacy & Ethics Rules](#23-security-privacy--ethics-rules)
24. [How Submission Works — 4 Steps](#24-how-submission-works--4-steps)
25. [Pre-Flight Checklist Before You Submit](#25-pre-flight-checklist-before-you-submit)
26. [Suggested Approach & Open Challenges (Extra Credit)](#26-suggested-approach--open-challenges-extra-credit)
27. [FAQ — Straight Answers](#27-faq--straight-answers)
28. [Appendix A — Worked Composition Examples](#appendix-a--worked-composition-examples)
29. [Appendix B — Package File Map & Quick Curl Reference](#appendix-b--package-file-map--quick-curl-reference)

---

## 1. The Challenge at a Glance

| Item | Detail |
|---|---|
| **Challenge** | Build the message engine behind **Vera**, magicpin's AI assistant for merchant growth |
| **Core deliverable** | A **deterministic `compose(category, merchant, trigger, customer?)` function** exposed as a hosted HTTP bot |
| **Bot returns** | Next message, CTA, send-as identity, suppression key, and rationale |
| **Submission** | **One public bot URL** — the judge calls your endpoints |
| **Judging** | LLM-powered (`judge_simulator v1.0.0`) · 30 canonical test pairs · 30s timeout · 20 actions/tick |
| **Scored on** | 5 dimensions, each 0–10 (Decision quality, Specificity, Category fit, Merchant fit, Engagement compulsion) |
| **Key rule** | Your output must stay **deterministic** for the same input and simulator settings |
| **Status** | Submissions **OPEN NOW** — submit anytime |
| **What it leads to** | A full-time offer — or an internship that can convert into a full-time offer |

**The one-sentence version (from the official brief):**

> Build an AI chatbot that engages and assists merchants on WhatsApp the way **Vera** (magicpin's merchant-AI assistant) does — but better. Same base dataset for every participant. AI judges the outcome.

**What strong entries do:** Use merchant context to decide what Vera should say next. Make every message specific, useful, and easy to reply to.

---

## 2. Background — About magicpin

magicpin is one of India's largest local-commerce platforms — a network of **~100,000 merchant partners across 50+ Indian cities** (restaurants, salons, gyms, dentists, retailers, car dealers, etc.).

- Customers discover merchants on the magicpin app/web, transact, and earn cashback.
- Merchants benefit from visibility, walk-ins, and online orders.
- magicpin runs a marketing-assistant product called **Vera** that talks to merchants over WhatsApp, helps them grow their Google Business Profile (GBP), runs campaigns for them, and answers customer questions on their behalf. **Vera is the product you're rebuilding.**

---

## 3. About Vera (What You Are Rebuilding)

### What Vera does today

- Talks to **~6,000–10,000 merchants per day** over WhatsApp
- Helps them improve their Google Business Profile (photos, hours, posts, reviews)
- Runs marketing campaigns for them (festival, news, local events)
- Recommends pricing, offers, and content
- Answers customers' questions about merchants on their behalf

### Live engagement shape (real numbers — Apr 23–25, 2026)

| Metric | Apr 23 | Apr 24 | Apr 25 |
|---|---:|---:|---:|
| Merchants who engaged with Vera | 6,917 | 10,158 | 5,181 |
| Total messages mx ↔ Vera | 34,022 | 47,651 | 23,712 |
| Avg messages per engaged merchant | 4.9 | 4.7 | 4.6 |
| Customers who engaged with Vera | 720 | 707 | 681 |
| Unique merchants customers asked about | 580 | 514 | 466 |
| Total messages cx ↔ Vera | 3,713 | 4,839 | 4,695 |
| Avg messages per customer | 5.2 | 6.8 | 6.9 |

### Today's biggest pain points (= your opportunities to outperform Vera)

1. **Auto-reply pollution** — 40–70% of "merchant replies" are the merchant's own WhatsApp Business canned auto-reply ("Thank you for contacting…"). Production Vera detects this but burns 2–3 turns each time. **Better detection + faster routing wins.**
2. **Intent-handoff failures** — When a merchant says "I want to join," production Vera often goes back to qualifying questions instead of starting the action. **Better intent detection wins.**
3. **Generic copy** — Discount-style offers ("10% off") rarely engage Indian merchants. Service+price ("Haircut @ ₹99", "Dental Cleaning @ ₹299") works better. **Compelling, category-correct copy wins.**
4. **Low engagement frequency** — Functional nudges (renewal due, profile incomplete) are inherently rare. To engage merchants 3–5×/week needs *curiosity-driven* and *knowledge-driven* conversations, not just reminder-style. **Diversified conversation portfolio wins.**

---

## 4. The Task — Build the Message Engine

### What Vera is

Vera is magicpin's AI assistant for merchant growth. It helps merchants improve listings, run campaigns, and reply faster.

### What you build

Build a **deterministic `compose(category, merchant, trigger, customer?)` function**. It should return:

- the next **message**,
- the **CTA**,
- the **send-as identity**,
- the **suppression key**, and
- the **rationale**.

Formal signature (from the brief):

```python
def compose(
    category: dict,      # CategoryContext — how to talk to this type of business
    merchant: dict,      # MerchantContext — this specific business's current state
    trigger: dict,       # TriggerContext  — why this message should go NOW
    customer: dict | None  # CustomerContext — optional, for direct outreach
) -> dict:
    """
    Returns a dict with keys:
        body              — the WhatsApp message body
        cta               — the call-to-action
        send_as           — "vera" (merchant-facing) or "merchant_on_behalf" (customer-facing)
        suppression_key   — for dedup
        rationale         — short explanation of why this message, what it should achieve

    Inputs are plain dicts loaded from the dataset JSON.
    Free to use any LLM, any prompting strategy, any retrieval.
    MUST be deterministic given the same inputs (set temperature=0 if using LLMs).
    Must complete in < 30s per call.
    """
```

Every message must be composed from **four context layers**. Your bot receives these as structured input and must produce the next message.

| # | Context | The question it answers |
|---|---|---|
| 01 | **Category** | The right tone, offer patterns, seasonal moments, and what to avoid |
| 02 | **Merchant** | Business identity, performance signals, live offers, and conversation history |
| 03 | **Trigger** | Why this message should go now: recall, spike, dip, research, or festival |
| 04 | **Customer** | Optional context for direct outreach: relationship, consent, status, and preference |

---

## 5. The 4-Context Framework (Deep Dive)

### 5.1 CategoryContext — slow-changing knowledge pack

Knowledge about *the kind of business this is*. Shared across all merchants in the vertical. Refresh cadence: weekly (digest), monthly (voice/catalog).

| Field | Meaning |
|---|---|
| `slug` | e.g., `"dentists"` — one of 5 verticals: dentists, salons, restaurants, gyms, pharmacies |
| `offer_catalog` | Canonical service+price patterns for this vertical (e.g., `"Dental Cleaning @ ₹299"`) |
| `voice` | Tone, allowed vocabulary, taboos |
| `peer_stats` | Benchmarks: avg rating, avg reviews, typical CTR |
| `digest` | Weekly research / compliance / trend items, source-cited |
| `patient_content_library` | Content items the merchant can reshare with their customers |
| `seasonal_beats` | e.g., *"exam-stress bruxism spikes Nov-Feb"* |
| `trend_signals` | e.g., *"clear aligners Delhi searches +62% YoY"* |

> **In the actual dataset files**, each category JSON additionally carries `display_name`, `professional_journals` (e.g., JIDA for dentists), and `regulatory_authorities` (e.g., DCI) — plus ~5 digest items, ~8 catalog offers, seasonal beats, trend signals, and a patient content library per vertical. Load them and use what's there.

**Example — `dentists`:**
- voice: technical terms welcome ("fluoride varnish at 3-month recall"), legal taboos ("cure", "guaranteed"), peer tone not hype
- offer_catalog: `["Dental Cleaning @ ₹299", "Free Consultation", "Teeth Whitening @ ₹1,499"]`
- peer_stats: `{avg_rating: 4.4, avg_reviews: 62, avg_ctr: 0.030}` (South Delhi solo practices)
- digest: this week's items from JIDA / DCI / Dental Tribune India / IDA Delhi calendar
- seasonal_beats: `[{month: "Nov-Feb", note: "exam-stress bruxism spike"}, {month: "Oct-Dec", note: "wedding whitening peak"}]`

### 5.2 MerchantContext — the specific business's current state

Refreshed daily for performance, real-time for conversation history.

| Field | Meaning |
|---|---|
| `identity` | Name, place_id, locality, city, verified flag, languages, owner first name |
| `subscription` | Status (active/expired/trial), days remaining, plan |
| `performance` | Views/calls/CTR/directions over 30d window + 7-day deltas |
| `offers` | Active + paused/expired offers from their catalog |
| `conversation_history` | Last N turns with Vera, with engagement tags (replied, ignored, unsubscribed-from-topic) |
| `customer_aggregate` | Active count, lapsed count, retention % (aggregates only — never individual customers) |
| `signals` | Derived flags: `"stale_posts"`, `"ctr_below_peer_median"`, `"dormant_with_vera"`, … |

**Running example — Dr. Meera's Dental Clinic:**
- identity: name="Dr. Meera's Dental Clinic", city="Delhi", locality="Lajpat Nagar", verified=true
- subscription: status="active", days_remaining=82, plan="Pro"
- performance (30d): views=2,410, calls=18, directions=45, ctr=0.021
- offers: `["Dental Cleaning @ ₹299"]` active; `["Deep Cleaning @ ₹499"]` expired 2 months ago
- customer_aggregate: 540 unique patients YTD, 78 lapsed >180 days, 38% 6-month retention
- signals: `["stale_posts" (last post 22d ago), "ctr_below_peer_median" (peer median 0.030)]`

### 5.3 TriggerContext — why this message goes right now

Every message must have one trigger. Two families:

**External triggers** (happen outside the merchant's account):
- `festival_upcoming` (Diwali in 4 days)
- `weather_heatwave` (42°C today in Delhi)
- `local_news_event` (Mumbai-Pune expressway closed 3h)
- `category_research_digest_release` (JIDA Oct issue dropped)
- `regulation_change` (DCI radiograph dose limit revised)
- `competitor_opened` (new dentist 1.3 km away on GBP)
- `category_trend_movement` ("clear aligners Delhi" searches +62%)

**Internal triggers** (happen within the merchant's data):
- `perf_spike` (yesterday's views +28% vs avg)
- `perf_dip` (calls dropped 40% week-over-week)
- `milestone_reached` (crossed 100 reviews)
- `dormant_with_vera` (no merchant message in 14 days)
- `customer_lapsed_soft` (a customer's 6-month recall window opens)
- `appointment_tomorrow` (booking exists for next day)
- `review_theme_emerged` (3 reviews this week mention "wait time")
- `scheduled_recurring` (weekly Friday curious-ask cadence)

**Fields:** `id`, `scope` (merchant/customer), `kind`, `source` (external/internal), `payload` (kind-specific data), `urgency` (1–5), `suppression_key` (for dedup), `expires_at`.

**Example trigger for Dr. Meera:**

```json
{
  "id": "trg_2026_04_26_research_digest_dentists",
  "scope": "merchant",
  "kind": "research_digest",
  "source": "external",
  "payload": {
    "category": "dentists",
    "top_item": {
      "title": "3-mo fluoride recall cuts caries recurrence 38% better than 6-mo",
      "source": "JIDA Oct 2026, p.14",
      "trial_n": 2100,
      "patient_segment": "high-risk adults"
    }
  },
  "urgency": 2,
  "suppression_key": "research:dentists:2026-W17",
  "expires_at": "2026-05-03T00:00:00Z"
}
```

### 5.4 CustomerContext — optional, only for customer-facing messages

Populated when the bot sends a message *on behalf of the merchant* to one of the merchant's own customers.

| Field | Meaning |
|---|---|
| `identity` | Name, phone (redacted), language preference |
| `relationship` | First visit, last visit, total visits, services received |
| `state` | `new` \| `active` \| `lapsed_soft` (3–6 mo) \| `lapsed_hard` (6 mo+) \| `churned` (12 mo+) |
| `preferences` | Preferred time/slots, channel, derived from booking history |
| `consent` | When + how they opted in to merchant outreach, scope of consent |

**Example — Priya, a patient of Dr. Meera:**
- identity: name="Priya", phone="<redacted>", language_pref="hi-en mix"
- relationship: first_visit="2025-11-04", last_visit="2026-05-12", visits_total=4, services=["cleaning", "cleaning", "whitening", "cleaning"]
- state: "lapsed_soft" (5 months since last visit)
- preferences: weekday evening slots (derived from booking history)
- consent: opted in via merchant on 2025-11-04, scope=["recall_reminders", "appointment_reminders"]

---

## 6. Composition Rules & Hard Constraints

Your bot must respect these constraints (verbatim requirements from the brief):

1. **WhatsApp 24h session window** — the *first* outbound to a merchant or customer must use a pre-approved template (use any sensible template structure with `{{1}}/{{2}}/…` parameters; Meta won't actually be called). Subsequent messages within 24h of a merchant reply can be free-form.
2. **Body length** — no hard cap; keep it concise and context-appropriate for readability.
3. **Single primary CTA** — binary choice (YES/STOP) for action triggers; no CTA acceptable for pure-information triggers. Session rule: **one clear CTA per send, no fake claims.**
4. **URLs** — allowed when they add clear value to the merchant. *(Caution: `examples/api-call-examples.md` shows URLs in body scored as a −3 hard fail "Meta would reject" — safest to avoid URLs entirely.)*
5. **Specificity wins** — anchor on a verifiable fact the merchant can check (number, date, headline). "X% off" is generic; "Haircut @ ₹99" is specific.
6. **Voice match** — peer/colleague tone, not promotional; technical vocabulary OK if category allows.
7. **Hindi-English code-mix is fine** — and often preferred for Indian merchant audiences. Match the merchant's language.
8. **Don't fabricate** — if data isn't in the contexts, don't invent it. No fake offers, no fake research citations, no fake competitor names.

---

## 7. The Dataset

Every team starts from the same base data. The dataset is **synthetic but realistic** — generated from anonymized templates, no real PII.

### 7.1 Package structure

```
magicpin-ai-challenge/
├── challenge-brief.md            # What to build (the full product spec)
├── challenge-testing-brief.md    # How your bot is tested (HTTP contract)
├── engagement-design.md          # Design doc behind the 4-context framework
├── engagement-research.md        # Research notes on current Vera data access
├── judge_simulator.py            # Official local LLM-powered judge
├── dataset/
│   ├── categories/               # 5 verticals: dentists, salons, restaurants, gyms, pharmacies
│   │   ├── dentists.json
│   │   ├── gyms.json
│   │   ├── pharmacies.json
│   │   ├── restaurants.json
│   │   └── salons.json           # 5 fully-populated CategoryContexts
│   ├── merchants_seed.json       # 10 seed merchants (2 per category)
│   ├── customers_seed.json       # 15 seed customers
│   ├── triggers_seed.json        # 25 seed triggers
│   └── generate_dataset.py       # Deterministic expansion + 30 canonical test pairs
└── examples/
    ├── api-call-examples.md      # Exact HTTP calls the judge makes
    └── case-studies.md           # 10 judge-scored anchors
```

### 7.2 Generate the expanded dataset

Run this after extraction — **all teams use the same seed and get the same expanded base dataset** (fixed random seed `20260426`):

```bash
python3 dataset/generate_dataset.py --seed-dir dataset --out expanded
```

Output:

```
expanded/
├── categories/{slug}.json     (5 files, copied as-is)
├── merchants/m_NNN_*.json     → 50 merchants  (10 seeds + 40 generated, 10 per category)
├── customers/c_NNN_*.json     → 200 customers (seeds + generated, ~3–5 per merchant)
├── triggers/trg_NNN_*.json    → 100 triggers  (seeds + generated across all kinds)
└── test_pairs.json            → 30 canonical (merchant, trigger) pairs everyone answers
```

### 7.3 Key facts about the dataset

- Each trigger references one merchant (via `merchant_id`) and optionally one customer.
- Participants can compose any `(category, merchant, trigger)` or `(category, merchant, trigger, customer)` combination from this set.
- A canonical **submission test set of 30 specific (merchant, trigger) pairs** covers all trigger kinds (up to 2 pairs per kind). Everyone produces messages for the same 30 — this gives the AI judge a like-for-like comparison.
- Generated merchants get realistic Indian city/locality combinations (Delhi, Mumbai, Bangalore, Hyderabad, Chennai, Pune, Chandigarh, Jaipur, Lucknow, Ahmedabad), varied performance numbers, subscription statuses (active/trial/expired), and regional language lists.
- The base dataset is synthetic; merchant names are altered; phone numbers redacted.

---

## 8. What You Submit

**Per the challenge page:**

1. **Submit a public bot URL.** The judge will call `POST /v1/context`, `POST /v1/tick`, `POST /v1/reply`, `GET /v1/healthz`, and `GET /v1/metadata` on it.
2. **A one-page `README.md`** (optional but recommended) explaining your approach, model choice, and tradeoffs.

**Additionally, the brief describes these deliverables** for the judged artifacts:

| Artifact | Purpose |
|---|---|
| `bot.py` / your server code | Implements `compose(...)` and the HTTP endpoints. Any LLM, any prompting strategy, any retrieval allowed. Deterministic. <30s per call. |
| `submission.jsonl` (30 lines) | One composed message per canonical test pair: `{"test_id": "T01", "body": "...", "cta": "...", "send_as": "...", "suppression_key": "...", "rationale": "..."}` |
| `conversation_handlers.py` (optional) | Multi-turn handling: `respond(state, merchant_message) -> reply`. Multi-turn capability is a **tiebreaker, not a requirement**. |
| `README.md` (1 page max) | Approach, tradeoffs, what additional context would have helped most. |

---

## 9. The API Contract — 5 Endpoints

All endpoints are HTTPS (HTTP OK for local testing), JSON in/out, UTF-8. The judge is the source of truth; your bot is **stateful** (it must remember context pushed earlier and conversations in flight — in-memory storage is fine, just don't restart between calls).

Architecture:

```
   ┌──────────────────────────┐                    ┌────────────────────────────┐
   │  magicpin Judge Harness  │                    │  Candidate Bot (your code) │
   │  (LLM playing merchant + │ ──── HTTP/JSON ──► │  HTTP server, public URL   │
   │   context injector +     │ ◄──── HTTP/JSON ── │  Stateful per-conversation │
   │   scorer)                │                    │                            │
   └──────────────────────────┘                    └────────────────────────────┘
```

Two information flows:
1. **Judge → Bot**: pushes incremental context across all 4 dimensions over time (mimics how production data updates flow into Vera).
2. **Bot → Judge**: the bot proactively initiates conversations via `/v1/tick`, and the judge plays the merchant/customer role, replying realistically via `/v1/reply`.

### 9.1 `GET /v1/healthz` — liveness probe

Three consecutive failures disqualify the run.

```bash
$ curl -sS https://your-bot.example/v1/healthz
```

```json
{ "status": "ok",
  "uptime_seconds": 3600,
  "contexts_loaded": { "category": 5, "merchant": 50, "customer": 200, "trigger": 100 } }
```

The judge polls this every 60s during the test window. At warmup the counts start at zero; after warmup they must reflect everything pushed (5 categories + 50 merchants + 200 customers = 255 base contexts, triggers arrive during the window).

### 9.2 `GET /v1/metadata` — team identity for the leaderboard

```json
{ "team_name": "Team Alpha",
  "team_members": ["Alice", "Bob"],
  "model": "claude-opus-4-7",
  "approach": "single-prompt composer with retrieval",
  "contact_email": "team@example.com",
  "version": "1.2.0",
  "submitted_at": "2026-04-29T08:00:00Z" }
```

### 9.3 `POST /v1/context` — receive a context push (idempotent by scope + version)

Called whenever the judge wants the bot to know new/updated context — the initial base load, or incremental updates mid-test.

**Request:**

```json
{
  "scope": "merchant",                      // "category" | "merchant" | "customer" | "trigger"
  "context_id": "m_001_drmeera",
  "version": 3,
  "payload": { "identity": {}, "performance": {}, "offers": [] },
  "delivered_at": "2026-04-29T10:00:00Z"
}
```

**Behavior:**
- **Idempotent** by `(context_id, version)`. Re-posting the same version is a no-op.
- A higher `version` for the same `context_id` **replaces the prior version atomically** — the bot must then use the new version when composing.
- Persist context until the test ends.

**Response (200):**

```json
{ "accepted": true, "ack_id": "ack_abc123", "stored_at": "2026-04-29T10:00:00.123Z" }
```

**Response (409)** — you already hold a higher version:

```json
{ "accepted": false, "reason": "stale_version", "current_version": 5 }
```

**Response (400)** — malformed:

```json
{ "accepted": false, "reason": "invalid_scope", "details": "..." }
```

Payload shapes per scope mirror the four contexts in Section 5 (see `challenge-testing-brief.md` §3 and `examples/api-call-examples.md` for exact schemas).

### 9.4 `POST /v1/tick` — periodic wake-up; your bot decides what to send

Called every 5 simulated minutes during the test window. The bot inspects its stored context and decides whether anything is worth sending.

**Request:**

```json
{ "now": "2026-04-29T10:30:00Z",
  "available_triggers": ["trg_research_digest_dentists"] }
```

`available_triggers` is a hint listing trigger IDs the judge considers active right now. Use any subset — or none.

**Response — ≤ 20 actions per tick:**

```json
{
  "actions": [{
    "conversation_id": "conv_m_001_drmeera_research_W17",
    "merchant_id": "m_001_drmeera",
    "customer_id": null,
    "send_as": "vera",
    "trigger_id": "trg_research_digest_dentists",
    "template_name": "vera_research_digest_v1",
    "template_params": ["Dr. Meera", "JIDA Oct issue", "..."],
    "body": "Dr. Meera, your CTR is 2.1% vs 3.0% South Delhi peer median. You already have Dental Cleaning @ ₹299. Want me to draft a 160-char patient message around it?",
    "cta": "open_ended",
    "suppression_key": "research:dentists:2026-W17",
    "rationale": "External research digest with merchant-relevant clinical anchor..."
  }]
}
```

Rules for actions:
- `actions` MAY be empty — returning `{"actions": []}` is always valid. **Restraint is rewarded; spam is penalized.**
- To start a new conversation, generate any unique `conversation_id`. Reusing an existing ID inside `/v1/tick` is invalid — continue existing conversations through `/v1/reply`.
- Only one `action` per `(merchant_id, conversation_id)` pair per tick.
- Required fields per action: `conversation_id`, `send_as`, `trigger_id`, `cta`, `suppression_key`, `rationale` (+ ids/body). Missing required fields → action scored 0, −2 penalty.

### 9.5 `POST /v1/reply` — respond to a simulated merchant/customer message

The judge calls this when the simulated merchant (or customer) replies to your previous message. The bot must respond synchronously within 30 seconds with one of exactly three valid actions: **send**, **wait**, or **end**.

**Request:**

```json
{ "conversation_id": "conv_001",
  "merchant_id": "m_001_drmeera",
  "customer_id": null,
  "from_role": "merchant",
  "message": "Yes, send me the abstract",
  "received_at": "2026-04-29T10:45:00Z",
  "turn_number": 2 }
```

**Response — action `send`:**

```json
{ "action": "send",
  "body": "Sending now — also drafted a 90-sec patient-ed WhatsApp...",
  "cta": "open_ended",
  "rationale": "Honoring accept; adding next-best-step low-friction" }
```

**Response — action `wait`:**

```json
{ "action": "wait",
  "wait_seconds": 1800,
  "rationale": "Merchant asked for time; back off 30 min" }
```

After a wait expires, the judge calls `/v1/tick` again and the bot can re-engage.

**Response — action `end`:**

```json
{ "action": "end",
  "rationale": "Merchant said not interested; gracefully exiting conversation" }
```

After `end`, the bot must not send further messages on that `conversation_id`.

Conversations run up to **5 turns** deep, or until the bot ends them.

---

## 10. How Testing Works — The Full Lifecycle

The judge harness runs your submitted URL through five phases:

### Phase 01 — Warmup
Health and metadata checks (`healthz`, `metadata`), then base context load pushed to `/v1/context`: 5 categories + 50 merchants + 200 customers (255 contexts; triggers come later). The judge waits 60s, re-checks `/healthz`, and warmup passes only if `contexts_loaded` reflects everything pushed.

### Phase 02 — Test window
**60 simulated minutes.** Every **5 minutes**, the judge pushes updates and calls `/v1/tick`. For each action your bot returns: the judge logs it (with rationale), invokes a sub-LLM playing the merchant/customer, gets a plausible response (sometimes engaged, sometimes auto-reply, sometimes hard "no", sometimes a question), and POSTs it to `/v1/reply`. Your bot answers `send`/`wait`/`end`. Repeat up to 5 turns or until the bot ends the conversation.

### Phase 03 — Adaptive injection (interleaved during Phase 2)
Fresh facts the bot hasn't seen arrive mid-test:

- **New digest items** added to category contexts (~5 new research/compliance items per category, pushed as a new version)
- **Metric shifts** — updated performance snapshots (10 merchants get new numbers — some spikes, some dips)
- **New triggers** (~15 spread across the test window)
- **Surprise customer scopes** — for 5 specific merchants a customer context arrives mid-test, followed 2 minutes later by a `recall_due` trigger

Bots that incorporate the new context in subsequent sends score higher. Bots that ignore it (sending stale compositions) score lower. **Bots that hallucinate (invent context that wasn't pushed) score lowest.**

### Phase 04 — Replay test (top 10 bots only)
Auto-replies, intent transitions, and hostile/off-topic scenarios as standalone 5-turn replays, each scored on conversation flow:

1. **Auto-reply hell** — the judge sends the same canned WA-Business auto-reply 4 times in a row. The bot must detect it and exit gracefully (good sequence: one explicit prompt → wait 24h → end).
2. **Intent transition** — after 2 qualification turns the judge says "ok let's do it." The bot must switch from qualifying to acting immediately — asking another qualifying question loses points.
3. **Hostile / off-topic** — abuse, then an unrelated ask ("can you also help me file my GST?"). The bot must stay on-mission politely (decline out-of-scope, redirect to the thread) or end gracefully.

### Phase 05 — Score report
Judge aggregates: Phase 2 scores (5-dimension rubric), Phase 3 adaptation bonus (max +5 per dimension), Phase 4 replay scores (top 10 only; max +30), operational penalties (timeouts, healthz failures, malformed responses; max −20). Teams receive **message scores, logs, transcripts, a visual timeline, and judge rationale** — a per-team artifact bundle within 48h:

```
results/<team_name>/
├── conversations.jsonl      # all turns, both sides, with timestamps
├── context_pushes.jsonl     # every context push, with bot's ack
├── scoring.json             # 5-dimension scores per action + per conversation
├── timeline.html            # visual timeline of the test window
├── replay_*.jsonl           # phase 4 replay transcripts (top 10 only)
└── final_report.md          # aggregated score + judge's qualitative feedback
```

Top scorers' bundles (with consent) become reference material for the next cohort.

---

## 11. Limits, Timeouts & Rate Caps

| Limit | Value |
|---|---|
| Max requests/sec from judge to bot | **10** |
| Max response timeout (per call) | **30 seconds** |
| `/v1/context` payload size cap | **500 KB** |
| `/v1/tick` action count cap | **20 actions per tick** |
| Healthz failures before disqualification | **3 consecutive** |
| Conversation depth | Up to 5 turns |
| Total test window | 60 simulated minutes (real time ~30–45 min) |

**If your bot needs more than 30s for `/v1/tick`:** return `{"actions": []}` immediately and process work asynchronously — but there is no catch-up later, so design for the budget. Late responses are dropped.

Latency budgets per endpoint (from the API examples): `healthz` 2s (retried ×3) · `metadata` 2s · `context` 5s · `tick` 10s · `reply` 10s.

---

## 12. Scoring — The 5 Rubric Dimensions

> **"Our AI scores decisions, not just writing style."** Each dimension is scored 0–10 (10 = highest).

As listed on the challenge page (`judge_simulator v1.0.0 · 30 canonical test pairs · 30s timeout · 20 actions/tick`):

| Dimension | What the judge looks for |
|---|---|
| **Decision quality** | Can your bot pick the best signal for this moment? Great outputs combine trigger + merchant state + category fit before writing. Strong bots don't repeat every available fact — they choose the ONE signal that should drive the next message. |
| **Specificity** | Use real numbers, offers, dates, and local facts from the given input. Penalty for generic "10% off" / "increase your sales" framings. |
| **Category fit** | Keep tone true to the business type: clinical, visual, timely, or utility-first. Dentist messages should sound clinical-peer, not retail-promo. |
| **Merchant fit** | Personalize to merchant metrics, offer catalog, prior conversation behavior, and language preference. |
| **Engagement compulsion** | Give one strong reason to reply now with a low-effort next action. Engagement means the merchant is likely to *reply*, not just read. |

*(In `challenge-brief.md` §8 the same rubric appears with "Trigger relevance" in place of "Decision quality" — does the message clearly communicate why-now, the specific trigger that prompted it? Treat both as required: pick the one signal AND make the why-now obvious.)*

### The twist — post-submission context injection

After submission, judges inject new digest items, metric shifts, triggers, and customer contexts you haven't seen, then ask your bot to compose follow-ups for these enriched scenarios. Bots that adapt without hallucinating and without going off-voice score higher.

### Simulator vs. real harness (very important)

> **The simulator is an anchor. The exam is fresh scenarios.**
>
> The local `judge_simulator.py` gives you a deterministic dry-run on the 30 canonical test pairs you can see. The actual judge harness uses **the same scoring logic but injects new facts you haven't seen** — fresh digest items, performance shifts, surprise customer scopes, replies you can't predict. Your score depends on how your bot handles *those*, not on how it does on the 30 pairs.
>
> **Bots that pattern-match the simulator will fail. Bots that ground every output in the context they've actually been given will not.**

---

## 13. Message Craft — What Wins and What Loses

### What a strong message looks like

❌ **Generic (loses):**

> Hi Doctor, want to run a discount campaign today to increase sales?

No trigger. No merchant fact. No category voice.

✅ **High compulsion (wins):**

> 190 people in your locality are searching for "Dental Check Up". Should I send them a discounted check up at ₹299?

Specific benchmark. Real offer. Single CTA.

### Levers that work

Use **proof, urgency, curiosity, and one simple yes/no action.**

**Hard constraint:** respect the session rules — **one clear CTA per send, no fake claims.**

**Bold ≠ hype.** Bold means a sharp hook from real context, without invented claims.

**Generic messages lose. Grounded copy with real merchant facts scores better.**

---

## 14. Compulsion Levers

These eight levers drive merchant replies. Use one or more per message (from the brief):

1. **Specificity / verifiability** — concrete number, date, headline, source citation
2. **Loss aversion** — "you're missing X" / "before this window closes"
3. **Social proof** — "3 dentists in your locality did Y this month"
4. **Effort externalization** — "I've drafted X — just say go" / "5-min setup"
5. **Curiosity** — "want to see who?" / "want the full list?"
6. **Reciprocity** — "I noticed Y about your account, thought you'd want to know"
7. **Asking the merchant** — "what's your most-asked treatment this week?"
8. **Single binary commitment** — Reply YES / STOP, not multi-choice

Production Vera's biggest miss is **#3 social proof** and **#7 asking the merchant** — these families barely fire today and would unlock a lot of engagement.

---

## 15. Anti-Patterns the Judge Penalizes

- Generic offers ("Flat 30% off") when service+price is available ("Haircut @ ₹99")
- Multiple CTAs in one message ("Reply YES for X, NO for Y, MAYBE for Z")
- Buried CTA — the "what to do" should land in the last sentence
- Promotional tone ("AMAZING DEAL!") for categories needing clinical/peer voice (dentists, doctors, lawyers)
- Hallucinated data — citing a "JIDA paper" not in the context, naming a competitor not in the context
- Long preambles ("I hope you're doing well. I'm reaching out today to…")
- Re-introducing yourself after the first message
- Ignoring language preference (a "hi-en mix" merchant getting pure English)
- Sending the same message verbatim that was sent before (anti-repetition, −2 per repeat)

---

## 16. Real Vera Conversation Patterns (Reference)

Real conversations from production Vera — provided as reference, **not** as the bar (aim higher).

### Pattern A — Real intent, real value exchange (the gold standard)

```
[USER]  Hi Vera. Please update my google profile.
[VERA]  Hi! Priya, Vera se bol rahi hoon. Aapka Google profile abhi 62.5% complete hai
        — description, website aur business hours missing hain. Kya aap yeh details
        share kar sakte hain taaki main sab update kar sakun?
[USER]  Ok please check & update the profile.
[VERA]  Done! Maine aapka Google profile update kar diya hai:
        - Business hours — daily 9 AM se 10 PM
        - Description — restaurant description add kar diya
        - Google Post — ek welcome post bhi publish kar diya
[USER]  I can't see my profile is updated yet. It is showing temporarily closed.
[VERA]  Google ke changes mein 24-48 ghante lagte hain. Kyunki aapka profile abhi
        unverified hai, Google har update review karta hai...
```

**What's right:** Hindi-English mix, specific numbers (62.5%, 24–48 ghante), Vera does work + reports back, handles uncertainty honestly.

### Pattern B — Auto-reply detection + graceful exit

```
[VERA]     Studio11 Family Salon ka Google profile check kar rahi thi — aapki 4.9★
           rating hai 298 reviews ke saath... business description missing hai.
[MERCHANT] Aapki jaankari ke liye bahut-bahut shukriya. Main aapki yeh sabhi baatein
           aur sujhaav hamari team tak pahuncha deti hoon.        ← auto-reply
[VERA]     Samajh gayi. Team tak pahunchane se pehle, kya aap khud dekhna chahingi
           ki exact kya missing hai Google pe? 2 minute ka kaam hai. Chalega?
[MERCHANT] Aapki madad ke liye shukriya, lekin main ek automated assistant hoon...
[VERA]     Koi baat nahi, samajh gayi. Main owner/manager se directly connect karne
           ki koshish karungi. Best wishes! 🙂
```

**What's right:** Vera tried once after detecting auto-reply, then stopped wasting turns. Polite exit.

### Pattern C — Strong specificity hook

```
[VERA] Quick nudge: your dashboard shows 6,777 missed searches in Sector 14
       for makeup services — people are looking but not finding you. Want me
       to show how your listing would appear?
```

**What's right:** "6,777" is verifiable; "Sector 14" is local; "missed searches" frames as loss aversion.

### Pattern D — Intent-handoff failure (DON'T do this)

```
[MERCHANT] Mujhe magicpin join karna hai.        ← clear intent: "I want to join"
[VERA]     Badhiya! Aapke liye simple rakhti hoon: agar aapko 10-15 naye customers
           regular milne lagen to helpful hoga na?   ← went back to qualifying
```

**What's wrong:** Merchant said yes; Vera asked another qualification question. Lost momentum. Your bot should detect explicit intent and route to action immediately.

---

## 17. Case Studies — 10 Judge-Scored Anchors

Two cases per category × 5 categories (in `examples/case-studies.md`). Each shows the 4-context input, the good composed message, the compulsion levers used, and the dimension-by-dimension score out of 50. Summary:

| # | Category / Scenario | Scope | Score |
|---|---|---|---|
| 1 | **Dentists** — JIDA research digest (Dr. Meera, fluoride trial) | merchant | **50/50** |
| 2 | **Dentists** — 6-month recall reminder for Priya (₹299 cleaning, slots) | customer | 49/50 |
| 3 | **Salons** — bridal follow-up for Kavya (196 days to wedding, ₹2,499 skin-prep program) | customer | 47/50 |
| 4 | **Salons** — curious ask ("what service was most asked-for this week?") | merchant | 44/50 |
| 5 | **Restaurants** — IPL match day reframe (Saturday IPL ≈ −12% covers; push BOGO delivery instead) | merchant | **50/50** |
| 6 | **Restaurants** — corporate bulk-thali plan (tiered pricing, named office parks) | merchant | 49/50 |
| 7 | **Gyms** — seasonal dip reframe (April–June lull is normal, −25 to −35%; save ad spend for Sept–Oct) | merchant | 48/50 |
| 8 | **Gyms** — lapsed-member winback for Rashmi ("no judgment", free HIIT trial, no auto-charge) | customer | **50/50** |
| 9 | **Pharmacies** — drug-batch recall alert (22 of 240 chronic-Rx customers affected) | merchant | **50/50** |
| 10 | **Pharmacies** — chronic refill reminder for Mr. Sharma (senior discount, free delivery, molecule-level precision) | customer | 49/50 |

Read the full messages, lever analysis, and per-dimension reasoning in `examples/case-studies.md`.

⚠️ **Plagiarism warning:** direct copying of a case study's body text counts as plagiarism — the judge runs a similarity check and penalizes near-duplicates. The cases teach the *shape* of good output; your wording must be your own.

---

## 18. Cross-Case Patterns That Score 9–10/10

Reading the 10 cases together, these patterns consistently score highest:

1. **Source citation when claiming research/compliance** — JIDA p.14, DCI circular, batch numbers. No citation = score capped at 7.
2. **Numbers from the contexts, not invented** — "22 of your chronic-Rx customers" is computed from the merchant's customer_aggregate. Numbers without provenance get scored as fabrication.
3. **Owner/merchant first name when present** — Dr. Meera, Suresh, Karthik, Ramesh. Generic "Hi" loses 1 point on merchant fit.
4. **Single most important next step framed as a low-friction commitment** — "Want me to draft X? Live in 10 min" / "Reply YES — no commitment, no auto-charge." Multi-action asks dilute.
5. **Customer-facing messages honor language preference + relationship state** — hi-en mix for Priya, "Namaste" for Mr. Sharma's son. Treating every customer the same loses 2 points.
6. **Domain-specific vocabulary used correctly** — "covers", "AOV", "sub-potency", "fluoride varnish", "ad spend", "conversion". Wrong/absent vocabulary signals the bot didn't use `CategoryContext.voice`.
7. **The bot adds judgment, not just templating** — Case Study 5 recommends *against* the obvious IPL promo on a Saturday. Contrarian, data-informed calls are the highest signal of category understanding.
8. **Meaningful `conversation_id`** — `conv_priya_recall_2026_11` is decodable and resumable. UUIDs lose nothing but help nothing.
9. **Concise rationale matching actual output** — the judge cross-checks rationale against the message; mismatch = penalty. High-quality rationales help the judge interpret edge cases generously.
10. **No repetition, no fabrication** — the operational floor. Either one caps the case at 5/dimension regardless of quality.

---

## 19. Local Self-Test — judge_simulator.py

The package includes the **LLM-powered judge** as `judge_simulator.py` — the official local harness.

**What it does:**
- Validates endpoint behavior: `/healthz`, `/metadata`, `/context`, `/tick`, `/reply`
- Runs a deterministic judge pass against your bot URL
- Scores quality across all five rubric dimensions (with visible score bars and reasons)
- Prints the complete output in a single run

**Before running — open `judge_simulator.py` and edit the CONFIGURATION section at the top:**

```python
BOT_URL       = "http://localhost:8080"   # where your bot is running
LLM_PROVIDER  = "openai"                  # "openai", "anthropic", "gemini", "deepseek",
                                          #  "groq", "ollama", "openrouter"
LLM_API_KEY   = ""                        # paste your API key
LLM_MODEL     = ""                        # optional; leave empty for provider default
OLLAMA_URL    = "http://localhost:11434"  # Ollama only
TEST_SCENARIO = "all"                     # which test to run
```

**Run it (after setting your LLM API key):**

```bash
python judge_simulator.py
```

**Available scenarios:** `warmup` · `phase2_short` (context push + tick + scoring) · `auto_reply_hell` (4 identical canned auto-replies — expects detect → wait → end) · `intent_transition` ("Ok lets do it. Whats next?" — expects action-mode wording like "done/sending/draft/confirm", NOT more qualifying questions like "would you / do you") · `hostile` ("Stop messaging me…" — expects `end`, or an apologetic send) · `all` (runs warmup + auto_reply + intent + hostile) · `full_evaluation` (pushes ALL merchants + triggers, ticks in batches of 5, scores every action).

**How it scores:** every returned message gets 5 dimension scores (Specificity, Category Fit, Merchant Fit, Decision Quality, Engagement) each 0–10, minus penalties — printed as a bar with reasons and a cryptic improvement hint. Final summary prints averages and a verdict: ≥80% EXCELLENT · ≥60% GOOD · ≥40% NEEDS IMPROVEMENT · below that, BELOW EXPECTATIONS.

**Requirement:** your output should stay **deterministic** for the same input and simulator settings.

---

## 20. Reference Implementation Skeleton

`challenge-testing-brief.md` includes a minimal-viable bot in ~80 lines of Python (FastAPI). Its shape:

- In-memory stores: `contexts[(scope, context_id)] = {version, payload}` and `conversations[conversation_id] = [turns]`
- `GET /v1/healthz` — returns status, uptime, per-scope context counts
- `GET /v1/metadata` — returns team identity
- `POST /v1/context` — stores payload if `version` is newer than held; otherwise responds 409-style `{"accepted": false, "reason": "stale_version", ...}`
- `POST /v1/tick` — loops `available_triggers`, looks up trigger + merchant + category payloads, calls **your composer**, appends actions
- `POST /v1/reply` — appends the turn to conversation history, calls **your reply-composer**, returns send/wait/end

Run with: `uvicorn bot:app --host 0.0.0.0 --port 8080`

The composer logic is stubbed (`# YOUR COMPOSER GOES HERE`) — replace it with your LLM call. See the testing brief for the full copy-pasteable skeleton.

---

## 21. Deployment Options

Host the bot on **any cloud provider** — the submitted public URL must expose all required endpoints.

- Any cloud: AWS, GCP, Azure, Render, Fly, Railway, Replit, …
- An ngrok tunnel to localhost works too
- Any hosting that exposes HTTP endpoints at `https://<your-host>/v1/*`

Requirements: reachable from the public internet, all 5 endpoints implemented with correct schemas, bot persists context across calls (no restarts during the test), compute budget sized so the bot survives the full 60-minute test (rate limits, LLM API quota).

**Keep your bot live and reachable after you submit.** The judge harness runs scoring on fresh scenarios, and selected candidates hear from the team after evaluation.

---

## 22. Failure Modes & Penalties

From the testing brief:

| Failure | Judge behavior | Penalty |
|---|---|---|
| `/v1/healthz` non-200 (3× in a row) | Bot marked offline; remaining ticks skipped | −10 (operational) |
| `/v1/tick` timeout (>30s) | Tick's actions skipped; run continues | −1 per timeout |
| `/v1/reply` timeout | Turn marked `bot_silent`; judge plays next turn after 30s | −1 per timeout |
| Malformed JSON returned | Logged, scored 0 for that action | −2 per malformed |
| `action: send` with empty body | Treated as malformed | −2 |
| Same body verbatim repeated in one conversation | Anti-repetition flag | −2 per repeat |
| URL in message body (per api-call-examples F.4) | Hard fail for that action ("Meta would reject") | −3 per URL |

Missing required action fields (`conversation_id`, `send_as`, `trigger_id`, `cta`, `suppression_key`, `rationale`) → action scored 0 + −2 penalty. No retries on timeouts.

---

## 23. Security, Privacy & Ethics Rules

- All payloads are **synthetic — no real PII**. Merchant names altered; phones redacted.
- Bots **must not** transmit any payload data outside the test environment (no calls to non-LLM external APIs carrying merchant/customer fields).
- Bots **may** use commercial LLM APIs (OpenAI, Anthropic, Google, DeepSeek, etc.) — necessary for composition.
- Bots **must not** persist context data after the test ends. On receiving the optional `POST /v1/teardown` at end of test, wipe state.
- Participants must **not scrape** real magicpin / Google data; must not impersonate magicpin in any external test.
- All bot output is for the challenge only — not for real merchant outreach.

---

## 24. How Submission Works — 4 Steps

Open submissions. No long process — build something real, show your thinking, and submit. Entries are open for evaluation (**OPEN NOW**, submit anytime).

| Step | What to do |
|---|---|
| **Step 1 — Download the challenge pack** | Get the starter zip; review the context format |
| **Step 2 — Build a working message engine** | Start with one clear end-to-end flow |
| **Step 3 — Set your public bot URL** | Submit one public base URL (e.g., `https://mybot.example.com`). The judge calls `POST /v1/context`, `POST /v1/tick`, `POST /v1/reply`, `GET /v1/healthz`, `GET /v1/metadata` |
| **Step 4 — Submit your final entry** | Share your details and keep your bot live for evaluation |

Judges inject fresh facts after submission to test adaptability and grounding; strong submissions are replay-tested on replies, objections, auto-replies, and intent handoffs.

---

## 25. Pre-Flight Checklist Before You Submit

- [ ] Endpoint reachable from the public internet (HTTPS or HTTP)
- [ ] All 5 endpoints implemented and returning correct schemas
- [ ] `/v1/context` is idempotent on `(scope, context_id, version)` — same version no-op, higher version replaces atomically
- [ ] `/v1/tick` returns within 30s even with nothing to send (`{"actions": []}`)
- [ ] `/v1/reply` returns within 30s for any conversation
- [ ] Bot persists context across calls (in-memory fine; no restarts during test)
- [ ] `judge_simulator.py` passes locally with non-zero scores
- [ ] Submitted URL via the submission portal
- [ ] Compute budget set (rate limits, LLM API quota) so the bot survives the 60-min test
- [ ] Output stays deterministic for identical inputs
- [ ] No fabricated facts anywhere in outputs; every number traceable to pushed context
- [ ] Language preference honored; single CTA per message

---

## 26. Suggested Approach & Open Challenges (Extra Credit)

### Suggested approach (from the brief — one of many, you decide)

The challenge is LLM-agnostic. Most participants will:

1. **Build a prompt template** taking the 4 contexts as structured input and asking an LLM to compose. Likely best with a frontier model (Claude / GPT / Gemini / DeepSeek).
2. **Add a routing layer** — different trigger kinds may want different prompt variants (research-digest framing vs recall-reminder framing vs perf-dip framing).
3. **Add post-LLM validation** — check output for CTA shape and language match. Re-prompt if it fails.
4. **For multi-turn** — maintain small conversation state: what was said, what the merchant signaled, next best move.

Retrieval (embed digest items, retrieve the most relevant), tool use (let the LLM call a "lookup peer stat" function), or any other architecture is allowed.

### Open challenges (intentional — extra credit)

1. **Detect auto-replies** vs real merchant replies and route differently. *(Hint: same message verbatim 3+ times = auto-reply.)*
2. **Handle intent transitions** — "yes I want to join" / "let's do it" / "go ahead" ⇒ switch from pitch mode to action mode immediately.
3. **Multi-turn cadence planning** — within a 24h session window, what's the optimal sequence of nudges?
4. **Language detection per turn** — merchant might switch English→Hindi mid-conversation.
5. **Knowing when to stop** — gracefully exit on not-interested signals or after 3 unanswered nudges.

---

## 27. FAQ — Straight Answers

### From the challenge page

**Q: How does the local simulator differ from the real judge?**
Same scoring logic, different inputs. The simulator runs locally on the 30 canonical test pairs you can see. The real judge harness injects fresh scenarios you haven't seen. The simulator is for development confidence; the harness is for the score.

**Q: What do you actually care about?**
Signal quality. If your decisions are grounded, deterministic, and useful for merchants, we notice.

**Q: What can this lead to?**
A full-time offer — or an internship that can convert into a full-time offer. Strong submissions help us find people who can join the team.

**Q: How hard is the challenge?**
Building the bot is easy. Building one a merchant actually wants to engage with is the hard part — that's the filter.

**Q: Anything else after submitting?**
Keep your bot live and reachable. The judge harness runs scoring on fresh scenarios; selected candidates hear from the team after evaluation.

### From the testing brief

**Q: Can the bot use external tools / function calling during composition?**
Yes — any tool you implement internally. You can't call non-LLM external APIs that receive merchant/customer payloads (privacy rule).

**Q: What if my bot needs more than 30s to compose a really good message?**
(a) Speed it up, or (b) return `{"actions": []}` immediately and skip the cycle. Don't background-process and return late — late responses are dropped.

**Q: Can I send multiple messages in one tick to the same merchant?**
Only one `action` per `(merchant_id, conversation_id)` pair per tick. Use a follow-up tick for more.

**Q: Does the judge see my bot's `rationale` field?**
Yes — it's part of the rubric ("did the rationale match the actual output?"). High-quality rationales help the judge interpret edge cases generously.

**Q: What language do replies have to be in?**
Match the merchant's `identity.languages`. Default English; Hindi-English code-mix encouraged where the preference says `hi`.

**Q: Can my bot refuse to send when nothing's worth saying?**
Yes — return `{"actions": []}`. Restraint is rewarded; spam is penalized.

**Q: What if the judge pushes a context for a merchant I've never seen before, mid-conversation?**
Treat it as a normal new merchant. Be ready for any context to arrive at any time.

**Q: Is there a way to query the judge for clarification mid-test?**
No. The bot has only the contexts it's been pushed. Intentional — production Vera doesn't get clarifications either.

---

## Appendix A — Worked Composition Examples

These two anchors (from the brief appendices) show exactly what "good" looks like.

### A.1 Merchant-facing — Dr. Meera, research digest

**Inputs:** Category `dentists` (peer/clinical voice, peer avg CTR 0.030, digest top item = JIDA Oct fluoride trial) · Merchant Dr. Meera (CTR 2.1% below peer, high-risk-adult cohort, last touch 2 days ago) · Trigger `research_digest_release` (urgency 2, external) · Customer: none.

**Good composed message (the bar):**

> Dr. Meera, JIDA's Oct issue landed. One item relevant to your high-risk adult patients — 2,100-patient trial showed 3-month fluoride recall cuts caries recurrence 38% better than 6-month. Worth a look (2-min abstract). Want me to pull it + draft a patient-ed WhatsApp you can share? *— JIDA Oct 2026 p.14*

**Why it scores well:**
- Specificity: "2,100-patient", "38% better", "JIDA Oct 2026 p.14"
- Category fit: clinical vocabulary, source citation, peer tone
- Merchant fit: "your high-risk adult patients" (derived from her customer aggregate)
- Trigger relevance: explicitly references the digest as the reason for messaging
- Engagement compulsion: curiosity ("Worth a look"), reciprocity ("I'll pull it for you"), low-friction CTA

### A.2 Customer-facing — Priya, recall due

**Inputs:** Category `dentists` customer-facing voice (no "guaranteed", no medical claims) · Merchant Dr. Meera (offer "Dental Cleaning @ ₹299" active, slots Wed 6pm + Thu 5pm) · Trigger `recall_due` (scope=customer, urgency 3, internal) · Customer Priya (lapsed_soft, weekday-evening preference, hi-en mix).

**Good composed message** (sent from the merchant's WhatsApp number, drafted by the bot):

> Hi Priya, Dr. Meera's clinic here 🦷 It's been 5 months since your last visit — your 6-month cleaning recall is due. Apke liye 2 slots ready hain: Wed 6 Nov, 6pm ya Thu 7 Nov, 5pm. ₹299 cleaning + complimentary fluoride. Reply 1 for Wed, 2 for Thu, or tell us a time that works.

**Why it scores well:**
- `send_as = merchant_on_behalf` (correctly attributed)
- Category fit: clinical, no overclaims
- Merchant fit: real catalog price, real open slots
- Trigger relevance: explicitly names the 6-month recall
- Customer fit: name, language mix, evening preference honored (multi-choice slot offer is allowed for booking flows)

---

## Appendix B — Package File Map & Quick Curl Reference

### Every document and what it contains

| File | Read it for |
|---|---|
| `challenge-brief.md` | The complete product spec: magicpin/Vera background, 4-context framework, compose contract, constraints, dataset, submission formats, rubric, compulsion levers, anti-patterns, real conversation patterns |
| `challenge-testing-brief.md` | The technical contract: 5 endpoints, payload schemas, harness phases, rate limits, reference FastAPI skeleton, failure modes, security rules, candidate checklist |
| `engagement-design.md` | The internal design doc proposing the 4-context framework — composer architecture, engagement loops, phased rollout, worked examples |
| `engagement-research.md` | Research notes on how production Vera currently loads merchant/customer data (useful background; not required to build your bot) |
| `examples/api-call-examples.md` | Exact HTTP requests/responses for warmup, test window, replay scenarios, and failure modes |
| `examples/case-studies.md` | 10 fully-scored anchor compositions with per-dimension breakdowns |
| `judge_simulator.py` | The official local LLM judge (configure BOT_URL + LLM key, then run) |
| `dataset/generate_dataset.py` | Deterministic seed expansion → 50 merchants / 200 customers / 100 triggers / 30 test pairs |
| `dataset/categories/*.json` | The 5 complete CategoryContexts |
| `dataset/*_seed.json` | 10 merchant, 15 customer, 25 trigger seeds (each file carries a `_README` field) |

### Quick curl reference (local testing)

```bash
export BOT_URL=http://localhost:8080

# Liveness probe
curl $BOT_URL/v1/healthz

# Push a category context
curl -X POST -H "Content-Type: application/json" \
  -d @dataset/categories/dentists.json \
  $BOT_URL/v1/context

# Trigger a tick
curl -X POST -H "Content-Type: application/json" \
  -d '{"now": "2026-04-26T10:35:00Z", "available_triggers": ["trg_001_research_digest_dentists"]}' \
  $BOT_URL/v1/tick

# Send a reply
curl -X POST -H "Content-Type: application/json" \
  -d '{"conversation_id": "conv_001", "merchant_id": "m_001_drmeera_dentist_delhi", "from_role": "merchant", "message": "Yes please send the abstract", "received_at": "2026-04-26T10:42:00Z", "turn_number": 2}' \
  $BOT_URL/v1/reply
```

---

> **Final word (from the challenge page):** *"Come in, do the challenge, and submit your working bot URL when ready."* If your bot handles every example in `examples/api-call-examples.md` correctly, it will pass warmup, the test window, and the replays with no operational issues — leaving the score entirely to the quality of your composition.
