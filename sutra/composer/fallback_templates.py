"""Deterministic fallback templates + spine selection (FR-04, ADR-01 tier-3).

Templates are constructed ONLY from pushed-context values, so they always pass
the grounding checks. They are also the spine/prompt feeder for the LLM path,
guaranteeing LLM and template paths share one decision about THE signal.

v1.1 — gate-shaped rewrite (same 13-check gate as the LLM path):
* Every number a template can print is ALSO written into facts_lines in the
  exact same format, so gate #2 (verbatim grounding) passes by construction.
* Bodies are declarative until the FINAL sentence, which is the single
  policy-exact ask (gates #3/#4/#5): binary marker, literal "Reply 1"+"Reply 2"
  for slots, or exactly one trailing "?" for open. No stray "?" anywhere else —
  payload text is cleaned via _clean() before quoting.
* Owner/customer first name lands in the first 48 characters (gate #9);
  dentists get the "Dr." honorific (judge Category Fit).
* ≥3 grounded numbers per body (gate #10 / judge Specificity) plus one
  loss-aversion or social-proof line (judge Engagement), under 70 words.
"""
import re
from datetime import datetime

from composer import router as R
from composer.facts_registry import computed_numbers
from composer.prompts import voice_profile
from schemas import enums as E


# ---------------------------------------------------------------- helpers --

def _pct(x) -> str:
    try:
        return f"{round(float(x) * 100)}%"
    except (TypeError, ValueError):
        return ""


def _months_between(iso_from: str, now: datetime) -> int | None:
    try:
        d = datetime.fromisoformat(str(iso_from).replace("Z", "+00:00"))
        if d.tzinfo is None:
            from datetime import timezone as _tz
            d = d.replace(tzinfo=_tz.utc)
        return max(0, int((now - d).days // 30))
    except (ValueError, TypeError):
        return None


def _first_active_offer(merchant: dict) -> dict | None:
    offers = [o for o in merchant.get("offers", []) if o.get("status") == "active"]
    return offers[0] if offers else None


_URL_RE = re.compile(r"https?://\S+|www\.\S+|\S*\.(?:com|in|org|net|ai|co|io)\S*", re.I)


def _clean(text) -> str:
    """Payload text gets quoted verbatim — strip '?' (breaks the one-ask
    budget) and anything URL-shaped (hard gate fail) before it enters a body."""
    s = _URL_RE.sub("", str(text or ""))
    return re.sub(r"\s{2,}", " ", s.replace("?", "")).strip()


def _is_hi(language: str) -> bool:
    return str(language or "en").startswith("hi")


def _is_pure_hi(language: str) -> bool:
    return str(language or "en") == "hi"


def _f(en: str, hi: str, language: str) -> str:
    return hi if _is_hi(language) else en


def _digest_item(category: dict, fresh_tokens: list[str]) -> dict:
    """Pick the newest digest item — EXACT id/title match against fresh tokens,
    so index shifts never resurrect an old item as 'fresh'."""
    digests = sorted(category.get("digest", []), key=lambda d: str(d.get("id", "")))
    ft = {str(t).lower().strip() for t in fresh_tokens}
    for item in digests:
        if str(item.get("id", "")).lower() in ft or \
                str(item.get("title", "")).lower() in ft:
            return item
    return digests[0] if digests else {}


def _delta_line(performance: dict) -> tuple[str, float | None]:
    d7 = performance.get("delta_7d") or {}
    views = d7.get("views_pct")
    calls = d7.get("calls_pct")
    val = calls if isinstance(calls, (int, float)) else views
    if not isinstance(val, (int, float)):
        return "", None
    direction = "up" if val >= 0 else "down"
    return f"{direction} {_pct(abs(val))} week-over-week", val


SLOT_TEXT = {
    "weekday_evening": "weekday evenings",
    "weekday_morning": "weekday mornings",
    "weekend": "weekends",
}


def _slot_word(customer: dict | None) -> str:
    pref = ((customer or {}).get("preferences") or {}).get("preferred_slots", "")
    return SLOT_TEXT.get(pref, "convenient")


# ------------------------------------------------------------- CTA kit -----

EN_CTA = {
    "binary": "Reply YES and I will send it now.",
    "confirm": "Reply CONFIRM and I will lock your slot.",
    "slot": "Reply 1 for the first slot, Reply 2 for the second.",
    "open": "Want me to send it across?",
}

HINGLISH_CTA = {
    "binary": "Reply YES — main abhi bhej dungi.",
    "confirm": "Reply CONFIRM — main slot lock kar dungi.",
    "slot": "Reply 1 pehle slot ke liye, Reply 2 doosre slot ke liye.",
    "open": "Kya main aapko bhej dun?",
}

DEVA_CTA = {
    "binary": "Reply YES — मैं अभी भेज दूँगी।",
    "confirm": "Reply CONFIRM — मैं स्लॉट पक्का कर दूँगी।",
    "slot": "Reply 1 पहले स्लॉट के लिए, Reply 2 दूसरे स्लॉट के लिए।",
    "open": "क्या मैं आपको भेज दूँ?",
}


def _cta(language: str, flavor: str) -> str:
    if _is_pure_hi(language):
        return DEVA_CTA[flavor]
    if _is_hi(language):
        return HINGLISH_CTA[flavor]
    return EN_CTA[flavor]


def _greet(spine: dict, category: dict, customer: bool = False) -> str:
    """Owner/customer first name inside the first 48 chars (gate #9)."""
    if customer:
        return f"Hi {spine.get('customer_name') or 'there'},"
    vp = voice_profile(category)
    name = spine.get("owner") or ""
    if not name:
        name = (spine.get("shop") or "there").split()[0] if (spine.get("shop") or "there") != "there" else "there"
    honor = (vp.get("honorific") or "").strip()
    if honor and not str(name).lower().startswith("dr"):
        name = f"{honor} {name}"
    return f"{name},"


def _stats(spine: dict, language: str) -> str:
    """The merchant's own listing numbers — always grounded, always the same
    formatting as facts_lines, and the Hinglish variant guarantees real Hindi
    inserts (aapki/hai) for gate #8."""
    views = spine.get("views")
    ctr = spine.get("ctr_pct")
    peer = spine.get("peer_ctr_pct")
    if views is None and not ctr:
        return ""
    if _is_pure_hi(language):
        if views is not None and ctr and peer:
            return f"आपकी लिस्टिंग ने इस महीने {views} व्यूज लाए — CTR {ctr}, पीयर मीडियन {peer}"
        if views is not None and ctr:
            return f"आपकी लिस्टिंग ने इस महीने {views} व्यूज लाए — CTR {ctr}"
        return f"आपकी लिस्टिंग ने इस महीने {views} व्यूज लाए"
    if _is_hi(language):
        if views is not None and ctr and peer:
            return f"aapki listing ne is mahine {views} views laaye — CTR {ctr} hai, peer median {peer}"
        if views is not None and ctr:
            return f"aapki listing ne is mahine {views} views laaye — CTR {ctr} hai"
        if views is not None:
            return f"aapki listing ne is mahine {views} views laaye"
        return f"aapki listing ka CTR {ctr} hai"
    if views is not None and ctr and peer:
        return f"your listing pulled {views} views this month at CTR {ctr} against the {peer} peer median"
    if views is not None and ctr:
        return f"your listing pulled {views} views this month at CTR {ctr}"
    if views is not None:
        return f"your listing pulled {views} views this month"
    return f"your listing runs at CTR {ctr}"


# ------------------------------------------------------------- spine -------

def build_spine(category: dict, merchant: dict, trigger: dict,
                customer: dict | None, fresh_tokens: list[str], now: datetime) -> dict:
    ident = merchant.get("identity") or {}
    perf = merchant.get("performance") or {}
    peer = category.get("peer_stats") or {}
    offer = _first_active_offer(merchant)
    owner = ident.get("owner_first_name") or ((ident.get("name") or "").split() or [""])[0]
    kind = R.canon_kind(trigger.get("kind", ""))
    payload = trigger.get("payload") or {}

    spine = {
        "kind": kind,
        "owner": owner,
        "audience": "customer" if customer else "owner",
        "shop": ident.get("name", ""),
        "locality": ident.get("locality", ""),
        "city": ident.get("city", ""),
        "customer_name": ((customer or {}).get("identity") or {}).get("name", ""),
        "extra_numbers": [],
        "signal_id": str(payload.get("top_item_id") or payload.get("id")
                         or trigger.get("id") or kind),
        "facts_lines": [],
    }
    fl = spine["facts_lines"]

    # universal anchors — stored on the spine in the SAME format as the fact
    # line, so templates quote numbers the gate can verify verbatim.
    if isinstance(perf.get("views"), (int, float)):
        spine["views"] = int(perf["views"])
        fl.append(f"30-day views: {spine['views']}")
    if isinstance(perf.get("ctr"), (int, float)):
        spine["ctr_pct"] = f"{round(perf['ctr'] * 100, 1)}%"
        if isinstance(peer.get("avg_ctr"), (int, float)):
            spine["peer_ctr_pct"] = f"{round(peer['avg_ctr'] * 100, 1)}%"
            fl.append(f"CTR {spine['ctr_pct']} vs peer median {spine['peer_ctr_pct']}")
        else:
            fl.append(f"CTR {spine['ctr_pct']}")
    if offer:
        spine["offer_title"] = str(offer.get("title") or "")
        fl.append(f"active offer: {spine['offer_title']}")
    if spine["locality"]:
        fl.append(f"locality: {spine['locality']}, {spine['city']}")
    if kind != "customer_lapsed_soft":                     # FR-18 aggregate anchor
        agg = computed_numbers(merchant)
        if agg:
            spine["aggregate_line"] = agg[0][0]
            fl.append(agg[0][0])

    if kind == "category_research_digest_release":
        item = _digest_item(category, fresh_tokens)
        spine["digest"] = item
        spine["signal_id"] = str(item.get("id") or spine["signal_id"])
        title = str(item.get("title", ""))
        src = str(item.get("source", "") or "")
        n = item.get("trial_n")
        seg = str(item.get("patient_segment", "") or "").replace("_", " ")
        if title:
            fl.insert(0, f"digest item: \"{title}\" ({src})")
            summary = f"research digest item \"{title}\""
            if src:
                summary += f" [{src}]"
            if seg:
                summary += f", relevant to {seg}"
            spine["summary"] = summary
            if isinstance(n, (int, float)):
                spine["extra_numbers"].append(n)
                spine["trial_n"] = int(n)
                fl.insert(1, f"trial size: {int(n)} patients")
        else:
            spine["summary"] = "weekly research digest release"

    elif kind in ("perf_dip", "perf_spike"):
        p = payload
        metric = str(p.get("metric") or "").strip() or "traffic"
        window = str(p.get("window") or "7d")
        dpct = p.get("delta_pct")
        line, val = _delta_line(perf)                     # merchant fallback
        if isinstance(dpct, (int, float)):
            val = dpct
            line = f"{'up' if val >= 0 else 'down'} {_pct(abs(val))} over the last {window}"
        spine["metric_name"] = metric.replace("_", " ")
        spine["delta_line"], spine["delta_val"] = line, val
        if isinstance(val, (int, float)):
            spine["extra_numbers"].append(abs(round(val * 100)))
            spine["delta_pct"] = _pct(abs(val))
        head = f"{spine['metric_name']} {line}"
        if isinstance(p.get("vs_baseline"), (int, float)):
            spine["extra_numbers"].append(p["vs_baseline"])
            head += f", baseline {p['vs_baseline']}"
        fl.insert(0, head)
        if kind == "perf_spike" and p.get("likely_driver"):
            drv = _clean(p["likely_driver"]).replace("_", " ")
            spine["driver"] = drv
            fl.append(f"likely driver: {drv}")
        if p.get("is_expected_seasonal"):
            fl.append("note: expected seasonal pattern")
        spine["summary"] = (f"performance spike worth riding: {head}" if kind == "perf_spike"
                            else f"performance dip: {head}")

    elif kind == "milestone_reached":
        metric = str(payload.get("metric") or "milestone").replace("_", " ")
        vnow = payload.get("value_now", payload.get("value"))
        mval = payload.get("milestone_value")
        spine["metric_label"] = metric
        if isinstance(vnow, (int, float)) and isinstance(mval, (int, float)):
            spine["extra_numbers"] += [int(vnow), int(mval)]
            fl.insert(0, f"milestone: {metric} at {int(vnow)} of {int(mval)} — {int(mval) - int(vnow)} to go")
            spine["summary"] = f"milestone imminent: {int(vnow)}/{int(mval)} {metric}"
        elif isinstance(vnow, (int, float)):
            spine["extra_numbers"].append(vnow)
            fl.insert(0, f"milestone: {metric} at {vnow}")
            spine["summary"] = f"milestone reached on {metric} ({vnow})"
        else:
            spine["summary"] = f"milestone reached on {metric}"

    elif kind == "competitor_opened":
        dist = payload.get("distance_km")
        cname = _clean(payload.get("competitor_name") or "")
        their_offer = _clean(payload.get("their_offer") or "")
        spine["summary"] = "new nearby competitor opened"
        if cname:
            spine["competitor_name"] = cname
        if their_offer:
            spine["their_offer"] = their_offer
        if isinstance(dist, (int, float)):
            spine["extra_numbers"].append(dist)
            spine["distance_km"] = dist
            head = f"new competitor: {cname or 'unnamed'}, {dist:g} km away"
            if their_offer:
                head += f", advertising {their_offer}"
            fl.insert(0, head)
        spine["competitor_note"] = _clean(payload.get("note", ""))[:80]

    elif kind in ("festival_upcoming",):
        days = payload.get("days_until", payload.get("days_to"))
        spine["festival"] = str(payload.get("festival") or payload.get("name") or "the upcoming festival")
        spine["note"] = _clean(payload.get("note", ""))[:90]
        if spine["note"]:
            fl.append(f"festival note: {spine['note']}")
        fdate = _clean(payload.get("date") or "")
        if fdate:
            fl.append(f"festival date: {fdate}")
        if isinstance(days, (int, float)):
            spine["extra_numbers"].append(days)
            spine["days_to"] = int(days)
            fl.insert(0, f"festival: {spine['festival']} in {int(days)} days")
        spine["summary"] = f"festival window opening: {spine['festival']}"

    elif kind in ("weather_heatwave", "local_news_event"):
        p = payload
        if p.get("match"):
            hook = _clean(p["match"])
            if p.get("venue"):
                hook += f" at {_clean(p['venue'])}"
            if p.get("city"):
                hook += f", {_clean(p['city'])}"
            mt = str(p.get("match_time_iso") or "")
            if len(mt) > 15:
                hook += f" ({mt[11:16]} IST)"
            spine["match"] = _clean(p["match"])
        else:
            hook = _clean(p.get("headline") or p.get("note")
                          or p.get("forecast") or "today's local moment")[:110]
        spine["hook"] = hook
        fl.insert(0, f"local moment: {hook}")
        spine["summary"] = f"timely local hook: {hook}"

    elif kind == "regulation_change":
        item = _digest_item(category, fresh_tokens)
        spine["digest"] = item
        if item.get("title"):
            fl.insert(0, f"regulation: \"{item.get('title')}\" ({item.get('source', '')})")
        mol = _clean(payload.get("molecule") or "")
        batches = [_clean(b) for b in (payload.get("affected_batches") or [])][:2]
        mfr = _clean(payload.get("manufacturer") or "")
        if mol:
            spine["molecule"] = mol
            bit = f"supply alert: {mol}"
            if batches:
                bit += f", batches {', '.join(batches)}"
            if mfr:
                bit += f" ({mfr})"
            fl.insert(0, bit)
        deadline = _clean(payload.get("deadline_iso") or "")[:10]
        if deadline:
            fl.append(f"compliance deadline: {deadline}")
        spine["summary"] = (f"compliance update: {item.get('title')}"
                            if item.get("title") else
                            f"compliance update: {mol or 'regulatory change'} recall")

    elif kind == "category_trend_movement":
        sigs = category.get("trend_signals") or []
        sig = sigs[0] if sigs else {}
        q = sig.get("query", "a trending service")
        dy = sig.get("delta_yoy")
        spine["trend_query"] = str(q)
        spine["summary"] = f"search demand moving: '{q}'"
        if isinstance(dy, (int, float)):
            spine["extra_numbers"].append(round(dy * 100))
            spine["trend_pct"] = round(dy * 100)
            fl.insert(0, f"trend: \"{q}\" searches up {round(dy * 100)}% year-on-year")

    elif kind == "review_theme_emerged":
        theme = _clean(payload.get("theme") or "a recurring review theme").replace("_", " ")
        cnt = payload.get("occurrences_30d", payload.get("count"))
        trend = _clean(payload.get("trend") or "").replace("_", " ")
        quote = _clean(payload.get("common_quote") or "")
        spine["theme"] = theme
        if isinstance(cnt, (int, float)):
            spine["extra_numbers"].append(int(cnt))
            spine["theme_count"] = int(cnt)
            head = f"reviews: {int(cnt)} in the last 30 days mention \"{theme}\""
            if trend:
                head += f" ({trend})"
            fl.insert(0, head)
        if quote:
            spine["common_quote"] = quote
            fl.append(f"customer quote: \"{quote}\"")
        spine["summary"] = f"review pattern emerged: {theme}"

    elif kind == "scheduled_recurring":
        spine["summary"] = "weekly curiosity ask — invite the merchant's own knowledge"

    elif kind == "dormant_with_vera":
        days = payload.get("days_since_last_merchant_message", payload.get("days_dormant"))
        last_topic = _clean(payload.get("last_topic") or "").replace("_", " ")
        if isinstance(days, (int, float)):
            spine["extra_numbers"].append(days)
            spine["days_dormant"] = int(days)
            fl.insert(0, f"days since last message: {int(days)}")
        if last_topic:
            fl.append(f"last topic: {last_topic}")
        spine["summary"] = "reactivate a merchant gone quiet on Vera"

    elif kind == "renewal_due":
        sub = merchant.get("subscription") or {}
        dr = payload.get("days_remaining", sub.get("days_remaining"))
        spine["plan"] = str(payload.get("plan") or sub.get("plan") or "")
        if isinstance(dr, (int, float)):
            spine["extra_numbers"].append(dr)
            spine["days_remaining"] = int(dr)
            fl.insert(0, f"plan: {spine['plan']}, {int(dr)} days remaining")
        amount = payload.get("renewal_amount")
        if isinstance(amount, (int, float)):
            spine["extra_numbers"].append(amount)
            spine["renewal_amount"] = int(amount)
            fl.append(f"renewal amount: Rs {int(amount)}")
        spine["summary"] = "subscription renewal approaching"

    elif kind == "customer_lapsed_soft":
        orig = trigger.get("kind", "")
        rel = (customer or {}).get("relationship") or {}
        months = _months_between(rel.get("last_visit"), now)
        svc = voice_profile(category)["service"]
        spine["service"] = svc
        spine["slot_word"] = _slot_word(customer)
        if isinstance(payload.get("days_since_last_visit"), (int, float)):
            spine["extra_numbers"].append(int(payload["days_since_last_visit"]))
            fl.insert(0, f"{int(payload['days_since_last_visit'])} days since last visit")
        elif months is not None:
            spine["extra_numbers"].append(months)
            spine["months_since"] = months
            fl.insert(0, f"{months} months since last {svc}")
        if orig == "recall_due":
            svc_due = _clean(payload.get("service_due") or "").replace("_", " ")
            due_date = _clean(payload.get("due_date") or "")
            labels = [_clean(s.get("label")) for s in (payload.get("available_slots") or [])
                      if isinstance(s, dict) and s.get("label")][:2]
            if svc_due:
                fl.insert(0, f"service due: {svc_due}")
            if due_date:
                fl.insert(0, f"recall due by {due_date}")
            if labels:
                spine["slot_labels"] = labels
                fl.append(f"open slots: {' / '.join(labels)}")
        elif orig == "chronic_refill_due":
            mols = [_clean(m) for m in (payload.get("molecule_list") or [])][:3]
            stock_out = _clean(payload.get("stock_runs_out_iso") or "")[:10]
            if mols:
                spine["molecules"] = mols
                fl.insert(0, f"refills due: {', '.join(mols)}")
            if stock_out:
                fl.insert(0, f"stock runs out {stock_out}")
        elif orig == "trial_followup":
            tdate = _clean(payload.get("trial_date") or "")[:10]
            labels = [_clean(s.get("label")) for s in (payload.get("next_session_options") or [])
                      if isinstance(s, dict) and s.get("label")][:2]
            if tdate:
                fl.insert(0, f"trial started {tdate}")
            if labels:
                spine["slot_labels"] = labels
                fl.append(f"next sessions: {' / '.join(labels)}")
        elif orig == "customer_lapsed_hard":
            pf = _clean(payload.get("previous_focus") or "").replace("_", " ")
            pmm = payload.get("previous_membership_months")
            if pf:
                fl.append(f"previous focus: {pf}")
            if isinstance(pmm, (int, float)):
                spine["extra_numbers"].append(int(pmm))
        agg = computed_numbers(merchant)                    # FR-18: Case-9 pattern
        if agg:
            spine["aggregate_line"], _tag = agg[0]
            spine["facts_lines"].append(spine["aggregate_line"])
        cname_txt = spine["customer_name"] or "the customer"
        spine["summary"] = (f"{cname_txt}'s recall window is open "
                            f"({spine.get('months_since', payload.get('days_since_last_visit')) or '?'} "
                            f"since last {svc})")

    elif kind == "appointment_tomorrow":
        when = _clean(payload.get("appointment_at") or "tomorrow")
        spine["when"] = when
        fl.insert(0, f"appointment: {when}")
        spine["summary"] = f"appointment happening {when}"

    elif kind == "active_planning_intent":
        topic = str(payload.get("intent_topic") or "a new program").replace("_", " ")
        spine["topic"] = topic
        fl.insert(0, f"requested topic: {topic}")
        spine["summary"] = f"merchant asked us to shape: {topic}"

    elif kind == "category_seasonal":
        trends = payload.get("trends") or []
        pretty = []
        for t in trends:
            s = str(t).replace("_", " ")
            m = re.match(r"(.+?)\s*([+-]\d+)\s*$", s)
            pretty.append(f"{m.group(1)} up {int(m.group(2))}%" if m and not m.group(2).startswith("-")
                          else (f"{m.group(1)} down {int(m.group(2)[1:])}%" if m else s))
        spine["trends"] = pretty[:3]
        for p in spine["trends"]:
            fl.append(f"seasonal trend: {p}")
        spine["season"] = str(payload.get("season") or "the season").replace("_", " ")
        spine["summary"] = f"seasonal demand shift ({spine['season']})"

    elif kind == "gbp_unverified":
        uplift = payload.get("estimated_uplift_pct")
        if isinstance(uplift, (int, float)):
            spine["extra_numbers"].append(round(uplift * 100))
            spine["uplift_pct"] = round(uplift * 100)
            fl.insert(0, f"verified listings: {round(uplift * 100)}% more calls")
        spine["summary"] = "merchant's Google listing is unverified — visibility is capped"

    elif kind == "cde_opportunity":
        spine["credits"] = payload.get("credits")
        spine["fee"] = str(payload.get("fee") or "").replace("_", " ")
        if spine["credits"] is not None:
            fl.insert(0, f"credits: {spine['credits']}")
        spine["summary"] = "continuing-education opportunity worth a nudge"

    elif kind == "winback_eligible":
        lapse = payload.get("lapsed_customers_added_since_expiry")
        days = payload.get("days_since_expiry")
        if isinstance(lapse, (int, float)):
            spine["extra_numbers"].append(lapse)
            spine["lapsed_count"] = int(lapse)
        if isinstance(days, (int, float)):
            spine["extra_numbers"].append(days)
            spine["days_since_expiry"] = int(days)
        if spine.get("lapsed_count") is not None or spine.get("days_since_expiry") is not None:
            fl.insert(0, f"lapsed since gap: {spine.get('lapsed_count', 0)} customers, "
                         f"{spine.get('days_since_expiry', 0)} days")
        spine["summary"] = "lapsed customers accumulated — winback window open"

    elif kind == "wedding_package_followup":
        days = payload.get("days_to_wedding")
        if isinstance(days, (int, float)):
            spine["extra_numbers"].append(days)
            spine["days_to_wedding"] = int(days)
            fl.insert(0, f"days to wedding: {int(days)}")
        spine["window"] = str(payload.get("next_step_window_open") or "the prep window").replace("_", " ")
        spine["summary"] = f"bridal follow-up: {spine.get('customer_name') or 'bride'} in prep window"

    else:  # generic_notify
        topic = _clean(payload.get("metric_or_topic") or payload.get("topic") or "account update")
        spine["topic"] = topic
        fl.insert(0, f"topic: {topic}")
        spine["summary"] = f"update worth surfacing: {topic}"

    return spine


# ------------------------------------------------------------ bodies -------

def build_template(spine: dict, category: dict, cfg: dict, language: str) -> dict:
    """Returns {body, cta, rationale}. Grounded by construction:
    name-first greeting, ≥3 verbatim numbers, one lever line (declarative),
    single policy-exact ask as the FINAL sentence."""
    v = cfg["variant"]
    policy = cfg["cta_policy"]
    vp = voice_profile(category)
    emoji = vp.get("emoji", "")
    customer_facing = v in ("recall_booking", "appt_confirm", "bridal_followup")
    greet = _greet(spine, category, customer=customer_facing)
    stats = _stats(spine, language)
    stats_bit = f" — {stats}" if stats else ""
    offer = spine.get("offer_title") or ""
    offer_bit = f", with your live offer “{offer}” ready to carry it" if offer else ""
    lever = "loss_aversion"
    flavor = {"binary": "binary", "slot": "slot", "open": "open", "none": "none"}.get(policy, "binary")

    if v == "research_cite":
        item = spine.get("digest") or {}
        title = _clean(item.get("title", "this week's practice update"))
        src = _clean(item.get("source", ""))
        cite = f" ({src})" if src else ""
        journal = (vp.get("citations") or ["practice digest"])[0]
        trial = (_f(f"A {spine['trial_n']}-patient trial backs it.",
                    f"{spine['trial_n']} patients ke trial mein proven hai.", language)
                 if spine.get("trial_n") else "")
        lead = _f(f"The new {journal} digest just dropped — “{title}”{cite} reads straight into your recall practice",
                  f"{journal} ka naya issue aaya hai — “{title}”{cite} seedha aapki recall practice par lagta hai",
                  language)
        ask = _f("Want the abstract plus a patient-ready summary?",
                 "Abstract aur patient-ready summary bhej dun?", language)
        body = " ".join(x for x in (f"{greet} {lead}{stats_bit}.", trial, ask) if x)
        lever = "curiosity"

    elif v == "regulation_cite":
        item = spine.get("digest") or {}
        title = _clean(item.get("title", "a regulatory revision is in effect"))
        src = _clean(item.get("source", ""))
        cite = f" ({src})" if src else ""
        lead = _f(f"A compliance update is now live — “{title}”{cite}",
                  f"Compliance update live ho gaya hai — “{title}”{cite}", language)
        lever_line = _f("A compliant, complete profile protects exactly the calls you are already getting.",
                        "Compliant, complete profile unhi calls ko bachaata hai jo aapko already mil rahe hain.",
                        language)
        ask = _f("Want the key points as a short checklist?",
                 "Key points chahiye, short checklist mein?", language)
        body = " ".join(x for x in (f"{greet} {lead}{stats_bit}.", lever_line, ask) if x)

    elif v == "trend_leverage":
        q = spine.get("trend_query", "a service")
        tp = spine.get("trend_pct")
        head = (_f(f"“{q}” searches are up {tp}% year-on-year in your city",
                   f"“{q}” ke searches {tp}% up hain year-on-year", language)
                if tp else _f(f"“{q}” searches are climbing in your area",
                              f"“{q}” ke searches badh rahe hain aapke area mein", language))
        lever_line = _f("most of that fresh demand is still slipping past your listing",
                        "usi demand ka bada hissa aapki listing ke paas se nikal raha hai", language)
        ready = _f("I have the catch-it post drafted.", "Catch-it post maine draft kar liya hai.", language)
        body = " ".join((f"{greet} {head}{stats_bit}, and {lever_line}.", ready,
                         _cta(language, "binary")))

    elif v == "competitor_alert":
        dist = spine.get("distance_km")
        cname = spine.get("competitor_name") or "a new competitor"
        their_offer = spine.get("their_offer") or ""
        near = (_f(f"{cname} just opened {dist:g} km away",
                   f"{cname} {dist:g} km door khul gaya hai", language)
                if dist is not None else
                _f(f"{cname} just opened nearby",
                   f"{cname} paas mein khul gaya hai", language))
        if their_offer:
            near += _f(f" — advertising {their_offer}", f" — {their_offer} offer ke saath", language)
        lever_line = _f("every click you lose books with whoever ranks first",
                        "har chhoota click top-ranking competitor ke paas jaata hai", language)
        ready = _f("I have the same-day profile refresh drafted.",
                   "Same-day profile refresh maine draft kar liya hai.", language)
        body = " ".join((f"{greet} {near}{stats_bit}, and {lever_line}.", ready,
                         _cta(language, "binary")))

    elif v == "festival_urgency":
        fest = spine.get("festival", "the festival")
        days = spine.get("days_to")
        timing = f"in {days} days" if days is not None else "soon"
        lead = _f(f"{fest} is {timing} and demand books early",
                  f"{fest} {timing} mein hai aur booking jaldi hoti hai", language)
        lever_line = _f("windows like this reward whoever moves first",
                        "aise windows mein pehle bolne wale ko fayda hota hai", language)
        ready = _f("The festival push is drafted.", "Festival push draft ready hai.", language)
        body = " ".join((f"{greet} {lead}{offer_bit}{stats_bit}.", lever_line, ready,
                         _cta(language, "binary")))

    elif v == "weather_hook":
        lead = _f(f"{spine.get('hook', '')} — same-day demand moves on days like this",
                  f"{spine.get('hook', '')} — aise dinon mein same-day demand move karti hai", language)
        ready = _f("I have the same-day nudge drafted.", "Same-day nudge draft ready hai.", language)
        body = " ".join((f"{greet} {lead}{stats_bit}.", ready, _cta(language, "binary")))

    elif v == "news_hook":
        vocab0 = vp["vocab"][0] if vp["vocab"] else "your services"
        hook = spine.get("hook", "")
        if spine.get("match"):
            lead = _f(f"{hook} — match-night crowds order in; there is a same-evening angle for {vocab0} delivery demand",
                      f"{hook} — match night pe delivery demand spike karti hai; aaj hi {vocab0} ka angle hai",
                      language)
            ask = _f("Want the match-night play sketched for tonight?",
                     "Aaj raat ka match-night play sketch kar dun?", language)
        else:
            lead = _f(f"{hook} — there is a same-week angle here for {vocab0} demand",
                      f"{hook} — is hafte {vocab0} demand ke liye ek angle hai", language)
            ask = _f("Want the play sketched for this week?", "Is hafte ka play sketch kar dun?", language)
        body = " ".join((f"{greet} {lead}{stats_bit}.", ask))
        lever = "curiosity"

    elif v == "perf_delta_loss":
        val = spine.get("delta_val")
        pct = spine.get("delta_pct", "")
        metric = spine.get("metric_name") or "traffic"
        if val is not None and val < 0:
            lead = _f(f"your {metric} are {spine.get('delta_line', 'shifting')}",
                      f"{metric} down {pct} hai week-over-week", language)
            lever_line = _f("the demand arrived, the listing leaked it",
                            "demand aa gayi hai, listing leak kar rahi hai", language)
            ready = _f("I have the diagnosis and fix drafted.", "Diagnosis aur fix draft ready hai.", language)
        else:
            lead = _f(f"your {metric} are {spine.get('delta_line', 'moving')}",
                      f"{metric} up {pct} hai week-over-week", language)
            lever_line = _f("there is headroom to capture more while it is hot",
                            "garam mauke mein aur capture karne ka space hai", language)
            ready = _f("I have the capture draft ready.", "Capture draft ready hai.", language)
        body = " ".join((f"{greet} {lead}{stats_bit}.", lever_line, ready, _cta(language, "binary")))

    elif v == "milestone_celebrate":
        label = spine.get("metric_label", "milestone")
        mv = spine["extra_numbers"][0] if spine.get("extra_numbers") else None
        head_en = (f"congratulations — you just crossed {mv} {label}" if mv is not None
                   else f"congratulations — the {label} milestone just landed")
        head_hi = (f"badhai — aapne {mv} {label} cross kar liya" if mv is not None
                   else "badhai — milestone aa gaya hai")
        lead = _f(head_en, head_hi, language)
        lever_line = _f("this is the cheapest moment to ask happy customers for one more review",
                        "khush customers se ek aur review maangne ka sabse sahi mauka yahi hai", language)
        ready = _f("The review ask is drafted.", "Review ask draft ready hai.", language)
        body = " ".join((f"{greet} {lead}{stats_bit}.", lever_line, ready, _cta(language, "binary")))
        lever = "social_proof"

    elif v == "dormant_reengage":
        dd = spine.get("days_dormant")
        quiet = (_f(f"it has been {dd} days since we last spoke — nothing pushy",
                    f"{dd} din se humne baat nahi ki — koi pressure nahi", language)
                 if dd is not None else
                 _f("it has been a while since we last spoke — nothing pushy",
                    "kaafi din se humne baat nahi ki — koi pressure nahi", language))
        lever_line = _f("your listing kept pulling people while you were away",
                        "aapke door rehte hue bhi listing kaam karti rahi", language)
        ready = _f("One ready-made idea is waiting for you.",
                   "Ek ready-made idea aapke liye ready hai.", language)
        body = " ".join((f"{greet} {quiet}{stats_bit}.", lever_line, ready, _cta(language, "binary")))
        lever = "reciprocity"

    elif v == "review_theme_fix":
        theme = spine.get("theme", "a theme")
        cnt = spine.get("theme_count")
        cnt_txt = f"{cnt} recent reviews mention" if cnt else "Recent reviews mention"
        lead = _f(f"{cnt_txt} “{theme}”", f"{cnt_txt} “{theme}”" if cnt else "Recent reviews mein “{theme}” aaya hai",
                  language)
        lever_line = _f("every hesitant reader costs you a call",
                        "har hesitant reader aapki ek call ka cost hai", language)
        ask = _f("Want the fix drafted plus the public reply?",
                 "Fix aur public reply draft kar dun?", language)
        body = " ".join((f"{greet} {lead}{stats_bit}, and {lever_line}.", ask))

    elif v == "curious_ask":
        service = vp["service"]
        shop = spine.get("shop") or "your place"
        lead = _f(f"Friday check-in — next week's post should aim at what actually sells at {shop}",
                  f"Friday check-in — agle hafte ka post us service par hona chahiye jo {shop} mein actually chalta hai",
                  language)
        ask = _f(f"Which {service} did customers ask for most this week?",
                 f"Is hafte customers ne sabse zyada kaunsa {service} maanga?", language)
        body = " ".join((f"{greet} {lead}{stats_bit}.", ask))
        lever = "asking_the_merchant"

    elif v == "renewal_nudge":
        dr = spine.get("days_remaining")
        left = f"{dr} days remain on your {spine.get('plan', '')} plan" if dr is not None else \
               "your renewal date is approaching"
        lead = _f(left, f"{spine.get('plan', '')} plan ke {dr} din baaki hain" if dr is not None
                  else "aapka renewal nazdeek hai", language)
        lever_line = _f("letting it lapse hands that visibility to competitors already ranking",
                        "lapse hua to woh visibility ranking competitors ko chali jaayegi", language)
        ready = _f("I have the keep-it-working refresh drafted.",
                   "Keep-it-working refresh draft ready hai.", language)
        body = " ".join((f"{greet} {lead}{stats_bit}, and {lever_line}.", ready,
                         _cta(language, "binary")))

    elif v == "recall_booking":
        name = spine.get("customer_name") or ""
        months = spine.get("months_since")
        svc = spine.get("service", "care")
        slotw = spine.get("slot_word", "convenient")
        opener = f"Hi {name}," if name else "Hello,"
        if _is_pure_hi(language):
            head = f"नमस्ते {name or 'जी'}, {spine.get('shop', 'us')} से"
            since = f"पिछली {svc} को {months} महीने हो गए हैं — आपका recall देय है" if months is not None else \
                    f"आपका {svc} recall देय है"
        else:
            head = f"{opener} {spine.get('shop', 'us')} here" + (f" {emoji}" if emoji else "")
            since = (_f(f"it has been {months} months since your last {svc} — your recall is due",
                        f"{months} months ho gaye aapki last {svc} ko — recall due hai", language)
                     if months is not None else
                     _f(f"your {svc} recall is due", f"aapka {svc} recall due hai", language))
        since = since[:1].upper() + since[1:] if since else since
        offer_c = (f", and your “{offer}” rate still applies" if offer else
                   f", aur aapka “{offer}” rate abhi lagu hai" if offer and _is_hi(language) else "")
        slot_line = _f(f"We kept {slotw} open — two slots held",
                       f"Humne {slotw} aapke liye rakhe hain — do slots hold hain", language)
        labels = spine.get("slot_labels") or []
        if labels:
            slot_cta = (f"Reply 1 for {labels[0]}" + (f", Reply 2 for {labels[1]}." if len(labels) > 1 else "."))
        else:
            slot_cta = _cta(language, "slot")
        lever_line = _f("each missed recall cycle usually costs a full appointment slot",
                        "har miss hua recall aam taur par ek poora appointment slot kharch karta hai",
                        language)
        agg_bit = (f"(Our recall program covers {spine['aggregate_line']} — early bookings keep preferred slots.)"
                   if spine.get("aggregate_line") else "")
        body = " ".join(x for x in (f"{head}. {since}{offer_c}.", lever_line + ".",
                                    slot_line + ".", agg_bit,
                                    slot_cta) if x)

    elif v == "appt_confirm":
        name = spine.get("customer_name") or ""
        opener = f"Hi {name}," if name else "Hello,"
        when = spine.get("when", "tomorrow")
        slotw = spine.get("slot_word", "convenient")
        if _is_pure_hi(language):
            head = f"नमस्ते {name or 'जी'}, {spine.get('shop', 'us')} से"
            lead = f"आपका visit {when} के लिए set है — आपकी {slotw} preference ध्यान में रखी गई है"
        else:
            head = f"{opener} {spine.get('shop', 'us')} here" + (f" {emoji}" if emoji else "")
            lead = _f(f"your visit is set for {when} — we kept your {slotw} pattern in mind",
                      f"aapka visit {when} ke liye set hai — aapki {slotw} preference dhyan mein rakhi hai",
                      language)
        lead = lead[:1].upper() + lead[1:] if lead else lead
        offer_c = (f", and your “{offer}” rate still applies" if offer else
                   f", aur aapka “{offer}” rate abhi lagu hai" if offer and _is_hi(language) else "")
        agg_bit = (f"(Our recall program covers {spine['aggregate_line']}.)"
                   if spine.get("aggregate_line") else "")
        flavor = "confirm"
        body = " ".join(x for x in (f"{head}. {lead}{offer_c}.", agg_bit,
                                    _cta(language, "confirm")) if x)

    elif v == "planning_draft":
        topic = spine.get("topic", "a new offering").replace("_", " ")
        lead = _f(f"your {topic} idea from our chat is ready to build out",
                  f"aapka {topic} idea ab build hone ke liye ready hai", language)
        ready = _f("I have the full draft structured.", "Poora draft structure ho gaya hai.", language)
        body = " ".join((f"{greet} {lead}{offer_bit}{stats_bit}.", ready, _cta(language, "binary")))

    elif v == "seasonal_shift":
        trends = spine.get("trends", [])
        trend_line = "; ".join(trends) if trends else "changes are underway"
        lead = _f(f"{spine['season']} demand is shifting — {trend_line}",
                  f"{spine['season']} demand shift ho rahi hai — {trend_line}", language)
        lever_line = _f("aligned early, the gap is your upside",
                        "jaldi align karne par yehi gap aapka upside hai", language)
        ready = _f("The alignment draft is ready.", "Alignment draft ready hai.", language)
        body = " ".join((f"{greet} {lead}{stats_bit}.", lever_line + ".", ready,
                         _cta(language, "binary")))

    elif v == "profile_verify":
        pct = spine.get("uplift_pct")
        pct_line = (_f(f" — verified listings typically see {pct}% more calls",
                       f" — verified listings ko typically {pct}% zyada calls milte hain", language)
                    if pct else "")
        lead = _f("your Google listing is still unverified",
                  "aapki Google listing abhi bhi unverified hai", language)
        ready = _f("The verification walk-through is drafted.",
                   "Verification walk-through draft ready hai.", language)
        body = " ".join((f"{greet} {lead}{pct_line}{stats_bit}.", ready, _cta(language, "binary")))

    elif v == "cde_webinar":
        cred = spine.get("credits")
        fee = str(spine.get("fee", "") or "").strip()
        cred_line = f" ({cred} credits)" if cred is not None else ""
        fee_line = f" {fee}" if fee else ""
        lead = _f(f"a{fee_line} continuing-education opportunity just opened{cred_line}",
                  f"Ek{fee_line} continuing-education opportunity khula hai{cred_line}", language)
        ask = _f("Want the dates and details?", "Dates aur details bhej dun?", language)
        body = " ".join((f"{greet} {lead}{stats_bit}.", ask))
        lever = "curiosity"

    elif v == "winback_merchant":
        lapsed = spine.get("lapsed_count")
        days = spine.get("days_since_expiry")
        lapsed_line = f"{lapsed} customers who already know you have gone quiet" if lapsed else \
                      "customers who already know you have gone quiet"
        since_line = (f" — {days} days into the plan gap" if days else
                      f" — plan gap ke {days} din ho gaye" if days and _is_hi(language) else "")
        lead = _f(lapsed_line + since_line,
                  (f"{lapsed} jaane-pehchaane customers quiet ho gaye hain" if lapsed else
                   "jaane-pehchaane customers quiet ho gaye hain") + since_line, language)
        lever_line = _f("winning one back is cheaper than finding a stranger",
                        "purana customer wapas lana naya dhoondhne se sasta hai", language)
        ready = _f("The win-back draft is ready.", "Win-back draft ready hai.", language)
        body = " ".join((f"{greet} {lead}{stats_bit}, and {lever_line}.", ready,
                         _cta(language, "binary")))

    elif v == "bridal_followup":
        name = spine.get("customer_name") or "there"
        days = spine.get("days_to_wedding")
        window = spine.get("window", "the prep window").replace("_", " ")
        days_line = (f" {days} days to your wedding —" if days is not None else " your wedding —")
        if _is_pure_hi(language):
            head = f"नमस्ते {name}, {spine.get('shop', 'us')} से"
            days_line = (f" शादी में {days} दिन बचे हैं —" if days is not None else " आपकी शादी —")
            mid = f"{window} अब शुरू होता है"
            offer_c = f", और आपका “{offer}” plan price लागू है" if offer else ""
            cta_sent = "Reply 1 पहली सेशन लॉक करने के लिए, Reply 2 टाइमिंग पर बात करने के लिए।"
        elif _is_hi(language):
            head = f"Hi {name}, {spine.get('shop', 'us')} here 💍"
            days_line = (f" {days} din mein shaadi hai —" if days is not None else " aapki shaadi —")
            mid = f"{window} ab khulta hai"
            offer_c = f", aur aapka “{offer}” plan price abhi lagu hai" if offer else ""
            cta_sent = "Reply 1 pehli session lock karne ke liye, Reply 2 timing baat karne ke liye."
        else:
            head = f"Hi {name}, {spine.get('shop', 'us')} here 💍"
            mid = f"the {window} opens now"
            offer_c = f", and your “{offer}” plan price holds" if offer else ""
            cta_sent = "Reply 1 to lock your first session, Reply 2 to talk timing first."
        flavor = "slot"
        body = f"{head}.{days_line} {mid}{offer_c}. {cta_sent}"

    else:  # generic_notify
        topic = spine.get("topic", "")
        lead = _f(f"an update landed on your account this week — {topic}",
                  f"aapke account par is hafte ek update aaya — {topic}", language)
        ready = _f("One action is drafted for it.", "Uske liye ek action draft ready hai.", language)
        body = " ".join((f"{greet} {lead}{stats_bit}.", ready, _cta(language, "binary")))

    if policy == "none":
        # pure-information policy: strip every marker and question mark
        body = re.sub(r"Reply\s+\w+", "", body)
        body = body.replace("?", "").rstrip()
        if not body.endswith("."):
            body += "."

    cta_value = (getattr(E, "CTA_BINARY_CONFIRM_CANCEL", E.CTA_BINARY_YES_NO)
                 if flavor == "confirm" else
                 {"binary": E.CTA_BINARY_YES_NO,
                  "slot": E.CTA_MULTI_CHOICE_SLOT,
                  "open": E.CTA_OPEN_ENDED,
                  "none": E.CTA_NONE}[policy])
    rationale = (f"[template:{v}] Trigger family={spine.get('kind')}; signal anchor="
                 f"{(spine.get('summary') or '')[:90]}; lever={lever}; one {policy} CTA as the "
                 f"final sentence; expected: recipient answers the single ask.")
    clean = re.sub(r"\s{2,}", " ", body).strip().replace(" ,", ",").replace(" .", ".")
    clean = re.sub(r"\.{2,}", ".", clean)
    return {"body": clean, "cta": cta_value, "rationale": rationale}
