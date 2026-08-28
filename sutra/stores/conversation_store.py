"""Conversation state (docs/5. Schema.md §3 conversation entity)."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_dt(value) -> Optional[datetime]:
    if isinstance(value, datetime):
        value = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
        return value
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
    except ValueError:
        return None


@dataclass
class ConversationState:
    conversation_id: str
    merchant_id: str = ""
    customer_id: Optional[str] = None
    send_as: str = "vera"
    language: str = "en"
    trigger_kind: str = ""
    turns: list = field(default_factory=list)          # [{from_role,message,received_at,classification,bot_action}]
    topics_sent: set = field(default_factory=set)      # {(trigger_kind, signal_id)}
    body_hashes: set = field(default_factory=set)
    last_merchant_reply_at: Optional[str] = None
    ended: bool = False
    ended_reason: Optional[str] = None
    wait_until: Optional[str] = None                   # ISO dt
    nudge_count: int = 0                               # sends without positive merchant engagement
    auto_reply_count: int = 0
    off_topic_count: int = 0
    flagged_auto_reply: bool = False
    intent_committed: bool = False
    last_spine: dict = field(default_factory=dict)     # for follow-up phrasing
    created_at: str = field(default_factory=lambda: utc_now().isoformat())

    def in_wait(self, now: datetime) -> bool:
        wu = parse_dt(self.wait_until)
        return bool(wu and now < wu)

    def to_dict(self) -> dict:
        d = self.__dict__.copy()
        d["topics_sent"] = sorted(self.topics_sent)
        d["body_hashes"] = sorted(self.body_hashes)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "ConversationState":
        st = cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})
        st.topics_sent = {tuple(t) for t in d.get("topics_sent", [])}
        st.body_hashes = set(d.get("body_hashes", []))
        return st


class ConversationStore:
    def __init__(self) -> None:
        self._data: dict[str, ConversationState] = {}
        self._seq: dict[str, int] = {}

    def new_conversation_id(self, merchant_id: str, kind: str) -> str:
        slug = merchant_id.split("_", 1)[-1][:18] or "m"
        n = self._seq.get(merchant_id, 0) + 1
        self._seq[merchant_id] = n
        return f"conv_{slug}_{kind[:20]}_{n:02d}"

    def get(self, cid: str) -> Optional[ConversationState]:
        return self._data.get(cid)

    def create(self, state: ConversationState) -> ConversationState:
        self._data[state.conversation_id] = state
        return state

    def get_or_create(self, cid: str, **kwargs) -> ConversationState:
        if cid in self._data:
            return self._data[cid]
        st = ConversationState(conversation_id=cid, **kwargs)
        return self.create(st)

    def all(self) -> list[ConversationState]:
        return list(self._data.values())

    def wipe(self) -> None:
        self._data.clear()

    def to_dict(self) -> dict:
        return {cid: st.to_dict() for cid, st in self._data.items()}

    def load_dict(self, d: dict) -> None:
        for cid, raw in d.items():
            try:
                self._data[cid] = ConversationState.from_dict(raw)
            except Exception:
                continue
