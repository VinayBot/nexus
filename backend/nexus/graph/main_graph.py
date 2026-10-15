"""The NEXUS orchestrator graph.

    intake → rewrite → route ─┬─(vague)→ clarify ⟲ rewrite          [interrupt]
                              └→ plan → assemble ─┬→ dispatch ⇉ worker×N → collect ─┐
                                   ↑              └→ report (team rejected)          │
                                   │       ┌──── more steps ready ⟲ dispatch ←──────┤
                                   │       ↓                                          │
                                   │  council | synthesize ← ────────────────────────┘
                                   │       ↓
                                   ├── validate ─(fail, fixes left)⟲ council
                                   │       ↓ pass            (fail, out of fixes) → plan / report
                                   │  risk_gate ─┬ auto → execute
                                   │             ├ approve → approval              [interrupt]
                                   │             └ dry-run → dry_run → approval
                                   │  approval ─┬ approve/edit → execute → verify ─┬ ok → memory_write
                                   ├────────────┤ respond (replan)                 └ fail → rollback
                                   └─────────── rollback (verify loops left) ←───────────┘
                                                memory_write → report → END

Every cycle has a guard counter in ``state.loops`` checked against ``state.limits``.
"""

from __future__ import annotations

from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import RetryPolicy

from nexus.graph.instrument import instrument
from nexus.graph.nodes import decide, finish, gate, planning, understand, work
from nexus.graph.state import MissionState
from nexus.llm.gateway import LLMUnavailableError

#: Fragile LLM-heavy nodes are retried by LangGraph itself (layer 2 of reliability).
RETRYABLE: tuple[type[Exception], ...] = (LLMUnavailableError, TimeoutError, ConnectionError)
LLM_RETRY = RetryPolicy(max_attempts=2, initial_interval=1.0, retry_on=RETRYABLE)

NODES: dict[str, Any] = {
    "intake": understand.intake,
    "rewrite": understand.rewrite,
    "route": understand.route,
    "clarify": understand.clarify,
    "plan": planning.plan,
    "assemble": planning.assemble,
    "dispatch": work.dispatch,
    "worker": work.worker,
    "collect": work.collect,
    "synthesize": work.synthesize,
    "council": decide.council,
    "validate": decide.validate,
    "risk_gate": gate.risk_gate,
    "dry_run": gate.dry_run,
    "approval": gate.approval,
    "execute": finish.execute,
    "verify": finish.verify,
    "rollback": finish.rollback,
    "memory_write": finish.memory_write,
    "report": finish.report,
}
RETRIED = {"rewrite", "route", "plan", "worker", "council", "synthesize", "validate"}

#: Human-readable descriptions for the Live Graph / Architecture Explorer.
NODE_INFO: dict[str, dict[str, str]] = {
    "intake": {"agent": "commander", "label": "Intake & Guardrails", "topic": "safety"},
    "rewrite": {"agent": "quill", "label": "Query Rewriter", "topic": "day16"},
    "route": {"agent": "commander", "label": "Mission Router", "topic": "day16-routing"},
    "clarify": {"agent": "user", "label": "Clarify (interrupt)", "topic": "day20"},
    "plan": {"agent": "sage", "label": "Planner / Replanner", "topic": "day16-plan-execute"},
    "assemble": {"agent": "commander", "label": "Team Assembler", "topic": "day19"},
    "dispatch": {"agent": "commander", "label": "Supervisor Dispatch", "topic": "day19-supervisor"},
    "worker": {"agent": "worker", "label": "ReAct Worker ×N", "topic": "day16-react"},
    "collect": {"agent": "commander", "label": "Fan-in", "topic": "day17-reducers"},
    "synthesize": {"agent": "quill", "label": "Synthesise", "topic": "day16"},
    "council": {"agent": "arbiter", "label": "Council Tournament", "topic": "council"},
    "validate": {"agent": "aegis", "label": "Validator", "topic": "day17-cycles"},
    "risk_gate": {"agent": "commander", "label": "Risk Gate", "topic": "day20"},
    "dry_run": {"agent": "aegis", "label": "Dry Run", "topic": "day20"},
    "approval": {"agent": "user", "label": "Human Approval (interrupt)", "topic": "day20"},
    "execute": {"agent": "forge", "label": "Executor", "topic": "playbook"},
    "verify": {"agent": "hawk", "label": "Verifier", "topic": "playbook"},
    "rollback": {"agent": "forge", "label": "Rollback", "topic": "day17-cycles"},
    "memory_write": {"agent": "quill", "label": "Memory Writer", "topic": "day18"},
    "report": {"agent": "quill", "label": "Reporter", "topic": "report"},
}


def build_graph(
    checkpointer: BaseCheckpointSaver[Any] | None = None,
) -> CompiledStateGraph[Any, Any, Any, Any]:
    g = StateGraph(MissionState)
    for name, fn in NODES.items():
        retry = LLM_RETRY if name in RETRIED else None
        g.add_node(
            name,
            instrument(
                name,
                fn,
                max_attempts=retry.max_attempts if retry else 1,
                retry_on=RETRYABLE,
            ),
            retry_policy=retry,
            # dispatch returns Command(goto=Send…): declare where it can go
            destinations=("worker", "collect") if name == "dispatch" else None,
        )

    g.add_edge(START, "intake")
    g.add_edge("intake", "rewrite")
    g.add_edge("rewrite", "route")
    g.add_conditional_edges("route", understand.after_route, ["clarify", "plan"])
    g.add_edge("clarify", "rewrite")
    g.add_edge("plan", "assemble")
    g.add_conditional_edges("assemble", planning.after_assemble, ["dispatch", "report"])
    g.add_edge("worker", "collect")
    g.add_conditional_edges("collect", work.after_collect, ["dispatch", "council", "synthesize"])
    g.add_edge("council", "validate")
    g.add_edge("synthesize", "validate")
    g.add_conditional_edges(
        "validate", decide.after_validate, ["risk_gate", "council", "synthesize", "plan", "report"]
    )
    g.add_conditional_edges("risk_gate", gate.after_gate, ["execute", "approval", "dry_run"])
    g.add_edge("dry_run", "approval")
    g.add_conditional_edges("approval", gate.after_approval, ["execute", "plan", "memory_write"])
    g.add_conditional_edges("execute", finish.after_execute, ["verify", "rollback"])
    g.add_conditional_edges("verify", finish.after_verify, ["memory_write", "rollback"])
    g.add_conditional_edges("rollback", finish.after_rollback, ["plan", "memory_write"])
    g.add_edge("memory_write", "report")
    g.add_edge("report", END)
    return g.compile(checkpointer=checkpointer, name="nexus")


def graph_structure(graph: CompiledStateGraph[Any, Any, Any, Any]) -> dict[str, Any]:
    """Nodes + edges (with conditional flags) for the Live Graph view."""
    drawable = graph.get_graph()
    nodes = []
    for node_id in drawable.nodes:
        info = NODE_INFO.get(node_id, {})
        nodes.append(
            {
                "id": node_id,
                "label": info.get("label", node_id.strip("_")),
                "agent": info.get("agent"),
                "topic": info.get("topic"),
                "kind": "terminal"
                if node_id in {"__start__", "__end__"}
                else ("interrupt" if node_id in {"clarify", "approval"} else "node"),
                "parallel": node_id == "worker",
                "subgraph": {"worker": "react_worker", "council": "tournament"}.get(node_id),
            }
        )
    edges = [
        {
            "source": e.source,
            "target": e.target,
            "conditional": e.conditional,
            "label": e.data if isinstance(e.data, str) else None,
        }
        for e in drawable.edges
    ]
    # dispatch → worker is a dynamic Send; make it explicit for the diagram
    if not any(e["source"] == "dispatch" and e["target"] == "worker" for e in edges):
        edges.append(
            {"source": "dispatch", "target": "worker", "conditional": True, "label": "Send ×N"}
        )
    return {"nodes": nodes, "edges": edges}


def subgraph_structures() -> dict[str, Any]:
    from nexus.graph.subgraphs.react_worker import react_worker
    from nexus.graph.subgraphs.tournament import tournament

    out = {}
    for name, sg in {"react_worker": react_worker, "tournament": tournament}.items():
        d = sg.get_graph()
        out[name] = {
            "nodes": [{"id": n, "label": n.strip("_")} for n in d.nodes],
            "edges": [
                {"source": e.source, "target": e.target, "conditional": e.conditional}
                for e in d.edges
            ],
        }
    return out
