"""Isolated command / test execution.

The workspace is copied to a throwaway directory first, so a sandboxed run can
never modify the real workspace. With Docker available, the copy runs in the
``nexus-sandbox`` image with networking disabled, 1 CPU, 512 MB RAM and a hard
timeout. Without Docker it falls back to a local subprocess — clearly labelled
``local (not isolated)`` in every result so nobody mistakes it for a sandbox.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from nexus.core.logging import get_logger
from nexus.core.workspace import IGNORE

log = get_logger(__name__)


@dataclass
class SandboxResult:
    ok: bool
    exit_code: int
    backend: str
    duration_ms: float
    stdout: str = ""
    passed: int = 0
    failed: int = 0
    errors: int = 0
    skipped: int = 0
    failures: list[str] = field(default_factory=list)
    timed_out: bool = False

    def as_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["output"] = d.pop("stdout")[-4000:]
        d["summary"] = (
            f"{self.passed} passed, {self.failed} failed, {self.errors} errors"
            + (" (timed out)" if self.timed_out else "")
            + f" [{self.backend}]"
        )
        return d


def parse_junit(path: Path) -> tuple[int, int, int, int, list[str]]:
    if not path.exists():
        return 0, 0, 0, 0, []
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
    passed = failed = errors = skipped = 0
    failures: list[str] = []
    for suite in suites:
        for case in suite.iter("testcase"):
            name = f"{case.get('classname', '')}::{case.get('name', '')}"
            if case.find("failure") is not None:
                failed += 1
                msg = (case.find("failure").get("message") or "")[:200]  # type: ignore[union-attr]
                failures.append(f"{name}: {msg}")
            elif case.find("error") is not None:
                errors += 1
                failures.append(f"{name}: error")
            elif case.find("skipped") is not None:
                skipped += 1
            else:
                passed += 1
    return passed, failed, errors, skipped, failures


class SandboxRunner:
    def __init__(
        self,
        *,
        prefer: str = "docker",
        image: str = "nexus-sandbox:latest",
        network: bool = False,
        cpu: float = 1.0,
        memory: str = "512m",
    ) -> None:
        self.prefer = prefer
        self.image = image
        self.network = network
        self.cpu = cpu
        self.memory = memory
        self._docker: Any = None
        self._checked = False
        self.backend = "local (not isolated)"
        self.reason = ""

    def _detect(self) -> None:
        if self._checked:
            return
        self._checked = True
        if self.prefer != "docker":
            self.reason = "configured for local execution"
            return
        import docker

        try:
            client = docker.from_env(timeout=3)
            client.ping()
            client.images.get(self.image)
            self._docker = client
            self.backend = "docker"
        except (docker.errors.DockerException, OSError) as exc:
            self.reason = f"docker unavailable ({type(exc).__name__}: {str(exc)[:120]}); run `make sandbox-image`"
            log.warning("sandbox.local_fallback", reason=self.reason)

    async def status(self) -> dict[str, Any]:
        await asyncio.to_thread(self._detect)
        return {
            "backend": self.backend,
            "isolated": self.backend == "docker",
            "network": self.network if self.backend == "docker" else True,
            "limits": {"cpu": self.cpu, "memory": self.memory}
            if self.backend == "docker"
            else None,
            "reason": self.reason,
        }

    async def run(
        self,
        workspace: Path,
        command: list[str],
        *,
        files: dict[str, str] | None = None,
        timeout_s: float = 90.0,
    ) -> SandboxResult:
        await asyncio.to_thread(self._detect)
        tmp = Path(tempfile.mkdtemp(prefix="nexus-sbx-"))
        work = tmp / "work"
        try:
            shutil.copytree(workspace, work, ignore=IGNORE)
            for rel, content in (files or {}).items():
                target = (work / rel).resolve()
                if work.resolve() not in target.parents:
                    raise PermissionError(f"sandbox file {rel!r} escapes the workspace")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content)
            if self._docker is not None:
                return await asyncio.to_thread(self._run_docker, work, command, timeout_s)
            return await self._run_local(work, command, timeout_s)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    async def run_tests(
        self,
        workspace: Path,
        target: str = "tests",
        *,
        files: dict[str, str] | None = None,
        timeout_s: float = 90.0,
    ) -> SandboxResult:
        cmd = [
            "python", "-m", "pytest", "-q", "-p", "no:cacheprovider",
            "--junitxml=.junit.xml", "-o", "junit_family=xunit2", target,
        ]  # fmt: skip
        return await self.run(workspace, cmd, files=files, timeout_s=timeout_s)

    def _run_docker(self, work: Path, command: list[str], timeout_s: float) -> SandboxResult:
        import docker
        import requests

        started = time.perf_counter()
        container = self._docker.containers.run(
            self.image,
            command,
            volumes={str(work): {"bind": "/work", "mode": "rw"}},
            working_dir="/work",
            network_disabled=not self.network,
            mem_limit=self.memory,
            nano_cpus=int(self.cpu * 1e9),
            pids_limit=128,
            detach=True,
        )
        timed_out = False
        try:
            status = container.wait(timeout=timeout_s)
            code = int(status.get("StatusCode", 1))
        except (requests.exceptions.RequestException, docker.errors.APIError):  # wait() timed out
            timed_out = True
            code = 124
            container.kill()
        logs = container.logs(stdout=True, stderr=True).decode(errors="replace")
        container.remove(force=True)
        return self._result(work, code, logs, "docker", started, timed_out)

    async def _run_local(self, work: Path, command: list[str], timeout_s: float) -> SandboxResult:
        started = time.perf_counter()
        if command and command[0] == "python":
            command = [sys.executable, *command[1:]]
        env = {
            "PATH": os.environ.get("PATH", ""),
            "PYTHONDONTWRITEBYTECODE": "1",
            "HOME": str(work),
        }
        proc = await asyncio.create_subprocess_exec(
            *command,
            cwd=work,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        timed_out = False
        try:
            out, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout_s)
        except TimeoutError:
            timed_out = True
            proc.kill()
            out, _ = await proc.communicate()
        code = proc.returncode if proc.returncode is not None else 124
        return self._result(
            work,
            124 if timed_out else code,
            out.decode(errors="replace"),
            "local (not isolated)",
            started,
            timed_out,
        )

    @staticmethod
    def _result(
        work: Path, code: int, logs: str, backend: str, started: float, timed_out: bool
    ) -> SandboxResult:
        passed, failed, errors, skipped, failures = parse_junit(work / ".junit.xml")
        return SandboxResult(
            ok=code == 0 and not timed_out,
            exit_code=code,
            backend=backend,
            duration_ms=round((time.perf_counter() - started) * 1000, 1),
            stdout=logs,
            passed=passed,
            failed=failed,
            errors=errors,
            skipped=skipped,
            failures=failures,
            timed_out=timed_out,
        )
