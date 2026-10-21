"""The mission WebSocket never loses events that were broadcast but not yet saved."""

from __future__ import annotations

from starlette.testclient import TestClient

from nexus.api.app import create_app
from nexus.core.config import get_settings
from nexus.core.event_types import MissionCreated
from nexus.core.events import bus, emit
from nexus.core.runtime import runtime
from nexus.llm.scripted import ScriptedLLM


async def test_unsaved_events_reach_a_new_subscriber() -> None:
    async with runtime(get_settings(), provider=ScriptedLLM(), recover=False):
        await bus.flush()
        # emitted before anyone subscribes, still only in the in-memory batch
        emit("mission.created", MissionCreated(title="t", task="t", playbook=None), mission_id="m1")
        assert bus._pending  # not written to the database yet
        tc = TestClient(create_app())  # no lifespan: the runtime above provides services
        with tc.websocket_connect("/ws/missions/m1?after_seq=0") as ws:
            event = ws.receive_json()
        assert event["type"] == "mission.created" and event["mission_id"] == "m1"
