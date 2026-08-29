"""Phase-4 replay mirrors (W8): auto-reply hell, intent transition, hostile."""
from tests.conftest import NOW, MERCHANT, push_base, push_trigger, trigger

AUTO = "Thank you for contacting Dr. Meera's Dental Clinic! Our team will respond shortly."


def _start_conv(client):
    push_base(client)
    trg = trigger()
    push_trigger(client, trg)
    action = client.post("/v1/tick", json={"now": NOW,
                                           "available_triggers": [trg["id"]]}
                         ).json()["actions"][0]
    return action["conversation_id"]


def _reply(client, conv, message, turn):
    return client.post("/v1/reply", json={
        "conversation_id": conv, "merchant_id": MERCHANT["merchant_id"],
        "from_role": "merchant", "message": message,
        "received_at": "2026-04-26T10:50:00Z", "turn_number": turn}).json()


def test_auto_reply_hell_arc(client):
    conv = _start_conv(client)
    r1 = _reply(client, conv, AUTO, 2)
    assert r1["action"] == "send" and "auto-reply" in r1["body"].lower()
    r2 = _reply(client, conv, AUTO, 3)
    assert r2["action"] == "wait"
    assert 900 <= r2["wait_seconds"] <= 3600          # bounded, never 86400
    r3 = _reply(client, conv, AUTO, 4)
    assert r3["action"] == "end"


def test_intent_transition_switches_to_action_mode(client):
    conv = _start_conv(client)
    r = _reply(client, conv, "Ok lets do it. Whats next?", 2)
    assert r["action"] == "send"
    low = r["body"].lower()
    actioning = ("done", "drafting", "sending", "confirm", "on it", "ready")
    qualifying = ("would you", "do you want", "are you interested",
                  "can you tell")
    assert any(v in low for v in actioning), f"no action verb: {low}"
    assert not any(q in low for q in qualifying), f"still qualifying: {low}"


def test_hostile_gets_polite_end(client):
    conv = _start_conv(client)
    r = _reply(client, conv, "Why are you bothering me. This is useless.", 2)
    assert r["action"] == "end"


def test_objection_then_graceful_exit(client):
    conv = _start_conv(client)
    r1 = _reply(client, conv, "Not interested right now, busy hoon.", 2)
    assert r1["action"] == "send"                       # one soft counter-offer max
    r2 = _reply(client, conv, "No.", 3)
    assert r2["action"] == "end"


def test_unknown_conversation_replay_start(client):
    """Replays may hit /v1/reply cold (no prior tick) — must handle gracefully."""
    push_base(client)
    r = _reply(client, "conv_cold_start_01",
               "Ok lets do it. Whats next?", 2)
    assert r["action"] == "send"
    assert any(v in r["body"].lower() for v in ("drafting", "sending", "on it"))
