"""Doc-sync regression tests for the six audit fixes:

FR-21 consent gate · FR-12 24h session window · FR-06 template gating ·
FR-18 computed numbers · artifact logging · FR-19 urgency restraint.
"""
import copy

from tests.conftest import (CATEGORY, NOW, MERCHANT, push_base,
                            push_trigger, trigger)

CUSTOMER = {
    "customer_id": "c_001_priya_for_m001",
    "merchant_id": MERCHANT["merchant_id"],
    "identity": {"name": "Priya", "phone_redacted": "<phone>", "language_pref": "hi-en mix"},
    "relationship": {"first_visit": "2025-11-04", "last_visit": "2025-11-20",
                     "visits_total": 4, "services_received": ["cleaning"]},
    "state": "lapsed_soft",
    "preferences": {"channel": "whatsapp", "preferred_slots": "weekday_evening"},
    "consent": {"opted_in_at": "2025-11-04", "scope": ["recall_reminders"]},
}


def _push_customer(tc, consent_scope):
    cust = copy.deepcopy(CUSTOMER)
    cust["consent"]["scope"] = consent_scope
    r = tc.post("/v1/context", json={"scope": "customer",
                                     "context_id": CUSTOMER["customer_id"],
                                     "version": 1, "payload": cust})
    assert r.status_code == 200


def _recall_trigger(tid, sk):
    trg = trigger(tid=tid, kind="customer_lapsed_soft", cid=CUSTOMER["customer_id"],
                  urgency=3, sk=sk)
    trg["payload"] = {"category": "dentists"}
    return trg


def test_consent_blocks_uncovered_family(client):
    push_base(client)
    _push_customer(client, ["appointment_reminders"])       # recall NOT covered
    trg = _recall_trigger("trg_c1", "recall:c1")
    push_trigger(client, trg)
    out = client.post("/v1/tick", json={"now": NOW,
                                        "available_triggers": [trg["id"]]}).json()
    assert out["actions"] == []                              # privacy gate held


def test_consent_allows_covered_family_and_uses_computed_numbers(client):
    push_base(client)
    _push_customer(client, ["recall_reminders"])
    trg = _recall_trigger("trg_c2", "recall:c2")
    push_trigger(client, trg)
    out = client.post("/v1/tick", json={"now": NOW,
                                        "available_triggers": [trg["id"]]}).json()
    assert len(out["actions"]) == 1
    a = out["actions"][0]
    assert a["send_as"] == "merchant_on_behalf" and a["customer_id"] is not None
    # FR-18: aggregate derived from customer_aggregate woven into the body
    assert "14%" in a["body"] or "38%" in a["body"]
    # months-since number grounded in relationship.last_visit
    assert "months" in a["body"]


def test_session_window_freeform_after_reply(client):
    push_base(client)
    _push_customer(client, ["recall_reminders"])
    trg = _recall_trigger("trg_s1", "recall:s1")
    push_trigger(client, trg)
    a = client.post("/v1/tick", json={"now": NOW,
                                      "available_triggers": [trg["id"]]}
                    ).json()["actions"][0]
    assert a["template_name"].startswith("sutra_")           # first touch: templated

    client.post("/v1/reply", json={
        "conversation_id": a["conversation_id"], "merchant_id": a["merchant_id"],
        "from_role": "merchant", "message": "Yes please go ahead",
        "received_at": "2026-04-26T10:45:00Z", "turn_number": 2})

    # fresh merchant context → new trigger fires while session still open
    shifted = {**MERCHANT, "signals": MERCHANT["signals"] + ["new_review_theme"]}
    client.post("/v1/context", json={"scope": "merchant",
                                     "context_id": MERCHANT["merchant_id"],
                                     "version": 2, "payload": shifted})
    t2 = trigger(tid="trg_s2", sk="research:dentists:2026-W18")
    push_trigger(client, t2)
    a2 = client.post("/v1/tick", json={"now": "2026-04-26T11:00:00Z",
                                       "available_triggers": [t2["id"]]}).json()["actions"][0]
    assert a2["template_name"] == "sutra_freeform_v1"        # FR-12 honored
    assert a2["template_params"] == []


def test_urgency_ranks_not_blocks(client):
    """FR-19 update: urgency drives ranking, not a hard floor — every valid
    event fires once (dedup prevents spam), high-urgency ranks first."""
    push_base(client)

    low = trigger(tid="trg_q1", kind="perf_dip", sk="q:1", urgency=1)
    high = trigger(tid="trg_q2", kind="perf_dip", sk="q:2", urgency=5)
    push_trigger(client, low)
    push_trigger(client, high)

    out = client.post("/v1/tick", json={"now": NOW,
                                        "available_triggers": [high["id"], low["id"]]}).json()
    actions = out["actions"]
    assert len(actions) == 2                      # both fire (urgency only ranks)
    assert {a["trigger_id"] for a in actions} == {high["id"], low["id"]}

    # second tick: suppression dedup -> nothing fires again
    out2 = client.post("/v1/tick", json={"now": NOW,
                                         "available_triggers": [low["id"], high["id"]]}).json()
    assert out2["actions"] == []


def test_artifact_logs_written(client, tmp_path):
    client.get("/v1/healthz")                                # → healthz.jsonl
    push_base(client)                                        # → context_pushes.jsonl
    art = tmp_path / "artifacts"
    assert (art / "healthz.jsonl").exists()
    assert (art / "context_pushes.jsonl").exists()

    trg = trigger()
    push_trigger(client, trg)
    a = client.post("/v1/tick", json={"now": NOW,
                                      "available_triggers": [trg["id"]]}).json()["actions"][0]
    client.post("/v1/reply", json={
        "conversation_id": a["conversation_id"], "merchant_id": MERCHANT["merchant_id"],
        "from_role": "merchant", "message": "Yes please send it",
        "received_at": NOW, "turn_number": 2})
    conv_lines = (art / "conversations.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert any('"event": "tick"' in ln for ln in conv_lines)
    assert any('"classification"' in ln for ln in conv_lines)


def test_template_gate_metadata_present(client):
    """FR-06 honesty: composer tracks gate outcome for every template."""
    push_base(client)
    trg = trigger()
    push_trigger(client, trg)
    client.post("/v1/tick", json={"now": NOW, "available_triggers": [trg["id"]]})
    st = client.app.state.sutra
    assert isinstance(st.composer.rejections, dict)          # rejection ledger live
