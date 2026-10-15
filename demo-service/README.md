# demo-service — the orders service NEXUS watches

A tiny FastAPI "orders" service with a background pipeline that processes a batch
of generated orders every second, structured logs (`/logs`), counters
(`/metrics`) and a health endpoint (`/health`, based on the last 15 s of orders).

NEXUS runs a live copy of this folder (a git repo under `backend/data/demo-live`)
with `uvicorn --reload` on port 8100. Ringing a bell in the **Chaos Shrine**
injects a real bug into that copy's source; the Self-Healing playbook then has to
find it, reproduce it with tests, fix it, get approval, apply it and verify it.

Run the tests: `cd demo-service && python -m pytest -q`
