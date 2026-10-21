"""Web Page Builder end to end, keyword routing, page checks and model profiles."""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from nexus.api.app import create_app
from nexus.core.config import ModelProfile, get_settings
from nexus.core.runtime import runtime
from nexus.db import repo
from nexus.graph.nodes.understand import keyword_route
from nexus.graph.schemas import ApprovalDecision
from nexus.llm import profiles
from nexus.llm.router import ModelRouter
from nexus.llm.scripted import ScriptedLLM
from nexus.llm.simulation import simulation_llm
from nexus.playbooks.web_page import PageSpec, Section, SectionPlan, check_page, render_html


@pytest.fixture(autouse=True)
def env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEXUS_SMTP_PORT", "9")
    get_settings.cache_clear()


@pytest.mark.parametrize(
    ("task", "playbook"),
    [
        (
            "build a html page and write ai blog in and give me link of that html page",
            "web_builder",
        ),
        ("Write a blog post about vector databases", "web_builder"),
        ("Create a landing page for my bakery", "web_builder"),
        ("Fix ticket T-12", "ticket_solver"),
        ("The demo-service is unhealthy. Investigate it", "self_healing"),
        ("build a CRUD API for books", "project_builder"),
        ("What is the difference between ReAct and Plan-and-Execute?", None),
    ],
)
def test_keyword_route(task: str, playbook: str | None) -> None:
    assert keyword_route(task) == playbook


def _spec() -> PageSpec:
    return PageSpec(
        title="Hello",
        tagline="Tag",
        sections=[SectionPlan(heading="A", points="a"), SectionPlan(heading="B", points="b")],
    )


def test_render_escapes_agent_text_and_checks_quality() -> None:
    evil = Section(heading="A <script>", paragraphs=["<script>alert(1)</script> **bold** " * 70])
    page = render_html(_spec(), [evil, evil], mission_id="m1")
    assert "<script>" not in page and "&lt;script&gt;" in page
    assert "<strong>bold</strong>" in page
    assert check_page(page, [evil, evil]) == []
    thin = [Section(heading="A", paragraphs=["short"]), Section(heading="B", paragraphs=["x"])]
    problems = check_page(render_html(_spec(), thin, mission_id="m1"), thin)
    assert any("words" in p for p in problems) and any("too thin" in p for p in problems)


async def test_blog_request_builds_and_publishes_a_page() -> None:
    llm = simulation_llm()
    async with runtime(get_settings(), provider=llm, recover=False) as svc:
        row = await svc.runner.create(
            "build a html page and write ai blog in and give me link of that html page"
        )
        await asyncio.wait_for(svc.runner.wait(row.id), timeout=90)
        pending = await svc.approvals.list(mission_id=row.id)
        assert pending, "publishing must wait for a human"
        assert pending[0].payload["action"]["kind"] == "publish_page"
        await svc.approvals.decide(pending[0].id, ApprovalDecision(decision="approve"))
        await asyncio.wait_for(svc.runner.wait(row.id), timeout=90)

        mission = await repo.get_mission(svc.db, row.id)
        assert mission is not None and mission.outcome == "success", mission and mission.report
        report = mission.report or {}
        assert report["preview_url"].endswith(f"/sites/{row.id}/")
        assert report["answer"].startswith("# How AI Agents Work Together")

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=create_app()), base_url="http://t"
        ) as client:
            page = await client.get(f"/sites/{row.id}/")
        assert page.status_code == 200
        assert "<h1>How AI Agents Work Together</h1>" in page.text
        assert "<script" not in page.text


def test_router_sends_code_to_the_coder_model() -> None:
    from nexus.core.config import PROFILES

    router = ModelRouter(PROFILES[ModelProfile.BALANCED])
    assert router.pick("code")[1] == "qwen2.5-coder:3b"
    assert router.pick("solve", role="code")[1] == "qwen2.5-coder:3b"
    assert router.pick("write")[1] == "qwen2.5:3b"
    lite = ModelRouter(PROFILES[ModelProfile.LITE])
    assert lite.pick("code")[1] == "llama3.2:3b"  # no coder → main


async def test_profile_switch_is_saved_and_reported() -> None:
    llm = ScriptedLLM()
    async with runtime(get_settings(), provider=llm, recover=False) as svc:
        info = await profiles.describe(svc)
        assert {p["id"] for p in info["profiles"]} == {"lite", "balanced", "standard"}
        await profiles.apply(svc, ModelProfile.BALANCED)
        assert svc.llm.router.models.code == "qwen2.5-coder:3b"
        assert svc.llm.fallback_model == "llama3.2:3b"
        saved = json.loads((svc.settings.data_dir / profiles.FILE).read_text())
        assert saved == {"profile": "balanced"}
        await profiles.apply(svc, ModelProfile.LITE)


async def test_finished_mission_emails_the_result(monkeypatch: pytest.MonkeyPatch) -> None:
    from sqlalchemy import select

    from nexus.db.models import OutboxRow

    monkeypatch.setenv("NEXUS_RESULT_EMAIL", "owner@example.com")
    get_settings.cache_clear()
    async with runtime(get_settings(), provider=simulation_llm(), recover=False) as svc:
        row = await svc.runner.create(
            "Write a blog post about agents as an HTML page and email me the result"
        )
        await asyncio.wait_for(svc.runner.wait(row.id), timeout=90)
        pending = await svc.approvals.list(mission_id=row.id)
        await svc.approvals.decide(pending[0].id, ApprovalDecision(decision="approve"))
        await asyncio.wait_for(svc.runner.wait(row.id), timeout=90)
        await asyncio.gather(*svc.notifier._tasks)
        async with svc.db.session() as s:
            mails = (
                (await s.execute(select(OutboxRow).where(OutboxRow.to == "owner@example.com")))
                .scalars()
                .all()
            )
        result = [m for m in mails if m.subject.startswith("[NEXUS] Completed")]
        assert len(result) == 1
        body = result[0].html
        assert "Summary" in body and "Page published" in body and "In short:" in body
        assert "You asked" in body
        assert "How AI Agents Work Together" in body

        approval = [m for m in mails if m.subject.startswith("[NEXUS] Approval needed")]
        assert [m.to for m in approval] == ["owner@example.com"]  # links go to the owner only
        with pytest.raises(ValueError):
            svc.notifier.save(to="not-an-address", enabled=True)


async def test_connect_gmail_checks_then_saves_private_credentials() -> None:
    async with runtime(get_settings(), provider=ScriptedLLM(), recover=False) as svc:
        n = svc.notifier
        path = svc.settings.data_dir / "smtp.json"
        logins: list[str] = []

        async def accept(host: str, port: int, user: str, pw: str) -> None:
            logins.append(pw)

        async def refuse(host: str, port: int, user: str, pw: str) -> None:
            raise ValueError("Gmail refused the sign-in.")

        # a normal Google password is refused before any network call, and never saved
        with pytest.raises(ValueError, match="not a Gmail App Password"):
            await n.connect("gmail", "me@gmail.com", "MyPass@19word!")
        n._login_check = refuse
        with pytest.raises(ValueError, match="refused"):
            await n.connect("gmail", "me@gmail.com", "abcd efgh ijkl mnop")
        assert not path.exists()

        n._login_check = accept
        await n.connect("gmail", "me@gmail.com", "abcd efgh ijkl mnop")
        assert logins == ["abcdefghijklmnop"]
        st = n.status()
        assert st["delivery"] == "smtp" and st["account"] == "me@gmail.com"
        assert "abcdefghijklmnop" not in json.dumps(st)
        assert path.stat().st_mode & 0o777 == 0o600
        assert n.mailer.host == "smtp.gmail.com" and n.mailer.port == 587
        n.disconnect()
        assert n.status()["delivery"] == "mailpit" and not path.exists()


def test_smtp_errors_are_explained() -> None:
    import aiosmtplib

    from nexus.hitl.mailer import explain_smtp_error

    auth = explain_smtp_error(aiosmtplib.SMTPAuthenticationError(535, "bad"), "smtp.gmail.com")
    assert "App Password" in auth
    eof = explain_smtp_error(aiosmtplib.SMTPServerDisconnected("EOF"), "smtp.gmail.com")
    assert "App Password" in eof
    assert "Could not reach" in explain_smtp_error(ConnectionError("refused"), "127.0.0.1")


class _Downloader(ScriptedLLM):
    def __init__(self) -> None:
        super().__init__()
        self.have: list[str] = ["llama3.2:3b", "nomic-embed-text"]

    async def available_models(self) -> list[str]:
        return list(self.have)

    async def pull(self, model: str, progress: object = None) -> None:
        for done in (50, 100):
            if callable(progress):
                progress("pulling", done, 100)
        self.have.append(model)


async def test_install_downloads_missing_models_then_switches() -> None:
    llm = _Downloader()
    async with runtime(get_settings(), provider=llm, recover=False) as svc:
        info = await profiles.describe(svc)
        std = next(p for p in info["profiles"] if p["id"] == "standard")
        assert std["missing"] == ["qwen2.5-coder:7b"]
        profiles.start_install(svc, ModelProfile.STANDARD, std["missing"])
        with pytest.raises(RuntimeError):  # one install at a time
            profiles.start_install(svc, ModelProfile.STANDARD, std["missing"])
        await svc.extras["model_install_task"]
        assert svc.extras["model_install"]["state"] == "done"
        assert svc.llm.router.models.main == "qwen2.5-coder:7b"
        assert (await profiles.describe(svc))["active"] == "standard"


async def test_keyword_routed_request_never_pauses_to_clarify() -> None:
    llm = simulation_llm()
    vague = json.dumps(
        {"goal": "blog", "clarified_task": "Write a blog", "is_vague": True, "question": "Which?"}
    )
    llm.on("rewrite", vague)
    async with runtime(get_settings(), provider=llm, recover=False) as svc:
        row = await svc.runner.create("Write a blog post about small local models")
        await asyncio.wait_for(svc.runner.wait(row.id), timeout=90)
        pending = await svc.approvals.list(mission_id=row.id)
        assert [p.kind for p in pending] == ["approve_action"]  # publish, not a question


def test_chaos_reset_route_is_not_captured_by_the_switch_route() -> None:
    from nexus.api import routes_chaos

    paths = [getattr(r, "path", "") for r in routes_chaos.router.routes]
    assert paths.index("/chaos/reset") < paths.index("/chaos/{switch_id}")


def test_recipients_parse_and_per_mission_address_wins() -> None:
    from nexus.hitl.result_email import parse_recipients

    assert parse_recipients("a@x.com, b@y.org;junk  A@x.com") == ["a@x.com", "b@y.org"]


async def test_email_goes_out_only_when_the_prompt_asks() -> None:
    async with runtime(get_settings(), provider=ScriptedLLM(), recover=False) as svc:
        n = svc.notifier
        n.save(to="me@example.com", enabled=False)
        assert n.recipients({}) == []  # no request in the prompt: nothing is emailed
        row = await svc.runner.create(
            "Write a blog about agents and send the output to boss@example.com",
            playbook="council_qa",
        )
        assert row.inputs["email_requested"] and row.inputs["email_to"] == ["boss@example.com"]
        assert n.recipients(row.inputs) == ["boss@example.com"]
        me = await svc.runner.create("What is ReAct? Email me the answer.", playbook="council_qa")
        assert n.recipients(me.inputs) == ["me@example.com"]  # "me" = the owner's inbox
        plain = await svc.runner.create(
            "Write an article about email marketing", playbook="council_qa"
        )
        assert "email_requested" not in plain.inputs and n.recipients(plain.inputs) == []
        typed = await svc.runner.create(
            "Explain ReAct", playbook="council_qa", inputs={"email_to": "a@x.com, b@y.org"}
        )
        assert n.recipients(typed.inputs) == ["a@x.com", "b@y.org"]
        for r in (row, me, plain, typed):
            await svc.runner.cancel(r.id)


def test_summary_in_short_skips_headings_and_lists() -> None:
    from nexus.hitl.email_body import in_short

    md = "# Title\n\n_tagline_\n\n## Intro\n\nFirst sentence here. Second one. Third."
    assert in_short(md) == "First sentence here. Second one."


async def test_delete_mission_removes_outputs_but_keeps_the_audit_log() -> None:
    from sqlalchemy import func, select

    from nexus.core.deletion import MissionBusyError, delete_mission
    from nexus.db.models import AuditRow, EventRow

    async with runtime(get_settings(), provider=simulation_llm(), recover=False) as svc:
        row = await svc.runner.create("Write a blog post about agents as an HTML page")
        await asyncio.wait_for(svc.runner.wait(row.id), timeout=90)
        [pending] = await svc.approvals.list(mission_id=row.id)
        await svc.approvals.decide(pending.id, ApprovalDecision(decision="approve"))
        await asyncio.wait_for(svc.runner.wait(row.id), timeout=90)
        site = svc.settings.data_dir / "sites" / row.id
        assert site.is_dir() and svc.workspaces.path_for(row.id).is_dir()

        await delete_mission(svc, row.id)
        assert await repo.get_mission(svc.db, row.id) is None
        async with svc.db.session() as s:
            events = await s.scalar(select(func.count()).where(EventRow.mission_id == row.id))
            audits = await s.scalar(select(func.count()).where(AuditRow.mission_id == row.id))
        assert events == 0 and audits and audits > 0  # the decision record stays
        assert not site.exists() and not svc.workspaces.path_for(row.id).exists()
        state = await svc.runner.graph.aget_state(svc.runner.config(row.id))
        assert not state.values  # checkpoints gone

        busy = await svc.runner.create("Write a blog post about robots as an HTML page")
        with pytest.raises(MissionBusyError):
            await delete_mission(svc, busy.id)
        await svc.runner.cancel(busy.id)
