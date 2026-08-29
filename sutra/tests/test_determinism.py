"""Determinism byte-equality: two fresh apps, identical pushes -> identical output."""
from fastapi.testclient import TestClient

from bot import create_app
from config import Settings
from tests.conftest import CATEGORY, NOW, MERCHANT, push_trigger, trigger


def _run(tmp_path):
    s = Settings(snapshot_path=str(tmp_path / "s.json"), disable_llm=True)
    with TestClient(create_app(s)) as tc:
        tc.post("/v1/context", json={"scope": "category", "context_id": "dentists",
                                     "version": 1, "payload": CATEGORY})
        tc.post("/v1/context", json={"scope": "merchant",
                                     "context_id": MERCHANT["merchant_id"],
                                     "version": 1, "payload": MERCHANT})
        trg = trigger()
        push_trigger(tc, trg)
        tick = tc.post("/v1/tick", json={"now": NOW,
                                         "available_triggers": [trg["id"]]}).json()
        reply = tc.post("/v1/reply", json={
            "conversation_id": tick["actions"][0]["conversation_id"],
            "merchant_id": MERCHANT["merchant_id"], "from_role": "merchant",
            "message": "Yes please send the abstract",
            "received_at": NOW, "turn_number": 2}).json()
        return tick, reply


def test_byte_identical_outputs(tmp_path):
    tick1, reply1 = _run(tmp_path)
    tick2, reply2 = _run(tmp_path / "b")
    assert tick1 == tick2
    assert reply1 == reply2
