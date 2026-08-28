"""Smoke gate: replays the critical flows from examples/api-call-examples.md.

Per docs/7.Tracker.md this is a HARD pre-submission gate.
"""
from tests.conftest import (NOW, CATEGORY, MERCHANT, push_base, push_trigger, trigger)


def test_warmup_counts_and_metadata(client):
    r = client.get("/v1/healthz").json()
    assert r["status"] == "ok"
    assert r["contexts_loaded"] == {"category": 0, "merchant": 0, "customer": 0, "trigger": 0}

    ack = push_base(client)
    assert ack["accepted"] is True and ack["ack_id"].startswith("ack_m_001")
    assert "stored_at" in ack

    counts = client.get("/v1/healthz").json()["contexts_loaded"]
    assert counts == {"category": 1, "merchant": 1, "customer": 0, "trigger": 0}

    meta = client.get("/v1/metadata").json()
    for field in ("team_name", "team_members", "model", "approach", "contact_email",
                  "version"):
        assert field in meta


def test_context_idempotency_and_version_bump(client):
    base = {"scope": "merchant", "context_id": MERCHANT["merchant_id"],
            "payload": MERCHANT, "delivered_at": NOW}
    assert client.post("/v1/context", json={**base, "version": 1}).status_code == 200

    # same-version re-push → state untouched, surfaced as stale (Example 1.5)
    r = client.post("/v1/context", json={**base, "version": 1})
    assert r.status_code == 409
    body = r.json()
    assert body["accepted"] is False and body["reason"] == "stale_version"
    assert body["current_version"] == 1

    # lower version → 409 as well
    r = client.post("/v1/context", json={**base, "version": 0})
    assert r.status_code == 409

    # higher version replaces atomically (Example 1.6)
    shifted = {**MERCHANT, "performance":
               {**MERCHANT["performance"], "views": 2580}}
    r = client.post("/v1/context", json={**base, "version": 2, "payload": shifted})
    assert r.status_code == 200 and r.json()["accepted"] is True

    # invalid scope → 400
    r = client.post("/v1/context", json={"scope": "galaxy", "context_id": "x",
                                         "version": 1, "payload": {}})
    assert r.status_code == 400 and r.json()["reason"] == "invalid_scope"


def test_tick_returns_valid_grounded_action(client):
    push_base(client)
    trg = trigger()
    push_trigger(client, trg)

    out = client.post("/v1/tick", json={"now": NOW,
                                        "available_triggers": [trg["id"]]}).json()
    actions = out["actions"]
    assert len(actions) == 1
    a = actions[0]
    for field in ("conversation_id", "merchant_id", "customer_id", "send_as",
                  "trigger_id", "template_name", "template_params", "body",
                  "cta", "suppression_key", "rationale"):
        assert field in a, f"missing required field {field}"
    assert a["customer_id"] is None                       # null, not omitted
    assert a["send_as"] == "vera"
    assert "http" not in a["body"].lower() and "www." not in a["body"].lower()

    # grounding spot-checks: real numbers only
    assert "2.1%" in a["body"] or "2410" in a["body"] or "38%" in a["body"]

    # suppression: same key never fires twice across ticks
    out2 = client.post("/v1/tick", json={"now": NOW,
                                         "available_triggers": [trg["id"]]}).json()
    assert out2["actions"] == []


def test_reply_engaged_accept_then_hostile_end(client):
    push_base(client)
    trg = trigger()
    push_trigger(client, trg)
    action = client.post("/v1/tick", json={"now": NOW,
                                           "available_triggers": [trg["id"]]}
                         ).json()["actions"][0]
    conv = action["conversation_id"]

    r = client.post("/v1/reply", json={
        "conversation_id": conv, "merchant_id": MERCHANT["merchant_id"],
        "from_role": "merchant", "message": "Yes please send the abstract.",
        "received_at": "2026-04-26T10:42:00Z", "turn_number": 2}).json()
    assert r["action"] == "send"
    assert any(v in r["body"].lower() for v in ("drafting", "sending", "on it"))

    r2 = client.post("/v1/reply", json={
        "conversation_id": conv, "merchant_id": MERCHANT["merchant_id"],
        "from_role": "merchant", "message": "Stop messaging me. This is useless spam.",
        "received_at": "2026-04-26T10:44:00Z", "turn_number": 3}).json()
    assert r2["action"] == "end"

    # after end, conversation stays closed
    r3 = client.post("/v1/reply", json={
        "conversation_id": conv, "merchant_id": MERCHANT["merchant_id"],
        "from_role": "merchant", "message": "hello?",
        "received_at": "2026-04-26T10:46:00Z", "turn_number": 4}).json()
    assert r3["action"] == "end"


def test_offtopic_declined_once(client):
    push_base(client)
    trg = trigger()
    push_trigger(client, trg)
    action = client.post("/v1/tick", json={"now": NOW,
                                           "available_triggers": [trg["id"]]}
                         ).json()["actions"][0]
    r = client.post("/v1/reply", json={
        "conversation_id": action["conversation_id"],
        "merchant_id": MERCHANT["merchant_id"], "from_role": "merchant",
        "message": "Btw can you also help me file my GST?",
        "received_at": "2026-04-26T10:43:00Z", "turn_number": 2}).json()
    assert r["action"] == "send"
    low = r["body"].lower()
    assert ("gst" in low or "ca " in low or "outside" in low)


def test_teardown_wipes_everything(client):
    push_base(client)
    r = client.post("/v1/teardown")
    assert r.status_code == 200
    assert r.json()["teardown"] is True
    assert client.get("/v1/healthz").json()["contexts_loaded"][
        "category"] == 0
