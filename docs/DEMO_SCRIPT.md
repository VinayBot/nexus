# 7-minute demo

**Before you start (2 min, off-camera):** `make dev`, open <http://localhost:3000>.
Start Mailpit if Docker is running (`make mail`, inbox at <http://localhost:8025>);
without it, approval e-mails land in the outbox and the approval card says so. In the
Chaos Lab, press **Restore baseline**, and keep **Auto-heal** on.

Presentation Mode (**▶ Present** in the top bar, or ⌘K → "Presentation mode") walks the
same path with spotlights, if you prefer to narrate over it.

| Time | Screen | Do | Say |
|---|---|---|---|
| 0:00 | Gate `/` | Let the Commander wave, then **Enter Command Center** | "Everything here runs on this laptop: a local 3B model via Ollama, no cloud APIs." |
| 0:20 | Top bar | Hover **System Power** | "The Resource Governor watches RAM and queues LLM calls instead of crashing a 16 GB Mac." |
| 0:40 | `/learn` | Scroll the table | "Every Day 16–20 concept, where it lives in code, and live counts of the events proving it ran." |
| 1:10 | `/chaos` | Ring **Null-handling bug** | "That injected a real bug into the live service. Watch the heartbeat go red, and the sky." |
| 1:40 | `/missions` | Open the new Hawk mission | "Hawk opened an incident. The Commander sends data packets to three investigators in parallel (Send fan-out). The Activity panel is their live ReAct trace." |
| 2:30 | Graph toggle | Switch to **Graph** | "This is the compiled LangGraph. The glowing node is the one running; light follows the branch just taken; ×N counts loops." |
| 3:00 | `/arena/<id>` | Watch the council | "Three Challengers propose fixes independently. Each patch runs in its own sandbox: green lights passed. Identities hide for anonymous review, and Arbiter weighs test evidence first." |
| 3:50 | `/approvals` (or Mailpit) | Show the risk gauge, the diff and the dry run, then **Approve** (or click Approve in the e-mail) | "HIGH risk means a dry run first, then a human approval. The e-mail link is signed and single-use; GET only shows a confirmation." |
| 4:30 | `/missions` | Watch execute → verify | "It's applied on a git branch with hot reload, then verified on live traffic. If errors came back it would roll back automatically." Point at the dawn sky and victory burst. |
| 5:10 | `/timetravel/<id>` | **Choose the tournament runner-up**, then compare | "Every super-step is a checkpoint. We can rewind to the tournament and fork with the runner-up: a new branch, compared side by side." |
| 6:00 | `/memory` | Show the Fix Library shelf | "The incident and its fix were stored. Arm the same switch again and the remembered fix enters the tournament as a seed, so it's faster." |
| 6:30 | Nova | Ask "Explain how reducers merged the parallel findings in this mission" | "Nova answers from the project docs and the live mission state, and says when something is a guess." |

**If the 3B model struggles live:** the tournament often needs a second round (the
validator feeds the failing tests back). That's the system working. Show the red
light bars in the Arena, then the green ones. Without Ollama, start the backend with
`NEXUS_LLM_PROVIDER=simulation` and say so: the UI shows a SIMULATION badge.
