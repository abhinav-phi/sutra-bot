"""Regex-first reply classifier (ADR-08): deterministic, sub-millisecond.

Classes (docs TechSpec AI-3): accept / question / objection / auto_reply /
explicit_intent / hostile / off_topic.
"""
import re

from schemas import enums as E

AUTO_SIGNATURES = [
    r"thank you for contacting",
    r"automated assistant",
    r"team tak pahuncha",
    r"aapki jaankari ke liye",
    r"bahut[- ]bahut shukriya",
    r"our team will respond shortly",
]

HOSTILE = [
    r"\bstop (?:messaging|sending|calling)\b", r"leave me alone",
    r"\bbas karo\b", r"\bchodo?\b", r"don'?t bother",
    r"\bbother(?:ing)? me\b", r"\buseless\b", r"\bspam\b", r"harass",
    r"\bkhatam karo\b",
]

OFF_TOPIC = [
    r"\bgst\b", r"tax filing", r"\bloan\b", r"\binvest(?:ment)?\b",
    r"legal advice", r"\binsurance policy\b",
]

INTENT = [
    r"\blet'?s do it\b", r"\blets do it\b", r"go ahead", r"\bsign me up\b",
    r"i want to join", r"mujhe (?:karna hai|join karna hai)", r"\bkar do\b",
    r"\bkardo\b", r"\bbhejo?\b", r"send karo", r"\bhaan\b(?! [,.] ?(?:par|lekin))",
    r"\byes\b", r"^ok\b", r"\btheek hai\b", r"\bconfirm\b",
]

OBJECTION = [
    r"not interested", r"maybe later", r"\babhi nahi\b", r"\bbaad mein\b",
    r"^no\b\.?$", r"\bnahi\b(?! [a-z])?$", r"\bi'?m busy\b", r"\bbusy hoon\b",
    r"later please",
]

QUESTION_WORDS = r"\?|\bwhat\b|\bhow\b|\bwhy\b|\bwhen\b|\bkya\b|\bkaise\b|\bkab\b|\bkaun\b|\bkyun\b"


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def classify(message: str, state=None) -> str:
    m = _norm(message)

    # auto-reply: known canned signature OR same text seen 2+ times before
    if any(re.search(p, m) for p in AUTO_SIGNATURES):
        return E.CLASS_AUTO_REPLY
    if state is not None:
        prior = [t.get("message", "") for t in getattr(state, "turns", [])
                 if t.get("from_role") == "merchant"]
        same = sum(1 for p in prior if _norm(p) == m)
        if same >= 2:
            return E.CLASS_AUTO_REPLY

    if any(re.search(p, m) for p in HOSTILE):
        return E.CLASS_HOSTILE
    if any(re.search(p, m) for p in OFF_TOPIC):
        return E.CLASS_OFF_TOPIC
    if any(re.search(p, m) for p in INTENT):
        return E.CLASS_EXPLICIT_INTENT
    if any(re.search(p, m) for p in OBJECTION):
        return E.CLASS_OBJECTION
    if re.search(QUESTION_WORDS, m):
        return E.CLASS_QUESTION
    return E.CLASS_ACCEPT
