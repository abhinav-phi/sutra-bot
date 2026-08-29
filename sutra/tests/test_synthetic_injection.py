"""Adaptive-injection generalization (FR-15): fresh context must be USED,
never hallucinated — verified in template-only mode."""
import copy

from tests.conftest import (CATEGORY, NOW, MERCHANT, push_base,
                            push_trigger, trigger)


def _tick_first_body(client, tid):
    out = client.post("/v1/tick", json={"now": NOW,
                                        "available_triggers": [tid]}).json()
    actions = out["actions"]
    assert actions, "expected an action for a fresh trigger"
    return actions[0]


def test_fresh_digest_item_is_incorporated(client):
    push_base(client)

    t1 = trigger(tid="trg_r1", sk="research:dentists:2026-W17")
    push_trigger(client, t1)
    body1 = _tick_first_body(client, t1["id"])["body"].lower()
    assert "fluoride" in body1                          # base digest item cited

    # adaptive injection: category v2 adds a NEW digest item (Example 2.8 shape)
    v2 = copy.deepcopy(CATEGORY)
    v2["digest"] = [
        {"id": "d_2026W18_dci_radiograph_NEW", "kind": "compliance",
         "title": "DCI revised radiograph dose limits effective 2026-12-15",
         "source": "DCI circular 2026-11-04"},
        *CATEGORY["digest"],
    ]
    r = client.post("/v1/context", json={"scope": "category",
                                         "context_id": "dentists",
                                         "version": 2, "payload": v2})
    assert r.status_code == 200

    t2 = trigger(tid="trg_r2", sk="research:dentists:2026-W18")
    push_trigger(client, t2)
    action = _tick_first_body(client, t2["id"])
    low = action["body"].lower()

    # leads with the NEW item, and never invents beyond it
    assert "radiograph" in low or "dose limits" in low
    for tok in ("https://", "www.", "guaranteed"):
        assert tok not in low


def test_metric_shift_reflected_not_hallucinated(client):
    push_base(client)

    t1 = trigger(tid="trg_m1", kind="perf_dip", sk="perfdip:m001:w17", urgency=3)
    push_trigger(client, t1)
    b1 = _tick_first_body(client, t1["id"])["body"]
    assert "-5%" in b1 or "5%" in b1                    # calls_pct -0.05 grounded

    shifted = {**MERCHANT, "performance":
               {**MERCHANT["performance"], "delta_7d": {"views_pct": -0.30,
                                                        "calls_pct": -0.40}}}
    client.post("/v1/context", json={"scope": "merchant",
                                     "context_id": MERCHANT["merchant_id"],
                                     "version": 2, "payload": shifted})

    t2 = trigger(tid="trg_m2", kind="perf_dip", sk="perfdip:m001:w18", urgency=4)
    push_trigger(client, t2)
    b2 = _tick_first_body(client, t2["id"])["body"]
    assert "40%" in b2                                  # new number, from context only
    stale_numbers = "18%"                                # old views_pct must vanish
    assert stale_numbers not in b2
