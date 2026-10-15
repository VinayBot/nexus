"""The live demo-service: a git repo under ``data/demo-live`` served by uvicorn --reload.

* Chaos switches inject *real* bugs by editing the live source (each ring starts
  from the ``baseline`` tag, then applies every enabled switch).
* The Self-Healing executor applies a fix on a ``nexus/fix-<mission>`` branch and
  checks it out (uvicorn reloads); rollback checks the previous ref out again;
  a verified fix is fast-forwarded into ``main``.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import shutil
import sys
from dataclasses import dataclass
from typing import Any

import httpx

from nexus.core.config import PROJECT_ROOT, Settings
from nexus.core.event_types import ChaosToggled
from nexus.core.events import emit
from nexus.core.logging import get_logger
from nexus.core.workspace import IGNORE

log = get_logger(__name__)
SOURCE = PROJECT_ROOT / "demo-service"


@dataclass(frozen=True)
class ChaosSwitch:
    id: str
    title: str
    symptom: str
    file: str
    search: str
    replace: str


SWITCHES: dict[str, ChaosSwitch] = {
    s.id: s
    for s in [
        ChaosSwitch(
            "null_handling",
            "Null-handling bug",
            "Guest orders (no email) crash the pipeline",
            "app/orders.py",
            '    email = (order.get("email") or "").strip().lower()',
            '    email = order.get("email").strip().lower()',
        ),
        ChaosSwitch(
            "off_by_one",
            "Off-by-one bug",
            "Pagination silently drops the last order of each page",
            "app/orders.py",
            "    return items[start:end]",
            "    return items[start : end - 1]",
        ),
        ChaosSwitch(
            "bad_config",
            "Bad config value",
            "Tax rate entered as a percent: totals explode",
            "app/config.py",
            "TAX_RATE = 0.08  # fraction, not percent",
            "TAX_RATE = 8  # fraction, not percent",
        ),
        ChaosSwitch(
            "slow_dependency",
            "Slow dependency",
            "Inventory calls exceed their timeout",
            "app/inventory.py",
            "SIMULATED_LATENCY_S = 0.02",
            "SIMULATED_LATENCY_S = 1.5",
        ),
        ChaosSwitch(
            "schema_mismatch",
            "Schema mismatch",
            "Producer renamed price → unit_price",
            "app/pipeline.py",
            '"items": [{"sku": sku, "price": price, "qty": 1 + n % 3}],',
            '"items": [{"sku": sku, "unit_price": price, "qty": 1 + n % 3}],',
        ),
    ]
}


class DemoService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.live = settings.data_dir / "demo-live"
        self.state_file = settings.data_dir / "chaos.json"
        self.port = settings.demo_service_port
        self.url = f"http://127.0.0.1:{self.port}"
        self._proc: asyncio.subprocess.Process | None = None
        self._lock = asyncio.Lock()

    # -- git ----------------------------------------------------------------------------
    async def git(self, *args: str, check: bool = True) -> str:
        proc = await asyncio.create_subprocess_exec(
            "git", "-c", "user.name=NEXUS", "-c", "user.email=nexus@nexus.local", *args,
            cwd=self.live, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
        )  # fmt: skip
        out, _ = await proc.communicate()
        text = out.decode(errors="replace").strip()
        if check and proc.returncode != 0:
            raise RuntimeError(f"git {' '.join(args)} failed: {text}")
        return text

    async def ensure_repo(self) -> None:
        if (self.live / ".git").exists():
            return
        if self.live.exists():
            shutil.rmtree(self.live)
        shutil.copytree(SOURCE, self.live, ignore=IGNORE)
        await self.git("init", "-q", "-b", "main")
        await self.git("add", "-A")
        await self.git("commit", "-q", "-m", "baseline")
        await self.git("tag", "baseline")

    # -- process ------------------------------------------------------------------------
    async def start(self) -> None:
        await self.ensure_repo()
        if self._proc and self._proc.returncode is None:
            return
        logf = (self.settings.data_dir / "demo-service.log").open("ab")
        self._proc = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1",
            "--port", str(self.port), "--reload", "--reload-dir", "app", "--log-level", "warning",
            cwd=self.live, stdout=logf, stderr=logf,
        )  # fmt: skip
        log.info("demo_service.started", port=self.port, pid=self._proc.pid)

    async def stop(self) -> None:
        if self._proc and self._proc.returncode is None:
            self._proc.terminate()
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(self._proc.wait(), 5)
            if self._proc.returncode is None:
                self._proc.kill()

    async def health(self) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=2) as c:
                r = await c.get(f"{self.url}/health")
                return dict(r.json())
        except httpx.HTTPError as exc:
            return {"status": "down", "error_rate": 1.0, "latency_ms": None, "error": str(exc)}

    async def logs(self, limit: int = 60, level: str | None = None) -> list[dict[str, Any]]:
        try:
            async with httpx.AsyncClient(timeout=2) as c:
                r = await c.get(
                    f"{self.url}/logs",
                    params={"limit": limit, **({"level": level} if level else {})},
                )
                return list(r.json())
        except httpx.HTTPError:
            return []

    async def metrics(self) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=2) as c:
                return dict((await c.get(f"{self.url}/metrics")).json())
        except httpx.HTTPError:
            return {}

    # -- chaos ---------------------------------------------------------------------------
    def enabled(self) -> list[str]:
        if not self.state_file.exists():
            return []
        return [s for s in json.loads(self.state_file.read_text()) if s in SWITCHES]

    async def set_switch(self, switch_id: str, on: bool) -> list[str]:
        if switch_id not in SWITCHES:
            raise KeyError(switch_id)
        async with self._lock:
            enabled = set(self.enabled())
            enabled = enabled | {switch_id} if on else enabled - {switch_id}
            await self._rebuild(sorted(enabled))
        emit("chaos.toggled", ChaosToggled(switch=switch_id, enabled=on))
        return sorted(enabled)

    async def reset(self) -> None:
        async with self._lock:
            await self._rebuild([])
        emit("chaos.toggled", ChaosToggled(switch="all", enabled=False))

    async def _rebuild(self, enabled: list[str]) -> None:
        await self.ensure_repo()
        await self.git("checkout", "-q", "-f", "main")
        await self.git("reset", "-q", "--hard", "baseline")
        for branch in (await self.git("branch", "--list", "nexus/*")).split():
            if branch.startswith("nexus/"):
                await self.git("branch", "-q", "-D", branch, check=False)
        for sid in enabled:
            sw = SWITCHES[sid]
            path = self.live / sw.file
            text = path.read_text()
            if sw.search not in text:
                raise RuntimeError(f"chaos {sid}: target code not found in {sw.file}")
            path.write_text(text.replace(sw.search, sw.replace, 1))
        if enabled:
            await self.git("commit", "-q", "-am", f"chaos: {', '.join(enabled)}")
        self.state_file.write_text(json.dumps(enabled))
        log.info("chaos.rebuilt", enabled=enabled)

    # -- fixes ---------------------------------------------------------------------------
    async def current_ref(self) -> str:
        return await self.git("rev-parse", "--abbrev-ref", "HEAD")

    async def apply_fix(
        self, mission_id: str, file: str, content: str, message: str
    ) -> dict[str, str]:
        async with self._lock:
            previous = await self.current_ref()
            branch = f"nexus/fix-{mission_id}"
            await self.git("checkout", "-q", "-B", branch)
            target = (self.live / file).resolve()
            if self.live.resolve() not in target.parents:
                raise PermissionError(f"{file} is outside the service")
            target.write_text(content)
            await self.git("commit", "-q", "-am", message)
            sha = await self.git("rev-parse", "--short", "HEAD")
        return {"branch": branch, "previous": previous, "commit": sha}

    async def rollback(self, previous: str, branch: str) -> None:
        async with self._lock:
            await self.git("checkout", "-q", "-f", previous)
            await self.git("branch", "-q", "-D", branch, check=False)

    async def promote(self, branch: str) -> None:
        async with self._lock:
            await self.git("checkout", "-q", "main")
            await self.git("merge", "-q", "--ff-only", branch)
            await self.git("branch", "-q", "-d", branch, check=False)

    def read(self, file: str) -> str:
        return (self.live / file).read_text()
