"""Wire schemas (request/response contracts). Mirrors docs/2. TechSpec.md §5."""
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


# ---------------- /v1/context ----------------

class ContextPushIn(StrictModel):
    scope: str
    context_id: str
    version: int
    payload: dict[str, Any]
    delivered_at: Optional[str] = None


class ContextAck(StrictModel):
    accepted: bool = True
    ack_id: str
    stored_at: str


class ContextReject(StrictModel):
    accepted: bool = False
    reason: str
    current_version: Optional[int] = None
    details: Optional[str] = None
    max_bytes: Optional[int] = None


# ---------------- /v1/tick ----------------

class TickIn(StrictModel):
    now: str
    available_triggers: list[str] = Field(default_factory=list)


class TickActionOut(StrictModel):
    conversation_id: str
    merchant_id: str
    customer_id: Optional[str] = None
    send_as: str
    trigger_id: str
    template_name: str
    template_params: list[str] = Field(default_factory=list)
    body: str
    cta: str
    suppression_key: str
    rationale: str


class TickOut(StrictModel):
    actions: list[TickActionOut] = Field(default_factory=list)


# ---------------- /v1/reply ----------------

class ReplyIn(StrictModel):
    conversation_id: str
    merchant_id: Optional[str] = None
    customer_id: Optional[str] = None
    from_role: str = "merchant"
    message: str
    received_at: Optional[str] = None
    turn_number: int = 0


class SendOut(StrictModel):
    action: str = "send"
    body: str
    cta: str = "open_ended"
    rationale: str


class WaitOut(StrictModel):
    action: str = "wait"
    wait_seconds: int
    rationale: str


class EndOut(StrictModel):
    action: str = "end"
    rationale: str


# ---------------- /v1/teardown ----------------

class TeardownOut(StrictModel):
    teardown: bool = True
    wiped_at: str
    stores_cleared: list[str] = Field(default_factory=list)
