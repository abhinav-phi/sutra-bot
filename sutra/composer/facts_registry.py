"""Facts registry — the anti-hallucination backbone (FR-05, gate check #2/#10/#13).

Extracts every verifiable token (numbers, dates, citations, names, prices,
localities, computed cohort numbers) from the CURRENT context versions.
Any number/citation in a composed message must be a member here, else the
validation gate rejects the output (cap-5/dim protection).
"""
import re
from dataclasses import dataclass, field

NUM_TOKEN_RE = re.compile(r"₹?\s?\d[\d,]*(?:\.\d+)?\s?%?")


def norm_num(tok: str) -> str:
    s = tok.lower().replace(",", "").replace("₹", "").replace("%", "")
    s = s.strip()
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s or "0"


def _walk(obj, path=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _walk(v, f"{path}.{k}" if path else str(k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _walk(v, f"{path}[{i}]")
    else:
        yield path, obj


def extract_numbers(text: str) -> list[str]:
    return [norm_num(t) for t in NUM_TOKEN_RE.findall(text)]


@dataclass
class FactsSet:
    numbers: set = field(default_factory=set)
    citations: set = field(default_factory=set)      # lowered source strings/keywords
    names: set = field(default_factory=set)          # owner/customer/locality words
    labels: dict = field(default_factory=dict)       # token -> origin path (debug)
    fresh_tokens: list = field(default_factory=list)

    # -- build --------------------------------------------------------------
    def add_number(self, raw) -> None:
        for t in NUM_TOKEN_RE.findall(str(raw)):
            self.numbers.add(norm_num(t))

    def add_citation(self, raw: str) -> None:
        s = str(raw).strip().lower()
        if s:
            self.citations.add(s)
            for word in re.findall(r"[A-Za-z]{3,}", s):
                self.citations.add(word.lower())

    def add_name(self, raw: str) -> None:
        for w in re.findall(r"[A-Za-z]{3,}", str(raw)):
            self.names.add(w.lower())

    def register_payload(self, payload: dict) -> None:
        for path, val in _walk(payload):
            if isinstance(val, bool):
                continue
            if isinstance(val, (int, float)):
                self.add_number(val)
                self.labels[str(val)] = path
            elif isinstance(val, str):
                for n in NUM_TOKEN_RE.findall(val):
                    self.numbers.add(norm_num(n))
                low = val.strip().lower()
                if any(k in path for k in ("source", "journal", "authorit", "circular")) and low:
                    self.add_citation(val)
                if any(k in path for k in ("name", "owner", "locality", "city")) and 3 < len(val) < 60:
                    self.add_name(val)

    # -- queries ------------------------------------------------------------
    def unknown_numbers(self, text: str) -> list[str]:
        """Number tokens in text that are NOT registered (single digits whitelisted
        for slot replies like 'Reply 1' / '2 slots')."""
        bad = []
        for raw in NUM_TOKEN_RE.findall(text):
            n = norm_num(raw)
            if len(n.lstrip("0")) <= 1:      # single digit
                continue
            if n not in self.numbers and n.rstrip("%") not in self.numbers:
                bad.append(raw.strip())
        return bad

    def citation_violation(self, text: str) -> bool:
        known_journal_words = {"jida", "dci", "ida", "fda", "tribune", "lancet"}
        words = {w.lower() for w in re.findall(r"[A-Za-z]{4,}", text)}
        hits = words & known_journal_words
        return bool(hits - self.citations)

    def fact_count_in(self, text: str) -> int:
        matched_nums = sum(1 for n in set(extract_numbers(text)) if n in self.numbers)
        words = {w.lower() for w in re.findall(r"[A-Za-z]{3,}", text)}
        cit_hits = len(words & self.citations)
        name_hits = len(words & self.names)
        return matched_nums + min(cit_hits, 3) + min(name_hits, 2)


def computed_numbers(merchant: dict) -> list[tuple[str, str]]:
    """Deterministically derived numbers from customer_aggregate (FR-18)."""
    out: list[tuple[str, str]] = []
    agg = merchant.get("customer_aggregate") or {}
    total = agg.get("total_unique_ytd")
    lapsed = agg.get("lapsed_180d_plus")
    ret = agg.get("retention_6mo_pct")
    if isinstance(total, (int, float)) and isinstance(lapsed, (int, float)) and total:
        pct = round(100 * lapsed / total)
        out.append((f"{pct}% of your {int(total)} customers have lapsed over 180 days",
                    f"computed:{total}:{lapsed}"))
    if isinstance(ret, (int, float)):
        out.append((f"{round(ret * 100)}% six-month retention", f"computed:retention"))
    return out


def diff_facts(old_payload: dict | None, new_payload: dict) -> list[str]:
    """Tokens that are genuinely NEW vs the previous version — powers adaptive
    incorporation (+5/dim). Value-set comparison (index-blind), so a list
    re-order never resurrects an old item as 'fresh'."""
    old_vals: set = set()
    if old_payload:
        for _p, v in _walk(old_payload):
            if isinstance(v, (str, int, float)) and not isinstance(v, bool):
                old_vals.add(str(v).strip().lower())
    fresh: list[str] = []
    seen: set = set()
    for _p, v in _walk(new_payload):
        if isinstance(v, (str, int, float)) and not isinstance(v, bool):
            s = str(v).strip()
            ls = s.lower()
            if ls and ls not in old_vals and ls not in seen:
                seen.add(ls)
                fresh.append(s)
    return fresh[:16]
