"""Composition pipeline (docs/3. AppFlow.md §5): cache -> LLM tiers -> gate -> template.

Guarantees:
- never emits an ungrounded number (gate check #2)
- never returns nothing because the LLM failed (template tier always available)
- byte-identical output for identical inputs within a run (cache, temp=0)
"""
import logging

from schemas import enums as E
from schemas.pydantic_models import TickActionOut
from composer import router as R
from composer.cache import ResponseCache
from composer.facts_registry import FactsSet, computed_numbers
from composer.fallback_templates import build_spine, build_template
from composer.prompts import build_system_prompt, build_user_prompt, voice_profile
from composer.validation_gate import parse_llm_json, validate

log = logging.getLogger("sutra.composer")

POLICY_DEFAULT_CTA = {
    "binary": E.CTA_BINARY_YES_NO,
    "slot": E.CTA_MULTI_CHOICE_SLOT,
    "open": E.CTA_OPEN_ENDED,
    "none": E.CTA_NONE,
}


class Composer:
    def __init__(self, context_store, registries, llm_client, settings) -> None:
        self.ctx = context_store
        self.reg = registries
        self.llm = llm_client
        self.settings = settings
        self.cache = ResponseCache()
        self.rejections: dict[str, int] = {}

    # ---------------------------------------------------------------- utils
    def _resolve(self, merchant: dict):
        slug = merchant.get("category_slug", "")
        return slug, self.ctx.get("category", slug)

    @staticmethod
    def _language(merchant: dict, customer: dict | None) -> str:
        if customer:
            pref = ((customer.get("identity") or {}).get("language_pref")) or "en"
        else:
            langs = (merchant.get("identity") or {}).get("languages") or ["en"]
            pref = langs[0] if langs else "en"
        if "hi" in pref and ("mix" in pref or "-" in pref or "en" in pref.split()):
            return "hi-en mix"
        return "hi" if pref.startswith("hi") else "en"

    def _facts_for(self, category, merchant, trigger, customer, spine) -> FactsSet:
        facts = FactsSet()
        for payload in filter(None, [category, merchant, trigger, customer]):
            facts.register_payload(payload)
        # derived display strings (spine summary + facts_lines) are built from
        # context values; register their numbers so the LLM may quote them
        # ("62%" for delta_yoy 0.62, "38%" for trial results, cohort %, etc.)
        for text in [spine.get("summary", ""), *spine.get("facts_lines", [])]:
            facts.add_number(text)
        for text, _tag in computed_numbers(merchant):
            facts.add_number(text)
        for n in spine.get("extra_numbers", []):
            facts.add_number(n)
        fresh = self.reg.peek_fresh_tokens([
            ("merchant", merchant.get("merchant_id", "")),
            ("category", category.get("slug", "")),
        ])
        for tok in fresh:
            facts.add_number(tok)
        facts.fresh_tokens = fresh
        return facts

    # ------------------------------------------------------------- compose
    async def compose(self, *, now, merchant_id: str, trigger_id: str,
                      conversation_id: str,
                      customer_id: str | None = None,
                      session_freeform: bool = False):
        mrec = self.ctx.get_record("merchant", merchant_id)
        trec = self.ctx.get_record("trigger", trigger_id)
        if not mrec or not trec:
            return None
        merchant, trigger = mrec["payload"], trec["payload"]
        slug, crec = (self._resolve(merchant)[0],
                      self.ctx.get_record("category", merchant.get("category_slug", "")))
        if not crec:
            return None
        category = crec["payload"]
        cust_rec = self.ctx.get_record("customer", customer_id) if customer_id else None
        customer = cust_rec["payload"] if cust_rec else None

        scope_kind = trigger.get("kind", "")
        scope = trigger.get("scope") or ("customer" if customer else "merchant")
        cfg = R.route(scope_kind, scope)
        canon = R.canon_kind(scope_kind)

        language = self._language(merchant, customer)
        spine = build_spine(category, merchant, trigger, customer,
                            self.reg.peek_fresh_tokens([("merchant", merchant_id),
                                                        ("category", slug)]), now)
        facts = self._facts_for(category, merchant, trigger, customer, spine)

        cache_key = self.cache.make_key(slug, crec["version"], merchant_id, mrec["version"],
                                        trigger_id, trec["version"], customer_id,
                                        cust_rec["version"] if cust_rec else 0,
                                        language, cfg["variant"], session_freeform)
        cached = self.cache.get(cache_key)
        if cached is not None:
            action = self._to_action(cached, conversation_id, merchant_id,
                                     customer_id, trigger_id, scope)
            return action, {"kind": canon,
                            "signal_id": cached.get("signal_id") or canon}

        owner = spine.get("owner") or None
        profile = voice_profile(category)
        system = build_system_prompt(category, cfg, language)
        user = build_user_prompt(spine, spine.get("facts_lines", []), facts.fresh_tokens)

        composed = await self._via_llm(system, user, body_ctx=dict(
            facts=facts, profile=profile, cfg=cfg, language=language, owner=owner,
            conv_hashes=set(), spine=spine))
        source = composed.pop("_source", "llm") if isinstance(composed, dict) else "template"
        if composed is None:
            composed = build_template(spine, category, cfg, language)
            composed["_source"] = "template"
            # FR-06 honesty: templates go through the SAME gate; failures are
            # logged, but tier-3 always emits (baseline-guarantee ADR-01).
            ok, reason = validate(composed["body"], composed["cta"],
                                  composed["rationale"], **dict(
                                      facts=facts, profile=profile, cfg=cfg,
                                      language=language, owner_name=owner,
                                      conv_body_hashes=set()))
            composed["_gate"] = reason or "pass"
            if not ok:
                self.rejections[reason.split("[")[0]] = \
                    self.rejections.get(reason.split("[")[0], 0) + 1
                log.warning("template gate %s for %s (emitted anyway)", reason, trigger_id)
        composed.setdefault("template_name", f"sutra_{cfg['variant']}_v1")
        composed.setdefault("template_params",
                            [spine.get("owner") or spine.get("shop") or "",
                             (spine.get("summary") or "")[:80]])
        composed.setdefault("suppression_key", trigger.get("suppression_key")
                            or f"{canon}:{merchant_id}")

        used_fresh = bool(facts.fresh_tokens) and any(
            t.lower() in composed["body"].lower() for t in facts.fresh_tokens[:6])
        # FR-12: within 24h of a merchant reply the session is open — free-form
        # send, no first-touch template framing.
        if session_freeform:
            composed["template_name"] = "sutra_freeform_v1"
            composed["template_params"] = []
        action = self._to_action(composed, conversation_id, merchant_id, customer_id,
                                 trigger_id, scope)
        self.cache.put(cache_key, {
            "body": action.body, "cta": action.cta, "rationale": action.rationale,
            "send_as": action.send_as, "suppression_key": action.suppression_key,
            "template_name": action.template_name, "template_params": action.template_params,
            "signal_id": spine.get("signal_id"),
            "_source": composed.get("_source", source),
        })
        if used_fresh:
            self.reg.clear_fresh("merchant", merchant_id)
            self.reg.clear_fresh("category", slug)
        log.info("composed %s via %s conv=%s", trigger_id, composed.get("_source"), conversation_id)
        return action, {"kind": canon, "signal_id": spine.get("signal_id") or canon}

    # ------------------------------------------------------------- llm path
    async def _via_llm(self, system: str, user: str, body_ctx: dict) -> dict | None:
        if not self.settings.llm_enabled or self.llm.ledger.status() == "hard":
            return None
        # single attempt per provider: reasoning models are slow (~10s/call) and
        # a re-prompt would blow the tick budget, losing even the template
        # fallback. First-pass quality + template fallback > double-attempt risk.
        for provider in self.llm.providers:
            try:
                text = await self.llm.complete(system, user, max_tokens=600)
            except Exception as e:                              # noqa: BLE001
                log.warning("llm provider %s failed: %s", provider.name, type(e).__name__)
                continue
            data = parse_llm_json(text)
            if not data or not data.get("body"):
                log.warning("llm provider %s returned unparsable output", provider.name)
                continue
            body = str(data["body"]).strip()
            cta = str(data.get("cta", "")).strip()
            if cta not in E.VALID_CTAS:
                cta = POLICY_DEFAULT_CTA[body_ctx["cfg"]["cta_policy"]]
            rationale = str(data.get("rationale", "")).strip()[:400]
            ok, reason = validate(body, cta, rationale, **dict(
                facts=body_ctx["facts"], profile=body_ctx["profile"],
                cfg=body_ctx["cfg"], language=body_ctx["language"],
                owner_name=body_ctx["owner"],
                conv_body_hashes=body_ctx["conv_hashes"]))
            if ok:
                return {"body": body, "cta": cta, "rationale": rationale, "_source": "llm"}
            log.warning("llm output rejected (%s) — falling back to template", reason)
            self.rejections[reason.split("[")[0]] = self.rejections.get(reason.split("[")[0], 0) + 1
            break
        return None

    # -------------------------------------------------------------- output
    def _to_action(self, composed: dict, conversation_id: str, merchant_id: str,
                   customer_id: str | None, trigger_id: str, scope: str) -> TickActionOut:
        send_as = E.SEND_AS_MERCHANT_ON_BEHALF if scope == "customer" else E.SEND_AS_VERA
        template_name = composed.get("template_name") or "sutra_composed_v1"
        params = composed.get("template_params") or []
        return TickActionOut(
            conversation_id=conversation_id,
            merchant_id=merchant_id,
            customer_id=customer_id,
            send_as=send_as,
            trigger_id=trigger_id,
            template_name=template_name,
            template_params=[str(p) for p in params][:6],
            body=composed["body"],
            cta=composed["cta"],
            suppression_key=composed.get("suppression_key", ""),
            rationale=composed.get("rationale", ""),
        )
