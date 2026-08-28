"""Validation gate — 13 checks in enforced order (docs/2. TechSpec.md AI-2).

Any failure returns a reason code; pipeline re-prompts ONCE, then uses the
deterministic fallback template. Every rejection is logged with its code.
"""
import json
import re
from pathlib import Path

from composer.facts_registry import extract_numbers, norm_num
from schemas import enums as E

URL_RE = re.compile(
    r"(?:https?://|www\.)\S+|\b[\w\-]+\.(?:com|in|org|net|co|io|ai|app|link)\b", re.I
)
CTA_MARKER_RE = re.compile(r"\b(yes|stop|confirm)\b|\breply\s*\d+\b|\?", re.I)
LAST_SENT_RE = re.compile(r"(?<=[.!?…])\s+")
REPLY_N_RE = re.compile(r"\breply\s+(\d)", re.I)

_case_study_cache: list[str] | None = None


def _case_study_bodies() -> list[str]:
    """Fenced example bodies from examples/case-studies.md (plagiarism check #12)."""
    global _case_study_cache
    if _case_study_cache is not None:
        return _case_study_cache
    bodies: list[str] = []
    p = Path(__file__).resolve().parents[2] / "challenge-pack" / "examples" / "case-studies.md"
    try:
        text = p.read_text(encoding="utf-8")
        for block in re.findall(r"```\n(.*?)```", text, re.S):
            b = block.strip()
            if len(b) > 80:
                bodies.append(b)
    except OSError:
        pass
    _case_study_cache = bodies or ["__none__"]
    return _case_study_cache


def _tokens(text: str) -> set:
    return {w.lower() for w in re.findall(r"[A-Za-z]{3,}", text)}


def _jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def validate(body: str, cta: str, rationale: str, *, facts, profile: dict,
             cfg: dict, language: str, owner_name: str | None,
             conv_body_hashes: set) -> tuple[bool, str | None]:
    low = body.lower()

    # 1. URL scan — hard fail (-3 each)
    if URL_RE.search(body):
        return False, "check1_url"

    # 2. Facts membership — every number traces to the registry
    if facts.unknown_numbers(body):
        return False, "check2_ungrounded_number"

    # 3. Single CTA — sentence-aware: rhetorical + directive in the FINAL
    #    sentence count as one ask; any ask buried earlier does not.
    markers = len(re.findall(r"\b(?:yes|stop|confirm)\b", low))
    slot_replies = REPLY_N_RE.findall(low)
    question_marks = body.count("?")
    sentences = [s for s in LAST_SENT_RE.split(body.strip()) if s.strip()]
    early_asks = sum(1 for s in sentences[:-1] if CTA_MARKER_RE.search(s))
    if slot_replies:
        if len(slot_replies) > 2 or markers or early_asks:
            return False, "check3_multiple_cta"
    elif cta != E.CTA_NONE:
        if markers >= 2 or question_marks > 1 or early_asks:
            return False, "check3_multiple_cta"

    # 4. CTA lands in the last sentence
    sentences = [s for s in LAST_SENT_RE.split(body.strip()) if s.strip()]
    last = sentences[-1] if sentences else body
    if cta != E.CTA_NONE and not CTA_MARKER_RE.search(last):
        return False, "check4_buried_cta"

    # 5. CTA policy matches trigger family
    policy = cfg["cta_policy"]
    ok_policy = {
        "binary": cta in (E.CTA_BINARY_YES_NO, E.CTA_BINARY_CONFIRM_CANCEL) and bool(markers),
        "slot": cta == E.CTA_MULTI_CHOICE_SLOT and bool(slot_replies),
        "open": cta == E.CTA_OPEN_ENDED and question_marks >= 1,
        "none": cta == E.CTA_NONE and not markers and question_marks == 0,
    }.get(policy, False)
    if not ok_policy:
        return False, f"check5_cta_policy[{policy}:{cta}]"

    # 6. Taboo words
    for t in profile.get("taboo", []):
        if t and re.search(rf"\b{re.escape(t.lower())}\b", low):
            return False, f"check6_taboo[{t}]"

    # 7. Domain vocabulary present — the vertical's own service noun counts
    #    ("cleaning", "refill", "session"): it IS the trade's language.
    vocab = list(profile.get("vocab") or [])
    service_noun = str(profile.get("service") or "").lower()
    if vocab and service_noun and service_noun not in low:
        if not any(v.lower() in low for v in vocab):
            return False, "check7_no_domain_vocab"
    elif vocab and not any(v.lower() in low for v in vocab):
        return False, "check7_no_domain_vocab"

    # 8. Language match
    lang = (language or "en").lower()
    if lang.startswith("hi"):
        has_hinglish = any(w in low for w in ("hai ", "hain ", "kya ", "aap", "apka",
                                              "karein", "kardo", "kar dun", "bhej", "ya ",
                                              "kaam", "denge"))
        has_devanagari = re.search(r"[\u0900-\u097F]", body)
        if not (has_hinglish or has_devanagari):
            return False, "check8_language"
    elif lang.startswith("en"):
        ascii_ratio = sum(1 for c in body if ord(c) < 128) / max(len(body), 1)
        if ascii_ratio < 0.85:
            return False, "check8_language"
    # regional scripts (mr/ta/te/kn): cannot verify reliably — accept

    # 9. Owner first-name greeting (when available)
    if owner_name:
        head = low[:48]
        if owner_first := owner_name.split()[0].lower():
            merchant_words = {w for w in (owner_first,)}
            if not any(w in head for w in merchant_words):
                return False, "check9_generic_greeting"

    # 10. Fact density — spine + supporting anchors
    if facts.fact_count_in(body) < 3:
        return False, "check10_thin_facts"

    # 11. Verbatim anti-repetition within this conversation
    from stores.suppression import body_hash
    if body_hash(body) in conv_body_hashes:
        return False, "check11_repeat"

    # 12. Plagiarism vs case studies (<0.6 Jaccard)
    toks = _tokens(body)
    for cs in _case_study_bodies():
        if cs == "__none__":
            break
        if _jaccard(toks, _tokens(cs)) >= 0.6:
            return False, "check12_plagiarism"

    # 13. Rationale grounded too
    if facts.unknown_numbers(rationale):
        return False, "check13_rationale_number"

    return True, None


def parse_llm_json(text: str) -> dict | None:
    """Strict-JSON extraction with one tolerant fallback."""
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except (json.JSONDecodeError, ValueError):
        pass
    m = re.search(r"\{.*\}", text, re.S)
    if m:
        try:
            data = json.loads(m.group(0))
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, ValueError):
            return None
    return None
