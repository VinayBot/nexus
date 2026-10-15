# ADR 0004 — Evidence-grounded tournaments

**Status:** accepted

## Context
LLM debate between copies of the same model tends to converge on shared mistakes.

## Decision
- In code mode every proposal is applied to its own throwaway copy of the workspace,
  and the full test suite runs in the sandbox. That suite includes a reproduction test,
  kept only if it fails on the buggy code.
- Peer review is anonymous (shuffled labels). Debate rounds happen only when reviewers
  disagree beyond a threshold.
- The judge weights evidence highest: tests 0.45, peer 0.25, critic 0.10, diff size
  0.10, reputation 0.10.
- A failing winner, low confidence or high divergence escalates to a human.
- A remembered Fix Library patch that still applies and passes the tests enters as a
  seed proposal, so repeat incidents are solved faster.

## Consequences
- Objective tie-breaks; wrong-but-confident patches are caught.
- Costs one sandbox run per proposal (about 1 s each locally).
