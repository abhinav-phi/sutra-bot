"""Crash-safe disk snapshot every N seconds; recover on startup (ADR-06/W4)."""
import asyncio
import json
import os
from pathlib import Path


class SnapshotManager:
    def __init__(self, path: str, state_provider, interval_s: int = 30) -> None:
        self.path = Path(path)
        self.state_provider = state_provider      # callable -> serializable dict
        self.interval_s = max(5, int(interval_s))
        self._task: asyncio.Task | None = None

    def save_sync(self) -> None:
        data = self.state_provider()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, self.path)               # atomic on POSIX & Windows

    async def _loop(self) -> None:
        while True:
            await asyncio.sleep(self.interval_s)
            try:
                await asyncio.to_thread(self.save_sync)
            except Exception:
                continue

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.ensure_future(self._loop())

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            self._task = None
            try:
                await asyncio.sleep(0)
            except Exception:
                pass
        try:
            await asyncio.to_thread(self.save_sync)
        except Exception:
            pass

    def load(self) -> dict | None:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return None
