"""Delete a mission and everything it produced, except the audit log.

Removed: the mission row, its events, approvals, dead letters, tool calls, outbox
mail, trace spans and time-travel branches; its LangGraph checkpoints; its
workspace folder, published page (``data/sites``) and project zip
(``data/exports``). Kept on purpose: the audit log, the record of who decided
what. Incidents keep their history but lose the link to the deleted mission.
A running mission must be cancelled first.
"""

from __future__ import annotations

import shutil
from typing import Any

from sqlalchemy import delete, update

from nexus.core.events import bus
from nexus.db.models import (
    ApprovalRow,
    BranchRow,
    DeadLetterRow,
    EventRow,
    IncidentRow,
    MissionRow,
    OutboxRow,
    ToolCallRow,
    TraceSpanRow,
)


class MissionBusyError(RuntimeError):
    pass


async def delete_mission(svc: Any, mission_id: str) -> None:
    runner = svc.runner
    if runner.is_running(mission_id):
        raise MissionBusyError("the mission is running: cancel it first")
    # events are written in batches: settle them first, or a late batch re-creates rows
    await bus.flush()
    async with svc.db.session() as s:
        for table in (
            EventRow,
            ApprovalRow,
            DeadLetterRow,
            ToolCallRow,
            OutboxRow,
            TraceSpanRow,
            BranchRow,
        ):
            await s.execute(delete(table).where(table.mission_id == mission_id))
        await s.execute(
            update(IncidentRow).where(IncidentRow.mission_id == mission_id).values(mission_id=None)
        )
        await s.execute(delete(MissionRow).where(MissionRow.id == mission_id))
    saver = svc.extras.get("checkpointer")
    if saver is not None:
        await saver.adelete_thread(mission_id)
    data = svc.settings.data_dir
    for path in (data / "sites" / mission_id, svc.workspaces.path_for(mission_id)):
        shutil.rmtree(path, ignore_errors=True)
    (data / "exports" / f"{mission_id}.zip").unlink(missing_ok=True)
