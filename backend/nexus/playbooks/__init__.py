"""Playbook registry: built-in playbooks plus saved (YAML) ones from the data dir."""

from __future__ import annotations

from nexus.playbooks.base import Playbook

_PLAYBOOKS: dict[str, Playbook] = {}


def register(playbook: Playbook) -> Playbook:
    _PLAYBOOKS[playbook.id] = playbook
    return playbook


def get_playbook(playbook_id: str) -> Playbook:
    _ensure_loaded()
    if playbook_id not in _PLAYBOOKS:
        reload_saved()  # a playbook saved by another request
    if playbook_id not in _PLAYBOOKS:
        raise KeyError(f"unknown playbook '{playbook_id}'")
    return _PLAYBOOKS[playbook_id]


def all_playbooks() -> list[Playbook]:
    _ensure_loaded()
    return list(_PLAYBOOKS.values())


def _ensure_loaded() -> None:
    if _PLAYBOOKS:
        return
    from nexus.playbooks.builder import ProjectBuilder
    from nexus.playbooks.council_qa import CouncilQA
    from nexus.playbooks.dynamic import Dynamic
    from nexus.playbooks.self_healing import SelfHealing
    from nexus.playbooks.ticket_solver import TicketSolver

    for pb in (SelfHealing(), TicketSolver(), ProjectBuilder(), CouncilQA(), Dynamic()):
        register(pb)
    reload_saved()


def reload_saved() -> None:
    from nexus.core.config import get_settings
    from nexus.playbooks.dynamic import load_saved

    builtin = {"self_healing", "ticket_solver", "project_builder", "council_qa", "dynamic"}
    for pb in load_saved(get_settings().data_dir / "playbooks"):
        if pb.id not in builtin:
            register(pb)
