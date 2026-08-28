"""Sutra — magicpin AI Challenge bot (docs/2. TechSpec.md is the spec).

Run:  uvicorn bot:app --host 0.0.0.0 --port 8080
"""
import asyncio
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone as _tz

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from composer.pipeline import Composer
from composer.router import canon_kind
from config import Settings
from llm.client import LLMClient
from llm.ledger import Ledger
from reply.classifier import classify
from reply.state_machine import decide
from schemas import enums as E
from schemas.pydantic_models import (
    ContextAck, ContextPushIn, ContextReject, EndOut, ReplyIn,
    SendOut, TeardownOut, TickIn, TickOut, WaitOut,
)
from stores.conversation_store import ConversationState, ConversationStore, parse_dt
from stores.context_store import ContextStore
from stores.artifacts import ArtifactsLogger
from stores.snapshot import SnapshotManager
from stores.suppression import Registries, body_hash, consent_allows

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("sutra")


E_TZ = _tz.utc


class SutraState:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or Settings()
        self.started_at = datetime.now(E_TZ)
        self.contexts = ContextStore()
        self.conversations = ConversationStore()
        self.registries = Registries()
        self.ledger = Ledger(self.settings.spend_soft_usd, self.settings.spend_hard_usd)
        self.llm = LLMClient(self.settings, self.ledger)
        self.composer = Composer(self.contexts, self.registries, self.llm, self.settings)
        self.artifacts = ArtifactsLogger(self.settings.artifacts_dir)
        self.snapshot = SnapshotManager(
            self.settings.snapshot_path, self._snapshot_payload,
            self.settings.snapshot_interval_s)

    # -- persistence --------------------------------------------------------
    def _snapshot_payload(self) -> dict:
        return {
            "contexts": self.contexts.to_dict(),
            "conversations": self.conversations.to_dict(),
            "registries": self.registries.to_dict(),
            "started_at": self.started_at.isoformat(),
        }

    def recover(self) -> bool:
        data = self.snapshot.load()
        if not data:
            return False
        try:
            self.contexts.load_dict(data.get("contexts", {}))
            self.conversations.load_dict(data.get("conversations", {}))
            self.registries.load_dict(data.get("registries", {}))
            log.info("state recovered from disk snapshot")
            return True
        except Exception:                                    # noqa: BLE001
            log.exception("snapshot recovery failed; starting clean")
            return False

    def wipe(self) -> list[str]:
        cleared = ["context_store", "conversation_store", "suppression_registries",
                   "response_cache", "fresh_context_registry"]
        self.contexts.wipe()
        self.conversations.wipe()
        self.registries.wipe()
        self.composer.cache.wipe()
        return cleared


def create_app(settings: Settings | None = None) -> FastAPI:
    st = SutraState(settings)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        st.recover()
        st.snapshot.start()
        yield
        await st.snapshot.stop()

    app = FastAPI(title="Sutra", version=st.settings.version, lifespan=lifespan)

    # ------------------------------------------------------------- healthz
    @app.get("/v1/healthz")
    async def healthz():
        counts = st.contexts.counts()
        uptime = int((datetime.now(E_TZ) - st.started_at).total_seconds())
        st.artifacts.healthz(counts, uptime)
        return {"status": "ok", "uptime_seconds": uptime, "contexts_loaded": counts}

    # ------------------------------------------------------------ metadata
    @app.get("/v1/metadata")
    async def metadata():
        s = st.settings
        return {"team_name": s.team_name, "team_members": s.team_members,
                "model": (f"Groq {s.primary_model} (primary) → OpenRouter "
                          f"{s.secondary_model} (fallback) → deterministic templates"
                          if s.llm_enabled else "deterministic templates (LLM disabled)"),
                "approach": ("Hybrid deterministic-guardrail composer: routed LLM core + "
                             "facts-registry validation gate + three-tier fallback + "
                             "reply state machine"),
                "contact_email": s.contact_email, "version": s.version}

    # ------------------------------------------------------------- context
    MAX_PAYLOAD_BYTES = 500_000

    @app.post("/v1/context")
    async def push_context(body: ContextPushIn):
        raw = body.model_dump_json()
        if len(raw.encode("utf-8")) > MAX_PAYLOAD_BYTES:
            return JSONResponse(status_code=400, content=ContextReject(
                reason="payload_too_large", max_bytes=MAX_PAYLOAD_BYTES
            ).model_dump(exclude_none=True))
        status, prev = st.contexts.put(body.scope, body.context_id, body.version,
                                       body.payload, body.delivered_at)
        stored_at = datetime.now(E_TZ).isoformat()
        if status == "invalid":
            st.artifacts.context_push(body.scope, body.context_id, body.version, "invalid_scope")
            return JSONResponse(status_code=400, content=ContextReject(
                reason="invalid_scope", details=f"scope={body.scope}"
            ).model_dump(exclude_none=True))
        if status == "stale":
            st.artifacts.context_push(body.scope, body.context_id, body.version,
                                      "stale_version", {"current_version": prev["version"]})
            return JSONResponse(status_code=409, content=ContextReject(
                reason="stale_version", current_version=prev["version"]
            ).model_dump(exclude_none=True))
        st.artifacts.context_push(body.scope, body.context_id, body.version,
                                  "stored", {"replaced": bool(prev)})
        from composer.facts_registry import diff_facts
        new_tokens = diff_facts(prev["payload"] if prev else None, body.payload)
        st.registries.mark_fresh(body.scope, body.context_id, body.version, new_tokens)
        ack_id = f"ack_{body.context_id}_v{body.version}"
        return ContextAck(ack_id=ack_id, stored_at=stored_at).model_dump()

    # ----------------------------------------------------------------- tick
    def _rank_key(trg: dict, mid: str):
        urgency = trg.get("urgency") or 1
        fresh = 1.5 if st.registries.has_pending([("trigger", trg.get("id")),
                                                  ("merchant", mid)]) else 1.0
        merchant = st.contexts.get("merchant", mid) or {}
        priority = 1.2 if ((merchant.get("identity") or {}).get("verified")) else 1.0
        return urgency * fresh * priority, mid          # mid tiebreak → determinism

    @app.post("/v1/tick")
    async def tick(body: TickIn):
        now = parse_dt(body.now) or datetime.now(E_TZ)
        candidates = []
        for tid in body.available_triggers:
            trec = st.contexts.get_record("trigger", tid)
            if not trec:
                continue
            trg = trec["payload"]
            # NOTE: `available_triggers` is the judge's own "active right now"
            # list (testing-brief §2.2) — it already filters expired/stale
            # triggers, so re-checking expires_at here only double-filters and
            # can suppress valid seeds whose dates are older than the host clock.
            mid = trg.get("merchant_id") or ""
            if not st.contexts.get("merchant", mid):
                continue
            sk = trg.get("suppression_key") or ""
            kind = trg.get("kind", "")
            if sk and st.registries.seen_suppression(mid, sk):
                continue
            # urgency ranks (see _rank_key) rather than hard-blocks; every valid
            # event is worth sending once (topic/suppression dedup prevents spam)
            # FR-21: consent scope gates every customer-facing send
            customer_id = trg.get("customer_id")
            if customer_id:
                cust = st.contexts.get("customer", customer_id) or {}
                canon = canon_kind(kind)
                if not consent_allows(canon,
                                      (cust.get("consent") or {}).get("scope")):
                    log.info("consent-blocked %s for %s", tid, customer_id)
                    continue
            if any(c.in_wait(now) for c in st.conversations.all() if c.merchant_id == mid):
                continue
            candidates.append((tid, trg, mid, kind))

        # deterministic ordering: rank desc, then merchant_id, then trigger_id
        candidates.sort(key=lambda c: (-_rank_key(c[1], c[2])[0], c[2], c[0]))
        selected = candidates[: max(3, min(st.settings.top_k_per_tick, len(candidates)))]
        if not selected:
            return TickOut(actions=[]).model_dump()

        tasks = []
        sem = asyncio.Semaphore(5)
        for (tid, trg, mid, kind) in selected:
            customer_id = trg.get("customer_id")
            conv_id = st.conversations.new_conversation_id(mid, kind)
            st.conversations.create(ConversationState(
                conversation_id=conv_id, merchant_id=mid, customer_id=customer_id,
                send_as=E.SEND_AS_MERCHANT_ON_BEHALF if trg.get("scope") == "customer"
                        else E.SEND_AS_VERA,
                language=_language_for(st, mid, customer_id),
                trigger_kind=canon_kind(kind)))
            freeform = st.registries.replied_within(mid, hours=24, now=now)  # FR-12
            tasks.append(asyncio.ensure_future(
                _bounded_compose(st, sem, now=now, merchant_id=mid,
                                 trigger_id=tid, conversation_id=conv_id,
                                 customer_id=customer_id, session_freeform=freeform)))

        done, pending = await asyncio.wait(tasks, timeout=st.settings.tick_deadline_s)
        for t in pending:
            t.cancel()

        actions = []
        for t in done:
            result = t.result() if not t.cancelled() else None
            if result is None:
                continue
            action, meta = result
            # topic dedup happens HERE, on the composer's real signal id
            if st.registries.seen_topic(action.merchant_id,
                                        canon_kind(meta["kind"]),
                                        str(meta["signal_id"])):
                cstate = st.conversations.get(action.conversation_id)
                if cstate:
                    cstate.ended = True
                    cstate.ended_reason = "topic_duplicate"
                continue
            actions.append(action)
            st.registries.clear_fresh("trigger", action.trigger_id)
            st.registries.register_action(
                merchant_id=action.merchant_id, conv_id=action.conversation_id,
                suppression_key=action.suppression_key,
                kind=canon_kind(meta["kind"]), signal_id=str(meta["signal_id"]),
                body=action.body)
        actions = actions[: st.settings.max_actions_per_tick]
        st.artifacts.tick_summary(len(body.available_triggers), len(actions))
        return TickOut(actions=actions).model_dump()

    # ---------------------------------------------------------------- reply
    @app.post("/v1/reply")
    async def reply(body: ReplyIn):
        state = st.conversations.get(body.conversation_id)
        mid = body.merchant_id or (state.merchant_id if state else "")
        customer_id = body.customer_id or (state.customer_id if state else None)
        language = _language_for(st, mid, customer_id)
        if state is None:
            state = st.conversations.get_or_create(
                body.conversation_id, merchant_id=mid, customer_id=customer_id,
                send_as=E.SEND_AS_MERCHANT_ON_BEHALF if body.from_role == "customer"
                        else E.SEND_AS_VERA, language=language)
        if state.ended:
            return EndOut(rationale="Conversation already closed.").model_dump()

        klass = classify(body.message, state)
        state.turns.append({"from_role": body.from_role, "message": body.message,
                            "received_at": body.received_at, "classification": klass})
        if body.from_role == "merchant":
            st.registries.note_merchant_reply(
                state.merchant_id, parse_dt(body.received_at) or datetime.now(E_TZ))
        response = decide(klass, state, language=language,
                          turn_number=body.turn_number,
                          now=parse_dt(body.received_at))
        state.turns[-1]["bot_action"] = response["action"]
        st.artifacts.conversation_turn(
            body.conversation_id, body.from_role, body.message, klass, response)
        if response["action"] == E.ACTION_SEND:
            state.body_hashes.add(body_hash(response["body"]))
        if response["action"] == E.ACTION_WAIT:
            return WaitOut(wait_seconds=int(response.get("wait_seconds", 1800)),
                           rationale=response["rationale"]).model_dump()
        if response["action"] == E.ACTION_END:
            return EndOut(rationale=response["rationale"]).model_dump()
        return SendOut(body=response["body"], cta=response.get("cta", E.CTA_OPEN_ENDED),
                       rationale=response["rationale"]).model_dump()

    # ------------------------------------------------------------- teardown
    @app.post("/v1/teardown")
    async def teardown():
        cleared = st.wipe()
        removed = st.artifacts.wipe_files()
        st.artifacts.wipe_event(cleared + removed)
        return TeardownOut(wiped_at=datetime.now(E_TZ).isoformat(),
                           stores_cleared=cleared + removed).model_dump()

    # ---------------------------------------------------------- debug root
    @app.get("/")
    async def root():
        return {"service": "sutra",
                "endpoints": ["/v1/healthz", "/v1/metadata", "/v1/context",
                              "/v1/tick", "/v1/reply", "/v1/teardown"],
                "llm_mode": "enabled" if st.settings.llm_enabled else "template-only"}

    app.state.sutra = st
    return app


# ------------------------------------------------------------------ utils --
def _language_for(st: SutraState, merchant_id: str, customer_id: str | None) -> str:
    cust = st.contexts.get("customer", customer_id) if customer_id else None
    if cust:
        pref = ((cust.get("identity") or {}).get("language_pref")) or "en"
    else:
        m = st.contexts.get("merchant", merchant_id) or {}
        langs = (m.get("identity") or {}).get("languages") or ["en"]
        pref = langs[0] if langs else "en"
    if pref.startswith("hi"):
        return "hi-en mix" if "mix" in pref or "en" in pref else "hi"
    return "en"


async def _bounded_compose(st: SutraState, sem: asyncio.Semaphore, **kwargs):
    async with sem:
        try:
            result = await asyncio.wait_for(
                st.composer.compose(**kwargs),
                timeout=max(5.0, st.settings.tick_deadline_s - 2))
            return result                                    # (TickActionOut, meta) | None
        except Exception:                                    # noqa: BLE001
            log.exception("compose failed for %s", kwargs.get("trigger_id"))
            return None


app = create_app()
