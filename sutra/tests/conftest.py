"""Shared fixtures: fresh app per test, template-only mode (no LLM keys),
realistic payloads modeled on examples/api-call-examples.md."""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# force template-only determinism regardless of developer env / .env file
for var in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY"):
    os.environ.pop(var, None)
os.environ["DISABLE_LLM"] = "1"

from bot import create_app                    # noqa: E402
from config import Settings                   # noqa: E402

# config._load_dotenv() may have re-added real keys from .env at import time —
# strip them again so the test suite stays deterministic and offline.
for var in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY"):
    os.environ.pop(var, None)
os.environ["DISABLE_LLM"] = "1"

NOW = "2026-04-26T10:35:00Z"


def make_settings(tmp_path) -> Settings:
    return Settings(snapshot_path=str(tmp_path / "snap.json"),
                    snapshot_interval_s=3600, disable_llm=True,
                    artifacts_dir=str(tmp_path / "artifacts"))


@pytest.fixture()
def client(tmp_path):
    from fastapi.testclient import TestClient
    app = create_app(make_settings(tmp_path))
    with TestClient(app) as tc:
        yield tc


CATEGORY = {
    "slug": "dentists",
    "display_name": "Dentists",
    "voice": {"tone": "peer_clinical", "vocab_allowed": ["fluoride varnish", "caries", "recall"],
              "taboos": ["cure", "guaranteed"]},
    "offer_catalog": [{"id": "den_001", "title": "Dental Cleaning @ ₹299", "value": "299"}],
    "peer_stats": {"avg_rating": 4.4, "avg_reviews": 62, "avg_ctr": 0.030},
    "digest": [{"id": "d_2026W17_jida_fluoride", "kind": "research",
                "title": "3-month fluoride recall cuts caries recurrence 38% better than 6-month",
                "source": "JIDA Oct 2026, p.14", "trial_n": 2100,
                "patient_segment": "high_risk_adults"}],
    "patient_content_library": [],
    "seasonal_beats": [{"month_range": "Nov-Feb", "note": "exam-stress bruxism spike"}],
    "trend_signals": [{"query": "clear aligners delhi", "delta_yoy": 0.62}],
    "professional_journals": ["JIDA"],
    "regulatory_authorities": ["DCI"],
}

MERCHANT = {
    "merchant_id": "m_001_drmeera_dentist_delhi",
    "category_slug": "dentists",
    "identity": {"name": "Dr. Meera's Dental Clinic", "city": "Delhi",
                 "locality": "Lajpat Nagar", "verified": True,
                 "languages": ["en", "hi"], "owner_first_name": "Meera"},
    "subscription": {"status": "active", "plan": "Pro", "days_remaining": 82},
    "performance": {"window_days": 30, "views": 2410, "calls": 18, "directions": 45,
                    "ctr": 0.021, "leads": 11,
                    "delta_7d": {"views_pct": 0.18, "calls_pct": -0.05}},
    "offers": [{"id": "o_meera_001", "title": "Dental Cleaning @ ₹299", "status": "active"},
               {"id": "o_meera_002", "title": "Deep Cleaning @ ₹499", "status": "expired"}],
    "conversation_history": [],
    "customer_aggregate": {"total_unique_ytd": 540, "lapsed_180d_plus": 78,
                           "retention_6mo_pct": 0.38, "high_risk_adult_count": 124},
    "signals": ["stale_posts:22d", "ctr_below_peer_median", "high_risk_adult_cohort"],
    "review_themes": [],
}


def trigger(tid="trg_001_research_digest_dentists", kind="research_digest",
            mid=MERCHANT["merchant_id"], cid=None, urgency=2,
            sk="research:dentists:2026-W17"):
    if kind.startswith("research"):
        payload = {"category": "dentists",
                   "top_item_id": "d_2026W17_jida_fluoride"}
    elif kind == "perf_spike":
        payload = {"metric": "views"}
    elif kind == "perf_dip":
        payload = {"metric": "calls"}
    else:
        payload = {"note": "worth surfacing"}
    return {
        "id": tid, "scope": "customer" if cid else "merchant", "kind": kind,
        "source": "external" if ("research" in kind or "festival" in kind) else "internal",
        "merchant_id": mid, "customer_id": cid,
        "payload": payload,
        "urgency": urgency, "suppression_key": sk,
        "expires_at": "2026-05-03T00:00:00Z",
    }


def push_base(tc):
    assert tc.post("/v1/context", json={"scope": "category", "context_id": "dentists",
                                        "version": 1, "payload": CATEGORY,
                                        "delivered_at": NOW}).status_code == 200
    r = tc.post("/v1/context", json={"scope": "merchant",
                                     "context_id": MERCHANT["merchant_id"],
                                     "version": 1, "payload": MERCHANT,
                                     "delivered_at": NOW})
    assert r.status_code == 200
    return r.json()


def push_trigger(tc, trg, version=1):
    r = tc.post("/v1/context", json={"scope": "trigger", "context_id": trg["id"],
                                     "version": version, "payload": trg,
                                     "delivered_at": NOW})
    assert r.status_code == 200, r.text
    return r.json()
