"""Compiled graph structure, agents and playbooks — what the Live Graph renders."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from nexus.core.services import services
from nexus.graph.main_graph import graph_structure, subgraph_structures
from nexus.graph.reducers import REDUCED_CHANNELS
from nexus.graph.state import DEFAULT_LIMITS
from nexus.playbooks import all_playbooks

router = APIRouter(tags=["graph"])


@router.get("/graph/structure")
async def structure() -> dict[str, Any]:
    return {
        **graph_structure(services().runner.graph),
        "subgraphs": subgraph_structures(),
        "reducers": REDUCED_CHANNELS,
        "limits": DEFAULT_LIMITS,
    }


@router.get("/playbooks")
async def playbooks() -> list[dict[str, Any]]:
    return [
        {
            "id": p.id,
            "title": p.title,
            "description": p.description,
            "tournament_mode": p.tournament_mode,
            "approve_team": p.approve_team,
        }
        for p in all_playbooks()
    ]
