"""Artifact logging (docs/2. TechSpec.md §12) — mirrors the harness's own
per-team bundle so local debugging aligns with what judges receive:

    data/artifacts/conversations.jsonl    every /v1/reply turn + bot action
    data/artifacts/context_pushes.jsonl   every push + ack/stale decision
    data/artifacts/healthz.jsonl          every poll with derived counts

Append-only JSONL, crash-safe (open/append/close per line). Teardown logs the
wipe event and rotates the files so re-runs start clean.
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ArtifactsLogger:
    FILES = ("conversations.jsonl", "context_pushes.jsonl", "healthz.jsonl")

    def __init__(self, artifacts_dir: str) -> None:
        self.dir = Path(artifacts_dir)
        self.enabled = True

    def _write(self, fname: str, record: dict) -> None:
        if not self.enabled:
            return
        try:
            self.dir.mkdir(parents=True, exist_ok=True)
            record = {"ts": _now(), **record}
            with open(self.dir / fname, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
        except OSError:
            pass                                   # logging must never break serving

    # -- public API ---------------------------------------------------------
    def conversation_turn(self, conversation_id: str, from_role: str,
                          message: str, classification: str | None,
                          bot_action: dict | None) -> None:
        self._write("conversations.jsonl", {
            "event": "turn", "conversation_id": conversation_id,
            "from_role": from_role, "message": message,
            "classification": classification, "bot_action": bot_action})

    def context_push(self, scope: str, context_id: str, version: int,
                     outcome: str, detail: dict | None = None) -> None:
        self._write("context_pushes.jsonl", {
            "event": "push", "scope": scope, "context_id": context_id,
            "version": version, "outcome": outcome, "detail": detail or {}})

    def healthz(self, counts: dict, uptime_seconds: int) -> None:
        self._write("healthz.jsonl", {
            "event": "healthz", "counts": counts, "uptime_seconds": uptime_seconds})

    def tick_summary(self, available: int, emitted: int) -> None:
        self._write("conversations.jsonl", {
            "event": "tick", "available_triggers": available, "actions_emitted": emitted})

    def wipe_event(self, cleared: list[str]) -> None:
        for fname in self.FILES:
            self._write(fname, {"event": "teardown", "cleared": cleared})

    def wipe_files(self) -> list[str]:
        removed = []
        for fname in self.FILES:
            p = self.dir / fname
            if p.exists():
                try:
                    os.remove(p)
                    removed.append(fname)
                except OSError:
                    pass
        return removed
