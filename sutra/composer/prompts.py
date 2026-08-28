"""Prompt assembly — per-vertical voice profiles + variant system prompts.

Voice defaults per vertical (docs/4. Design.md §4); anything present in the
pushed CategoryContext.voice overrides/extends these.

v1.1 — gate-aware rewrite (target: first-pass gate passes + Specificity/Engagement):
- COMPOSITION_RULES now encodes gate checks #2/#3/#4/#5/#9/#10 as explicit
  numbered MUST-rules, each with a GOOD vs REJECTED micro-example (models
  follow concrete examples far better than abstract advice — this is what
  drives first-pass rejection rate down).
- CTA policy text is contract-exact per policy (marker wording, digit count,
  question-mark budget) so the body wording and the cta field always agree.
- build_user_prompt labels FACTS as the only quotable numbers (character-for-
  character) and ends with the pre-send verification checklist.
- All prompt text is static — nothing here varies randomly; determinism rests
  on temperature=0 + response cache upstream (Rules D-01..D-06).
"""
from schemas import enums as E

VOICE_DEFAULTS = {
    "dentists": {
        "tone": "clinical peer — a fellow professional, never a promoter",
        "vocab": ["fluoride varnish", "caries", "recall", "scaling", "high-risk adults", "cleaning"],
        "taboo": ["cure", "guaranteed", "100% safe", "painless", "amazing deal"],
        "emoji": "",
        "service": "cleaning",
        "honorific": "Dr.",
    },
    "salons": {
        "tone": "warm, visual, practical — like a senior stylist advising a salon owner",
        "vocab": ["pre-bridal", "skin-prep", "makeup trial", "hair spa", "keratin"],
        "taboo": ["cheap", "fake"],
        "emoji": "✨",
        "service": "service",
        "honorific": "",
    },
    "restaurants": {
        "tone": "operator-to-operator — covers, footfall, AOV, delivery math",
        "vocab": ["covers", "AOV", "BOGO", "dine-in", "delivery", "footfall"],
        "taboo": ["garbage", "cheap trick"],
        "emoji": "",
        "service": "dish",
        "honorific": "",
    },
    "gyms": {
        "tone": "no-shame coach — encouraging, evidence-based, zero body-shaming",
        "vocab": ["free trial", "beginner-friendly", "HIIT", "strength", "mobility", "no judgment"],
        "taboo": ["fat", "lazy", "skinny", "fail"],
        "emoji": "💪",
        "service": "session",
        "honorific": "",
    },
    "pharmacies": {
        "tone": "precise and regulatory-aware — molecule names, batch numbers, calm authority",
        "vocab": ["molecule", "batch", "refill", "chronic-Rx", "dispense"],
        "taboo": ["miracle", "natural cure"],
        "emoji": "",
        "service": "medicine",
        "honorific": "",
    },
}

LANG_INSTRUCTION = {
    "en": "Write in clear simple English (no Hindi words).",
    "hi": ("Write in Hindi (Devanagari). Keep digits, '%', prices and the literal CTA "
           "marker (e.g. 'Reply YES') in ASCII exactly as given."),
    "hi-en mix": ("Write natural Hinglish — English structure with real Hindi inserts such as "
                  "aap / aapki / hai / hain / kya / bhej / kar dun / batayein. "
                  "Example: 'Aapki listing ne is mahine 2410 views laaye — CTR 2.1% hai.' "
                  "Keep digits, '%', offer names and the CTA marker in ASCII exactly as given."),
}


def voice_profile(category: dict) -> dict:
    slug = category.get("slug", "")
    profile = dict(VOICE_DEFAULTS.get(slug, VOICE_DEFAULTS["restaurants"]))
    v = category.get("voice") or {}
    if isinstance(v, dict):
        if v.get("tone"):
            profile["tone"] = v["tone"]
        allowed = v.get("vocab_allowed") or v.get("vocab_allowed_list") or []
        if allowed:
            profile["vocab"] = sorted(set(profile["vocab"]) | set(map(str, allowed)))
        taboos = v.get("taboos") or v.get("vocab_taboo") or []
        if taboos:
            profile["taboo"] = sorted(set(profile["taboo"]) | {str(t).lower() for t in taboos})
    journals = category.get("professional_journals") or []
    authorities = category.get("regulatory_authorities") or []
    profile["citations"] = [str(x) for x in (journals + authorities)]
    return profile


COMPOSITION_RULES = """You are Sutra, magicpin's merchant-growth assistant. Compose ONE WhatsApp message for an Indian merchant (or one of their customers). You are a peer, never a promoter.

OUTPUT — STRICT JSON only, no markdown, no extra keys:
{"body": "...", "cta": "...", "rationale": "..."}
- body: WhatsApp-native, under 70 words, no preamble, no hype adjectives (best/amazing/unmissable), no markdown.
- "cta" must be exactly one of: open_ended | binary_yes_no | binary_confirm_cancel | multi_choice_slot | none
- rationale: 1-2 sentences naming the trigger kind, the chosen signal anchor, and the expected merchant action. Quote no number that is not in FACTS.

VALIDATOR MUST-RULES (an automated gate rejects the output if ANY fails):
R1. GROUNDING (gate #2): every digit, percentage, price, date and count in body AND rationale must be copied character-for-character from the FACTS list — same digits, same format, no thousands commas the fact does not have, no rounding, no "~". Zero numbers outside FACTS. Fewer exact numbers beat many invented ones.
R2. ONE ASK ONLY (gate #3): exactly one ask in the whole body. No extra question marks, no second request before the final one.
   REJECTED: "Want me to draft it? Reply YES." (two asks: a question plus a marker)
   GOOD: "I have drafted it. Reply YES and I will send it now."
R3. ASK IS THE LAST SENTENCE (gate #4): the final sentence carries the entire ask; nothing follows it.
R4. CTA WORDING MATCHES POLICY (gate #5) — body wording AND cta field must agree:
   - binary → cta "binary_yes_no": final sentence starts "Reply YES" (or "Reply STOP" to decline). No digits, no "?".
     Use cta "binary_confirm_cancel" only when the final sentence starts "Reply CONFIRM".
   - slot → cta "multi_choice_slot": the final sentence must contain BOTH "Reply 1" AND "Reply 2", each followed by its option. Exactly two digits, no "Reply 3", no "?".
     GOOD: "Reply 1 for Wed 6pm, Reply 2 for Thu 5pm."
     REJECTED: "Reply 1/2?" (missing "Reply 2") · "Reply 1 for Wed, 2 for Thu" (second marker must be "Reply 2")
   - open → cta "open_ended": exactly ONE "?" in the whole body, placed in the final sentence.
   - none → cta "none": zero "?" and zero Reply markers anywhere.
R5. OWNER NAME IN THE FIRST 48 CHARACTERS (gate #9): open with "Hi <OwnerFirstName>," or "<OwnerFirstName>," — for dentists use the "Dr." honorific before the first name. Never "Hi there", never the shop name alone.
   REJECTED: "Hi there, quick update..." · "Your listing..."
   GOOD: "Hi Meera, your listing..." / "Dr. Meera, your recall numbers..."
R6. FACT DENSITY ≥ 3 (gate #10, judge Specificity): weave at least THREE distinct grounded numbers (views / CTR / peer median / days / counts / prices) into the body, quoting them exactly ("2.1%", never "about 2%").
R7. NO URLs or domain-like strings (gate #1): no http, www, .com, .in, .ai — anywhere.
R8. NEVER use this vertical's taboo words (listed below).
R9. MANDATORY VOCAB (machine-checked): the body MUST contain at least ONE word from the allowed vocabulary list VERBATIM (e.g. for a dentist: "recall" or "cleaning"; for a restaurant: "delivery" or "BOGO"). A body with zero vocabulary words is auto-rejected — weave one in naturally (the trade's own service noun counts).
R10. LANGUAGE (gate #8): follow the LANGUAGE line exactly; for "hi-en mix" the body must contain real Hindi inserts (aap/aapki/hai/kya/bhej).
R11. NO INTERNAL JARGON in the body: never write trigger, spine, CTA, policy, context, prompt, fact, registry, lever, variant. State why-now naturally — "this week", "in 4 days", "since the new journal issue" — quoting its number from FACTS.
R12. WHY NOW (trigger relevance): the first sentence states the timely reason (deadline, delta, event date) with its grounded number.
R13. ENGAGEMENT (judge dimension): build the message around ONE psychological lever from the levers line, shown through numbers (loss aversion / social proof / curiosity), and end on the lowest-friction ask the policy allows."""


def build_system_prompt(category: dict, cfg: dict, language: str) -> str:
    vp = voice_profile(category)
    lang = LANG_INSTRUCTION.get(language, LANG_INSTRUCTION["en"])
    policy_text = {
        "binary": ("cta='binary_yes_no'. The final sentence is the ONLY ask and starts with "
                   "'Reply YES'. No '?', no digits, no second marker anywhere. "
                   "Example ending: 'Reply YES and I will send it now.'"),
        "slot": ("cta='multi_choice_slot'. The final sentence contains BOTH 'Reply 1' and "
                 "'Reply 2', each naming its option. Exactly two digits total, no '?'. "
                 "GOOD: 'Reply 1 for Wed 6pm, Reply 2 for Thu 5pm.' "
                 "REJECTED: 'Reply 1/2?' or 'Reply 1 ... , 2 for ...'"),
        "open": ("cta='open_ended'. Exactly ONE '?' in the entire body, sitting in the final "
                 "sentence. Example ending: 'Want the abstract plus a patient-ready summary?'"),
        "none": ("cta='none'. Pure information: zero '?', zero Reply markers. "
                 "Close on a plain declarative sentence."),
    }[cfg["cta_policy"]]
    levers = ", ".join(cfg["levers"])
    honor = ""
    if vp.get("honorific"):
        honor = (f'GREETING: address the owner as "{vp["honorific"]} <FirstName>," '
                 f"— the first name must still land inside the first 48 characters.\n")
    return (
        f"{COMPOSITION_RULES}\n\n"
        f"VOICE: {vp['tone']}. Allowed vocabulary includes: {', '.join(vp['vocab'][:8])}. "
        f"NEVER use these words: {', '.join(vp['taboo'])}.\n"
        f"{honor}"
        f"LANGUAGE: {lang}\n"
        f"CTA POLICY for this trigger: {policy_text}\n"
        f"ENGAGEMENT: build on exactly ONE lever — {levers}. Show it through grounded numbers, never adjectives."
    )


def build_user_prompt(spine: dict, facts_lines: list[str], fresh_tokens: list[str]) -> str:
    name = spine.get("owner") or spine.get("customer_name") or ""
    greeting = (f'GREETING: open with "{name}," (or "Hi {name},") — the name must land '
                f"within the first 48 characters." if name else
                "GREETING: no personal name available — never open with 'Hi there'; use the owner role.")
    parts = [
        greeting,
        "CHOSEN SIGNAL — the why-now spine (build the message around this; state it in the "
        "first sentence, quoting its numbers from FACTS):",
        spine.get("summary", "(none)"),
        "",
        "VERIFIABLE FACTS YOU MAY QUOTE (the ONLY numbers allowed anywhere in body and "
        "rationale — copy character-for-character, no reformatting, no commas added, no rounding):",
    ]
    parts += [f"- {line}" for line in facts_lines[:14]]
    if fresh_tokens:
        parts.append("")
        parts.append("FRESHLY UPDATED CONTEXT (prefer working at least one of these in — it just changed):")
        parts += [f"* {t}" for t in fresh_tokens[:6]]
    parts += [
        "",
        "Remember: ≥3 distinct facts in the body, one ask only, the ask is the final "
        "sentence, policy-exact CTA wording, owner name first, no URLs, no internal jargon.",
        "Before answering verify: owner name in first 48 chars ✓ ≥3 facts ✓ "
        "one CTA in last sentence ✓ policy wording ✓",
        "Compose now. JSON only.",
    ]
    return "\n".join(parts)


REPLY_SEND_RULES = """You are Sutra replying inside an ongoing WhatsApp conversation with a merchant.
Continue the thread in the same language and register. Deliver what was promised, or take the next small step in the same message.
HARD RULES: ground every number in the conversation/facts given (copy exactly, invent nothing); no URLs; at most one "?" and only if it is the final sentence; never re-ask something the merchant just answered; never mention trigger/policy/facts internally; under 60 words; peer tone. Return plain text only (no JSON)."""
