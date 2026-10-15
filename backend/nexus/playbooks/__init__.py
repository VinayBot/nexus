"""Playbook registry."""

from __future__ import annotations

from nexus.playbooks.base import Playbook

_PLAYBOOKS: dict[str, Playbook] = {}


def register(playbook: Playbook) -> Playbook:
    _PLAYBOOKS[playbook.id] = playbook
    return playbook


def get_playbook(playbook_id: str) -> Playbook:
    _ensure_loaded()
    if playbook_id not in _PLAYBOOKS:
        raise KeyError(f"unknown playbook '{playbook_id}'")
    return _PLAYBOOKS[playbook_id]


def all_playbooks() -> list[Playbook]:
    _ensure_loaded()
    return list(_PLAYBOOKS.values())


def _ensure_loaded() -> None:
    if _PLAYBOOKS:
        return
    from nexus.playbooks.council_qa import CouncilQA

    for pb in (CouncilQA(),):
        register(pb)
