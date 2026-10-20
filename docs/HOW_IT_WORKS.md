# What NEXUS can do, and how to demo it

NEXUS is a team of 14 AI agents that runs on your Mac with local models (Ollama). You type
a task. The agents plan it, split it up, do the work in parallel, check it, and ask you
before anything risky. Then they show you the result. Nothing leaves your machine.

This guide covers three things for each mission type: **what it can do**, **how the agents
do it**, and **how to demo it**. The code-level walkthrough moved to
[CODE_WALKTHROUGH.md](CODE_WALKTHROUGH.md).

---

## 1. Before a demo (2 minutes)

1. Start everything: `make dev` (backend on :8000, app on :3000), then open
   http://localhost:3000.
2. Check the top bar shows **Online** (green). If it says Degraded, Ollama is not running or
   a model is missing. Settings → Models lists the exact `ollama pull` command.
3. Pick models in **Settings → Models** (click a card's button to switch):
   - **Lite** (llama3.2 3B for everything, ~3 GB). Fastest; the safest choice when the Mac is busy.
   - **Balanced** (Qwen2.5 3B for planning and writing, Qwen2.5-Coder 3B for code, ~5 GB).
     Better writing and better code fixes. Recommended for demos.
   - **Standard (7B)**: click **Install and switch**. After you confirm, NEXUS downloads
     `qwen2.5-coder:7b` (about 4.7 GB) with a progress bar and switches when it is done. It is
     the strongest, but heavy for a 16 GB Mac that is also running a browser and an IDE; you
     can switch back at any time.
4. **Email results** (Settings → Email results). Results are emailed **only when the prompt
   asks**: "…and send the output to boss@example.com", "…email me the answer", "…and also
   share email". Several addresses work. As you type, the box under the task shows who will get
   it. The result always appears in the app too, and the result card shows whether the email
   went out.
   - **Sending account:** click **Sign in with Google** and sign in on Google's own page.
     NEXUS gets one permission, *send email as you*: it cannot read your inbox and never sees
     your password. Google needs the app registered once first (free, about 5 minutes); the
     steps and links are in Settings.
   - **Approval requests** of a mission that asked for email go to *your* email ("Your email"
     in Settings), never to the target address, because their links approve or reject actions.
   - Emails sent before you signed in wait in the outbox; **Send N waiting emails** sends them.
   - Each email starts with a **Summary** (mission type, outcome and time, the key result,
     a two-sentence "in short"), then what you asked, the full output and the steps.
5. **Accent colour** (Settings → Appearance): Violet (default), Emerald, Teal, Rose or Ember.
   The robots' sky, the aurora and the embers follow the colour you pick.
6. Close heavy apps. If the Mac is short of memory, NEXUS slows down rather than crashing
   (the Resource Governor queues model calls), but a demo feels better with free RAM.

---

## 2. The screen you will use most: Missions

```
┌ New mission ──────────┐ ┌ Mission header: title · status · type ─┐ ┌ Activity ─────┐
│ What should the       │ │ Stage strip: Intake ✓ Rewrite ✓ ...    │ │ Key steps     │
│ agents do? [........] │ ├────────────────────────────────────────┤ │ Plan  Sage    │
│ Mission type:         │ │ ⚠ Approval (when the mission waits)    │ │ Handoff  ...  │
│ Auto · Web page · ... │ │ ✓ Result: You asked / Output / How     │ │ Verdict  ...  │
│ [ Start mission ]     │ │ Agents at work: Robots | Graph         │ │ Risk  ...     │
├ Recent missions ──────┤ │ Checkpoints (time travel)              │ │               │
└───────────────────────┘ └────────────────────────────────────────┘ └───────────────┘
```

- **Left: New mission.** Type the task, optionally pick a mission type, press **Start
  mission** (or Cmd+Enter). An empty box runs the type's example. "Use example" fills it in.
  Clear requests (a web page, a ticket id, "build an API") start straight away; the agents
  only stop to ask you a question when a request is genuinely unclear.
- **Middle:** the mission's status, its progress through the stages, then (when it applies)
  **your decision**, the **result**, and the robots working live. The Graph tab shows the
  same mission as a LangGraph diagram.
- **Right: Activity.** What each agent is doing. *Key steps* hides internal routing;
  *Reasoning* shows each agent's think → act → observe loop; *All* shows every event.
- **Approvals pop up wherever you are.** When a mission needs you, a dialog opens on top of
  the current screen. Press **Approve** or **Reject**, or **Later** to close it. The
  **"N waiting"** button in the top bar brings it back, and the same card also sits inside
  the mission view.
- **Every result reads the same way:** *You asked* (your words) → *outcome* (one sentence)
  → *output* (the page, the zip or the answer) → *How the team did it* (numbered steps in
  plain English, with time and tokens).
- **If a mission fails**, a red card says why in plain words (for example "the local model
  did not answer in time") and offers **Retry**.

---

## 3. The seven mission types

Every mission goes through the same pipeline: **understand → plan → assign a team → work
in parallel → check → risk gate → (your approval) → act → verify → remember → report.**
What changes per type is the work in the middle, and what "check" and "act" mean.

### 3.1 Web page: blog posts, articles, landing pages

**What it can do.** It writes real content and publishes it as a professional HTML page with
its own link. Examples:
- "Build an HTML page with a blog post about the future of AI in healthcare"
- "Create a landing page for a small bakery called Sunrise Breads in Pune"
- "Write an article about vector databases for beginners"

**How the agents do it.**
1. **Sage** plans the page: its type (blog, landing, article, portfolio), title, one-line
   tagline, audience, accent colour, and 3–5 sections, each with what it should cover.
2. **Quill** and **Echo** write the sections **in parallel**, one section each, as
   structured paragraphs plus key points.
3. **Forge** builds `index.html` from a fixed, professional template: hero, reading time,
   table of contents, sections and footer. The agents write the words, not the HTML, so
   the page always looks right and can never contain scripts.
4. **Aegis** checks the page automatically: a title, exactly one H1, at least 2 sections,
   at least 250 words, no section too thin, no `<script>`. If a check fails, the thin
   section is rewritten and the page rebuilt.
5. **Risk gate:** publishing scores MEDIUM, so **you approve it**. The pop-up shows the
   article first.
6. On approval, the page is published at `http://127.0.0.1:8000/sites/<mission>/`, then
   checked again.

**Result:** an **Open page** button, a live preview inside the card, and the full article
as text underneath.

**Demo (about 1 minute on Lite).**
1. Mission type **Web page**, then "Use example" (or type your own topic), then **Start mission**.
2. Point at the Activity feed: "Sage planned five sections; now Quill and Echo are writing
   them at the same time."
3. The approval pop-up opens with the article. Say: "Nothing is published until I agree."
   Press **Approve**.
4. Click **Open page**. A real, styled page in a new tab.

*Verified live:* "build a html page and write ai blog…" → 5 sections, 1,208 words,
published in 55 s on Lite. A bakery landing page on Balanced took about 60 s.

### 3.2 Question: a council answers hard questions

**What it can do.** It answers a question better than one model call, by making three
agents compete. Examples: "When should a team prefer optimistic over pessimistic locking?",
"What is the difference between ReAct and Plan-and-Execute agents?"

**How the agents do it.**
1. **Echo** searches the knowledge base from two angles (facts, then caveats) and cites
   what it finds.
2. Three solvers (**Blaze**, **Volt**, **Frost**) each write an answer independently, each
   with a different style.
3. The answers are relabelled A, B and C, so reviewers can't tell who wrote what, and each
   one is scored for correctness, completeness, simplicity and risk.
4. If the reviewers disagree, the solvers **debate** and revise.
5. **Arbiter**, the judge, picks the winner and gives a confidence score plus the main
   dissent.
6. **Aegis** grades whether the answer actually addresses the question; if not, the
   council goes again.

**Result:** the winning answer, and "Three solvers competed; Volt won (judge confidence
66%)" under *How the team did it*.

**Demo.** Type a question, choose **Question**, start it. While it runs, open
**Advanced → Arena** to watch proposals, anonymous reviews and the verdict appear live.
Takes 1–3 minutes.

*Verified live:* the locking question on Balanced, 183 s, with a correct and well-structured answer.

### 3.3 Fix service: self-healing (the flagship)

**What it can do.** It finds a real bug in a running service, fixes it, tests the fix, asks
you, applies it, and proves the service is healthy again. The service is the **demo shop**
(a FastAPI app on port 8100 that keeps processing orders).

**How the agents do it.**
1. **Hawk** watches the shop's health every 2 seconds. Two bad readings in a row → an
   **incident**, and (with auto-heal on) a mission starts by itself.
2. The agents copy the live code into a sandbox, run the tests, and **Aegis** writes a test
   that reproduces the failure.
3. The solvers see the file where the error is raised, **plus the definition of anything
   the error message names**. For example, "(check TAX_RATE)" shows them `TAX_RATE` in
   `app/config.py`.
4. **Blaze** (minimal fix), **Volt** (root-cause fix) and **Frost** (defensive fix) each
   propose one edit. **Every patch runs the full test suite in its own sandbox.** If the
   model botches the indentation, NEXUS re-indents the patch until it compiles; only
   whitespace changes.
5. Anonymous review and the judge's verdict follow. Test results count most (45%). If
   nothing passes, round 2 runs with the test failures as feedback.
6. Changing a live service scores **HIGH** risk, so NEXUS first **rehearses** the patch on
   a fresh copy, then asks you.
7. On approval, the fix is committed on a git branch and the service reloads. **Hawk
   watches live traffic**; if new errors appear, it **rolls back automatically**.
8. The fix is saved to the **Fix Library**, so the same bug next time starts from the
   remembered fix.

**Result:** the diff, "Verified: Healthy on live traffic: 98 orders processed, 0 new errors",
and the branch name.

**Demo (2–3 minutes).**
1. Open **Advanced → Chaos Lab** and switch on **Bad config value** (tax entered as 8
   instead of 0.08). The health chart turns red, and within seconds Hawk opens an incident
   and a mission starts.
2. Go to **Missions** and open it. Show the three solvers' test results in the Activity feed
   and, if you like, the Arena.
3. The approval pop-up shows the patch diff, "Rehearsal passed: 10 passed", and HIGH risk.
   **Approve.**
4. Show the result: verified on live traffic, and the health chart back to green.

*Verified live (Balanced):* round 1 patches failed 3 of 10 tests; in round 2 Volt's
root-cause fix (`TAX_RATE = 8.0 / 100` in `app/config.py`) passed 10/10. It was approved,
applied, and verified on 98 live orders with 0 errors. Total: 156 s.

The other four Chaos Lab switches: **Null-handling bug** (guest orders crash), **Off-by-one**
(pagination drops an order), **Slow dependency** (inventory timeouts), **Schema mismatch**
(`price` renamed to `unit_price`).

### 3.4 Build API: a small tested project

**What it can do.** It builds a small FastAPI CRUD service or command-line tool (8 files
or fewer) with tests, and hands you a zip. You can attach a requirements file (.md, .txt or .pdf).
Example: "Build a small FastAPI API to manage books (title, author, year) with tests."

**How the agents do it.**
1. **Quill** turns the request into a spec: the entity (Book), its fields
   (`title: str, author: str, year: int`) and any rules you stated. If the model puts the
   fields in the wrong slot, or leaves them out, they are recovered from your words
   ("books (title, author, year)").
2. **Forge** writes `models.py`, `store.py` and `main.py`, and **Aegis** writes
   `tests/test_api.py`, one dependency wave at a time, from a proven template with your
   entity and fields swapped in. If you stated rules (for example "price must be at least
   1"), Forge adapts the models to them. That change is kept only if it still compiles and
   keeps the names the other files import.
3. The tests run in the sandbox. If they fail, Forge repairs the file the error points at.
   The repair is told which names each file must keep, and a "repair" that deletes one is
   rejected. Then the tests run again.
4. Packaging a project scores MEDIUM risk, so **you approve it**, and it is zipped.

**Result:** the file list and a **Download project (.zip)** button.

**Demo.** Choose **Build API**, use the example, start it, approve, download, and in the unzipped folder
run `uv run --no-project --with fastapi --with httpx --with pytest pytest` (the result card
shows this command, plus how to start the server).

*Verified live (Balanced):* "books (title, author, year)" → `Book` model with exactly those
fields, CRUD endpoints, 4/4 tests passing, zip downloaded, in 15 s.

**Honest limit:** 3B models can build small services only. For a web page or blog, use
**Web page**: requests that mention HTML, a page, a website or a blog are routed there
automatically.

### 3.5 New ticket: write and file a bug report

**What it can do.** It turns a short request into a proper ticket, files it in the tracker
and emails it to you. Examples: "Create a ticket for the bug in the order pipeline and email
it to me", "open an issue about slow inventory".

**How the agents do it.**
1. **Echo** reads the code the request names (from a copy of the demo shop) and the recent error logs.
2. **Quill** writes a structured ticket: title, summary, steps to reproduce, expected vs
   actual, suspected file, severity and labels. It sticks to what the evidence shows.
3. Automatic check: a real title, a real summary, and at least one step.
4. Filing a ticket in the local tracker is LOW risk, so it runs without stopping. **Swift**
   creates it as the next number (T-105, T-106, …).
5. If you asked for it to be shared or emailed, the ticket is emailed to your address
   (Settings → Email results).

**Result:** "Ticket T-105 created · Emailed to you", the full ticket, and a **Solve this
ticket now** button that starts a *Solve ticket* mission for it.

*Verified live:* "cretae ticket for fixing bug in pipeline and also share email" → T-105
about the `run_batch` page-size check in `app/pipeline.py`, filed and emailed in 9 s.

### 3.6 Solve ticket: fix a ticket from the tracker

**What it can do.** It reads a ticket, changes the code to satisfy it, proves it with an
acceptance test, and comments on the ticket. Built-in tickets: **T-101** add a WELCOME5
discount code · **T-102** bulk discount · **T-103** free-shipping threshold 40 ·
**T-104** receipt typo. (GitHub issues work too, with a token.)

**How the agents do it.** The agents read the ticket and its attachments and write an
acceptance test from it. Then the three-solver tournament runs exactly as in self-healing,
each patch tested in the sandbox. Posting a comment needs your approval.

**Demo.** Choose **Solve ticket**, pick T-101, start it, approve, and see the comment on the
ticket with the diff.

*Verified live (Balanced):* T-101 in 115 s. Blaze's patch added WELCOME5 and passed 10/10;
after approval, the test report, diff and sandbox output were attached to the ticket and it was closed.

### 3.7 Custom team: anything else

**What it can do.** Any multi-step task that fits none of the above. Example: "Review the
demo-service code for risky error handling and summarise the top 3 issues."

**How the agents do it.** **Sage** writes a plan, and the **Commander** picks the best
agent for each step (agents with a better track record get picked first). If the task is
about the demo shop, the team gets a read-only copy of its code. **Before any work starts,
you approve the team.** Then the agents work in parallel using their tools:
reading files, searching the knowledge base, running tests. Finally **Quill** writes the
answer.

**Demo.** Choose **Custom team** and start. The pop-up shows the proposed team ("Echo: 2
steps, Forge: 1 step"); approve it. Read the summary in the result.

*Verified live (Balanced):* the error-handling review found the real issues (the inventory
timeout in `app/inventory.py`, the cancelled batch in `app/pipeline.py`) in 25 s.

### And "Auto"

With **Auto**, the Commander picks the type for you. Obvious requests are routed by
keyword, so they can't be misrouted: HTML/page/blog → Web page; "create a ticket" → New
ticket; "ticket T-101" → Solve ticket;
"incident"/"unhealthy" → Fix service; "build an API/CLI" → Build API. Everything else is
classified by the model, and plain questions go to Question.

---

## 4. The other screens

| Screen | What you see | What to say in a demo |
|---|---|---|
| **Approvals** | Every waiting decision with full detail (each risk factor and its weight, the verdict, the evidence) plus the **Audit log** of every decision | "Risk is scored by rules, not by the model, so a prompt can't talk its way past it. Every decision is logged." |
| **Agents** | The 14 agents: role, model, tools and track record. You can edit an agent or create a new one. | "Each agent has a tool allowlist; Hawk can watch but never write files." |
| **Insights** | Observatory (traces, token and latency charts), Benchmarks (three measured experiments), Under the Hood (raw SDK vs LangGraph), Curriculum Map | Show the honest benchmark: the council only beats one model when tests decide. |
| **Settings** | Models (switch profile live), concurrency, memory pruning, verify window, auto-heal, safety policies | Switch Lite ↔ Balanced; the old models are unloaded to free RAM. |
| **Advanced → Live Graph** | The mission as a LangGraph diagram, nodes lighting up as they run, plus the state inspector | "This is the actual graph, about 20 nodes, with loops that are guarded." |
| **Advanced → Arena** | The tournament: three proposals, anonymous scores, debate and verdict | Use it during a Question or Fix service mission. |
| **Advanced → Time Travel** | Every checkpoint of a mission. Re-run from any step, fork with a change, choose the runner-up, compare branches. | "Every step is saved to SQLite. I can rewind and try the other answer." |
| **Advanced → Chaos Lab** | Five bug switches for the demo shop, a live health chart, incidents, auto-heal on/off | The starting point of the self-healing demo. |
| **Advanced → Memory** | Fix Library, past missions, uploaded docs, lessons; search across them | "The second time the same bug appears, the fix comes from memory." |
| **Advanced → Tools** | The 7 MCP servers and their tools; call one by hand | "Agents only reach the world through these tools, and the workspace is jailed to the mission's folder." |
| **Advanced → How it Works** | Architecture diagram and topic map | For questions about the design. |

Also: **Nova** (the round robot, bottom right) answers questions about the app and can
navigate for you ("show me the tools"). **Present** in the top bar starts an auto-advancing
guided tour of 14 stops (→/← keys, Esc to exit; you can click around while it runs). **Cmd+K** opens the command palette.

---

## 5. A 7-minute demo order

1. **(30 s)** Missions screen: "14 agents, local models, nothing leaves the Mac."
2. **(90 s)** Web page: the bakery landing page → approve in the pop-up → **Open page**.
3. **(3 min)** Fix service: Chaos Lab → Bad config → the auto-started mission → the
   approval with the diff and rehearsal → verified on live traffic.
4. **(60 s)** Time Travel on that mission: fork from the tournament's runner-up.
5. **(60 s)** Insights → Benchmarks: the honest numbers.

---

## 6. Honest limits

- Small local models (3B) sometimes need a second round of work. That is why the guarded
  fix loops exist, and why the UI shows round numbers.
- Build API is scoped to small services (8 files or fewer).
- Without Docker the sandbox runs tests as a plain subprocess, which is not isolated. The UI
  says "local (not isolated)" when that happens.
- Email approvals need Mailpit (`make mail`); without it the email stays in the outbox, and
  the in-app pop-up still works.
- Single user, no login. Each mission has a 120k-token cap, so a runaway mission stops
  with a clear message.
