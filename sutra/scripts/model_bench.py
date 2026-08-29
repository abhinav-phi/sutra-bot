#!/usr/bin/env python3
"""Model bake-off: compose the bot's REAL prompts with each candidate LLM,
score outputs with the judge rubric (via TokenRouter qwen), report ranking.

Usage:  python sutra/scripts/model_bench.py [--samples 6] [--only model1,model2]
"""
import argparse
import asyncio
import json
import os
import statistics
import sys
import time
from pathlib import Path

SUTRA = Path(__file__).resolve().parent.parent
ROOT = SUTRA.parent
sys.path.insert(0, str(SUTRA))

import httpx  # noqa: E402

from config import Settings  # noqa: E402
from stores.context_store import ContextStore  # noqa: E402
from composer import router as R  # noqa: E402
from composer.facts_registry import FactsSet, computed_numbers  # noqa: E402
from composer.fallback_templates import build_spine  # noqa: E402
from composer.prompts import build_system_prompt, build_user_prompt, voice_profile  # noqa: E402
from composer.validation_gate import parse_llm_json, validate  # noqa: E402

# Keys come from the environment (.env is loaded by config below); never hardcode.
OR_KEY = os.environ.get("OPENROUTER_API_KEY", "")
TR_KEY = os.environ.get("TOKENROUTER_API_KEY", "")
OR_URL = "https://openrouter.ai/api/v1/chat/completions"
TR_URL = "https://api.tokenrouter.com/v1/chat/completions"

MODELS = [
    # (display, url, key, model, max_tokens, extra_body)
    ("TR-qwen3.8-max-free", TR_URL, TR_KEY, "qwen/qwen3.8-max-free", 3000, {"thinking": {"type": "disabled"}}),
    ("glm-5.2:free", OR_URL, OR_KEY, "z-ai/glm-5.2:free", 600, {}),
    ("minimax-m3:free", OR_URL, OR_KEY, "minimax/minimax-m3:free", 600, {}),
    ("minimax-m2.7:free", OR_URL, OR_KEY, "minimax/minimax-m2.7:free", 600, {}),
    ("nemotron-3.5-lightning:free", OR_URL, OR_KEY, "nvidia/nemotron-3.5-lightning:free", 600, {}),
    ("nemotron-3-super-120b:free", OR_URL, OR_KEY, "nvidia/nemotron-3-super-120b-a12b:free", 600, {}),
    ("nemotron-3-nano-omni-reasoning:free", OR_URL, OR_KEY, "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free", 600, {}),
    ("gemma-4-31b-it:free", OR_URL, OR_KEY, "google/gemma-4-31b-it:free", 600, {}),
    ("gemma-4-26b-a4b:free", OR_URL, OR_KEY, "google/gemma-4-26b-a4b-it:free", 600, {}),
    ("poolside-laguna-s-2.1:free", OR_URL, OR_KEY, "poolside/laguna-s-2.1:free", 600, {}),
    ("poolside-laguna-xs-2.1:free", OR_URL, OR_KEY, "poolside/laguna-xs-2.1:free", 600, {}),
    ("thinkingmachines-inkling:free", OR_URL, OR_KEY, "thinkingmachines/inkling:free", 600, {}),
    ("thinkingmachines-inkling-small:free", OR_URL, OR_KEY, "thinkingmachines/inkling-small:free", 600, {}),
    ("cohere-north-mini-code:free", OR_URL, OR_KEY, "cohere/north-mini-code:free", 600, {}),
    ("ling-3.0-flash-fin:free", OR_URL, OR_KEY, "inclusionai/ling-3.0-flash-fin:free", 600, {}),
    ("lfm-2.5-2.6b:free", OR_URL, OR_KEY, "liquid/lfm-2.5-2.6b:free", 600, {}),
    ("dots-3-note-preview:free", OR_URL, OR_KEY, "dots-studio/dots-3-note-preview:free", 600, {}),
]

JUDGE_SYSTEM = """You are a STRICT judge for the magicpin AI Challenge. You score merchant engagement messages.

SCORING DIMENSIONS (0-10 each, be strict - 5 is average, 7+ is good, 9+ is excellent):

1. SPECIFICITY: Does the message have VERIFIABLE facts?
   - Numbers (percentages, counts, prices)
   - Dates/times
   - Source citations
   - Concrete claims vs vague statements

2. CATEGORY FIT: Does the voice match the business type?
   - Dentists: clinical, peer-to-peer, technical OK, use "Dr." prefix
   - Salons: warm, friendly, practical
   - Restaurants: operator-to-operator
   - Gyms: coaching, motivational
   - Pharmacies: trustworthy, precise

3. MERCHANT FIT: Is it personalized to THIS merchant?
   - Uses their name/owner name correctly
   - References their actual data (not fabricated)
   - Honors language preference

4. TRIGGER RELEVANCE: Does it connect to WHY NOW?
   - Clear reason for this specific message
   - Uses data from the trigger payload
   - Not a generic nudge

5. ENGAGEMENT COMPULSION: Would they reply?
   - Loss aversion, curiosity, social proof
   - Clear CTA
   - Low friction ask

PENALTIES:
- Fabricating data not in context: -2
- Exposing internal jargon to merchant: -1

RESPOND ONLY WITH THIS EXACT JSON FORMAT:
{
  "specificity": <0-10>,
  "specificity_reason": "<why this score, 1-2 sentences>",
  "category_fit": <0-10>,
  "category_fit_reason": "<why this score>",
  "merchant_fit": <0-10>,
  "merchant_fit_reason": "<why this score>",
  "decision_quality": <0-10>,
  "decision_quality_reason": "<why this score>",
  "engagement_compulsion": <0-10>,
  "engagement_reason": "<why this score>",
  "hint": "<one sentence guidance for improvement, cryptic not direct>"
}"""

PRIORITY_KINDS = ["ipl_match_today", "customer_lapsed_hard", "perf_dip", "festival_upcoming",
                  "chronic_refill_due", "research_digest", "winback_eligible", "review_theme_emerged"]


def load_samples(ctx: ContextStore, n: int):
    """Load expanded dataset, pick n diverse (merchant, trigger[, customer]) samples."""
    exp = ROOT / "expanded"
    for folder, scope, idf in [("categories", "category", lambda p, d: p.stem),
                               ("merchants", "merchant", lambda p, d: d["merchant_id"]),
                               ("customers", "customer", lambda p, d: d["customer_id"]),
                               ("triggers", "trigger", lambda p, d: d["id"])]:
        for f in sorted((exp / folder).glob("*.json")):
            payload = json.loads(f.read_text(encoding="utf-8"))
            ctx.put(scope, idf(f, payload), 1, payload)
    kinds = {}
    for rec in sorted(ctx._data.values(), key=lambda r: r["payload"].get("id", "")):
        pass
    trig_ids = sorted([cid for (scope, cid) in ctx._data if scope == "trigger"])
    for tid in trig_ids:
        t = ctx.get("trigger", tid)
        kinds.setdefault(t.get("kind"), []).append(t)
    samples = []
    for kind in PRIORITY_KINDS:
        if len(samples) >= n:
            break
        for t in kinds.get(kind, []):
            m = ctx.get("merchant", t.get("merchant_id", ""))
            if not m:
                continue
            if not ctx.get("category", m.get("category_slug", "")):
                continue
            if t.get("customer_id") and not ctx.get("customer", t["customer_id"]):
                continue
            samples.append(t)
            break
    return samples


def build_prompt_pack(ctx: ContextStore, trigger: dict, now: str):
    """Mirror Composer.compose's prompt construction exactly."""
    merchant = ctx.get("merchant", trigger["merchant_id"])
    category = ctx.get("category", merchant.get("category_slug", ""))
    customer = ctx.get("customer", trigger.get("customer_id")) if trigger.get("customer_id") else None
    scope_kind = trigger.get("kind", "")
    scope = trigger.get("scope") or ("customer" if customer else "merchant")
    cfg = R.route(scope_kind, scope)
    langs = (merchant.get("identity") or {}).get("languages") or ["en"]
    pref = langs[0]
    if customer:
        pref = ((customer.get("identity") or {}).get("language_pref")) or "en"
    language = "hi-en mix" if ("hi" in pref and ("mix" in pref or "-" in pref or "en" in pref.split())) else ("hi" if str(pref).startswith("hi") else "en")
    spine = build_spine(category, merchant, trigger, customer, [], now)
    facts = FactsSet()
    for payload in filter(None, [category, merchant, trigger, customer]):
        facts.register_payload(payload)
    for text in [spine.get("summary", ""), *spine.get("facts_lines", [])]:
        facts.add_number(text)
    for text, _tag in computed_numbers(merchant):
        facts.add_number(text)
    for num in spine.get("extra_numbers", []):
        facts.add_number(num)
    system = build_system_prompt(category, cfg, language)
    user = build_user_prompt(spine, spine.get("facts_lines", []), [])
    return dict(system=system, user=user, facts=facts, profile=voice_profile(category),
                cfg=cfg, language=language, owner=spine.get("owner") or None,
                category=category, merchant=merchant, customer=customer, trigger=trigger,
                scope=scope)


async def chat(client, url, key, model, system, user, max_tokens, extra, retries=3):
    body = {"model": model, "max_tokens": max_tokens, "temperature": 0, "top_p": 1,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    body.update(extra)
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    last = None
    for att in range(retries):
        try:
            r = await client.post(url, json=body, headers=headers, timeout=75)
            if r.status_code == 429:
                last = f"429 rate limited"
                await asyncio.sleep(20 * (att + 1))
                continue
            r.raise_for_status()
            d = r.json()
            msg = d["choices"][0]["message"]
            return (msg.get("content") or ""), d.get("usage", {})
        except Exception as e:  # noqa: BLE001
            last = str(e)[:120]
            if "503" in last or "cache_only" in last or "Service Unavailable" in last or "429" in last:
                await asyncio.sleep(2 * (att + 1))
                continue
            break
    return None, last


def judge_prompt(pack, body, cta):
    cat, mer, trg, cust = pack["category"], pack["merchant"], pack["trigger"], pack["customer"]
    return f"""SCORE THIS MESSAGE:

=== CONTEXT PROVIDED TO BOT ===
Category: {cat.get('slug', 'unknown')}
Voice: {cat.get('voice', {}).get('tone', 'unknown')}
Taboos: {cat.get('voice', {}).get('vocab_taboo', [])[:5]}

Merchant: {mer.get('identity', {}).get('name', 'unknown')}
Owner: {mer.get('identity', {}).get('owner_first_name', 'unknown')}
Locality: {mer.get('identity', {}).get('locality', 'unknown')}
Languages: {mer.get('identity', {}).get('languages', [])}
Performance: views={mer.get('performance', {}).get('views', '?')}, calls={mer.get('performance', {}).get('calls', '?')}, ctr={mer.get('performance', {}).get('ctr', '?')}
Signals: {mer.get('signals', [])}
Active Offers: {[o.get('title') for o in mer.get('offers', []) if o.get('status') == 'active']}

Trigger Kind: {trg.get('kind', 'unknown')}
Trigger Payload: {json.dumps(trg.get('payload', {}))}
Trigger Urgency: {trg.get('urgency', '?')}

Customer: {json.dumps(cust.get('identity', {})) if cust else 'None (merchant-facing)'}

=== BOT'S MESSAGE ===
Body ({len(body)} chars): "{body}"
CTA: {cta}
Send As: {'merchant_on_behalf' if pack['scope'] == 'customer' else 'vera'}

Score each dimension 0-10 with clear reasoning. Be STRICT."""


def parse_scores(text):
    import re
    m = re.search(r"\{[\s\S]*\}", text or "")
    if not m:
        return None
    try:
        d = json.loads(m.group())
        dims = ["specificity", "category_fit", "merchant_fit", "decision_quality", "engagement_compulsion"]
        vals = {}
        for k in dims:
            v = d.get(k, d.get("trigger_relevance" if k == "decision_quality" else 5))
            vals[k] = min(10, max(0, int(v)))
        vals["total"] = sum(vals[k] for k in dims)
        return vals
    except Exception:  # noqa: BLE001
        return None


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", type=int, default=6)
    ap.add_argument("--only", default="", help="comma-separated model display names")
    args = ap.parse_args()

    settings = Settings()
    ctx = ContextStore()
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    samples = load_samples(ctx, args.samples)
    packs = [build_prompt_pack(ctx, t, now) for t in samples]
    print(f"Loaded {len(packs)} samples: {[p['trigger']['kind'] for p in packs]}\n")

    models = MODELS if not args.only else [m for m in MODELS if m[0] in args.only.split(",")]
    tr_sem = asyncio.Semaphore(3)

    class RateLimiter:
        """Token-bucket: one slot every `interval` seconds, calls may overlap."""
        def __init__(self, interval):
            self.interval, self.next, self.lock = interval, 0.0, asyncio.Lock()

        async def acquire(self):
            async with self.lock:
                now = asyncio.get_event_loop().time()
                wait = max(0.0, self.next - now)
                self.next = max(now, self.next) + self.interval
            if wait:
                await asyncio.sleep(wait)

    or_limiter = RateLimiter(3.3)  # ~18 req/min, under the 20/min free cap

    async def or_post(client, url, key, model, system, user, max_tokens, extra, retries=3):
        await or_limiter.acquire()
        return await chat(client, url, key, model, system, user, max_tokens, extra, retries)

    async def compose_one(client, pack, m):
        name, url, key, model, maxtok, extra = m
        t0 = time.monotonic()
        if url == OR_URL:
            text, usage = await or_post(client, url, key, model, pack["system"], pack["user"], maxtok, extra)
        else:
            async with tr_sem:
                text, usage = await chat(client, url, key, model, pack["system"], pack["user"], maxtok, extra)
        dt = time.monotonic() - t0
        if text is None:
            return {"ok": False, "err": str(usage)[:100], "lat": dt}
        data = parse_llm_json(text)
        if not data or not data.get("body"):
            return {"ok": False, "err": "unparsable-json", "lat": dt, "raw": text[:150]}
        body = str(data["body"]).strip()
        cta = str(data.get("cta", "")).strip()
        rationale = str(data.get("rationale", "")).strip()[:400]
        ok_gate, reason = validate(body, cta, rationale, facts=pack["facts"], profile=pack["profile"],
                                   cfg=pack["cfg"], language=pack["language"],
                                   owner_name=pack["owner"], conv_body_hashes=set())
        return {"ok": True, "lat": dt, "body": body, "cta": cta, "gate_pass": ok_gate,
                "gate_reason": (reason or "pass")[:60]}

    async def judge_one(client, pack, comp):
        if not comp.get("ok"):
            return None
        # judge = OpenRouter minimax (same judge as historical full_evaluation runs)
        text, usage = await or_post(client, OR_URL, OR_KEY, "minimax/minimax-m3:free",
                                    JUDGE_SYSTEM, judge_prompt(pack, comp["body"], comp["cta"]),
                                    1500, {}, retries=5)
        if text is None:
            return {"err": str(usage)[:80]}
        return parse_scores(text)

    results = {}
    async with httpx.AsyncClient() as client:
        for m in models:
            name = m[0]
            t0 = time.monotonic()
            comps = await asyncio.gather(*[compose_one(client, p, m) for p in packs])
            scores = await asyncio.gather(*[judge_one(client, p, c) for p, c in zip(packs, comps)])
            ok = [c for c in comps if c.get("ok")]
            scored = [s for s in scores if s and "total" in s]
            gate_pass = sum(1 for c in ok if c.get("gate_pass"))
            totals = [s["total"] for s in scored]
            results[name] = {
                "compose_ok": len(ok), "n": len(packs),
                "scored": len(scored),
                "avg_total": round(statistics.mean(totals), 1) if totals else 0,
                "dims": {k: round(statistics.mean([s[k] for s in scored]), 1) for k in
                         ["specificity", "category_fit", "merchant_fit", "decision_quality", "engagement_compulsion"]} if scored else {},
                "gate_pass": f"{gate_pass}/{len(ok)}",
                "avg_lat": round(statistics.mean([c["lat"] for c in ok]), 1) if ok else 0,
                "errs": [c.get("err") for c in comps if not c.get("ok")][:3],
            }
            r = results[name]
            print(f"{name:38s} score={r['avg_total']:5.1f}/50  compose={r['compose_ok']}/{r['n']}  "
                  f"gate={r['gate_pass']:6s} lat={r['avg_lat']:4.1f}s  ({time.monotonic()-t0:.0f}s)")
            if r["errs"]:
                print(f"{'':38s} errs: {r['errs']}")

    print("\n=== RANKING (avg judge score /50) ===")
    for name, r in sorted(results.items(), key=lambda kv: -kv[1]["avg_total"]):
        print(f"{r['avg_total']:5.1f}  {name}  (compose {r['compose_ok']}/{r['n']}, gate {r['gate_pass']})")
    out = ROOT / "data" / "model_bench_results.json"
    out.write_text(json.dumps(results, indent=1), encoding="utf-8")
    print(f"\nraw -> {out}")


if __name__ == "__main__":
    asyncio.run(main())
