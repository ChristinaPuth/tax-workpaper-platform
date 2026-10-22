# Okafor-Lindqvist 2025 — Workpaper

A web-native tax workpaper for one household's 2025 return (Miraflores case study).
The delivered packet is the immutable base layer; everything people do on top of it is an
append-only event log keyed by the same node ids.

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python run_checks.py            # -> out/errors.md, out/findings.json, out/document_landing.json
.venv/bin/python -m pytest -q             # 62 tests
.venv/bin/uvicorn app.main:app --reload   # -> http://127.0.0.1:8000/docs
```

The packet is read from `data/okafor_lindqvist_2025_packet.json` as delivered (override with `PACKET_PATH`).
Events go to `var/workpaper.db` (SQLite; override with `DATABASE_URL`).

## Layout

| Path | What it does |
|---|---|
| `workpaper/packet.py` | Read-only accessors over the packet. |
| `workpaper/index.py` | The graph. Stable node ids (`doc:D08`, `page:D08#1`, `ev:ev-0016`, `line:v3:F1040.1a`, `qa:qa-25`, `py:/…`, `agency:/…`) and typed edges. `trace_line()` = how a number was built, down to the page; `lines_fed_by()` = everywhere a value landed; `document_landing()` = where a document went, or why it did not. |
| `workpaper/checks/` | Checks that don't trust the engine. `extraction` (pipeline vs printed text), `recompute` (32 independent recomputations), `reconcile` (payments vs agency records, identities, carryovers, variance, completeness), `judgment` (facts stated elsewhere that should have changed a line). |
| `workpaper/findings.py`, `linking.py`, `report.py` | Findings attached to node ids, cross-linked, rendered to `out/errors.md`. |
| `app/main.py` | Loads the packet once, builds the index, runs every check, opens the event store. Serves `frontend/dist` when it exists. |
| `app/api.py` | Read-only endpoints: overview, versions/lines, line detail, trace, impact, documents, pages, findings, search. |
| `app/documents.py` | Simulated source documents: locates each value's text inside `printed_content` so the UI can highlight the exact span. Real page images later only touch this module. |
| `app/db.py` | Append-only `events`, `snapshots` (sign-off / filing), `attachments`, `user_state`. |
| `app/people.py` | Identities from the packet (6 staff, 2 client users) and the permission matrix; firm rules enforced on write (no self-review, verification types, judgment authority). |
| `app/events_api.py` | The only write surface: `POST /api/events` (actor in `X-Actor`), bulk with one `batch_id`, undo as a new event, `GET /api/me/changes` (what changed since I last looked). |
| `app/live.py` | Server-Sent Events: `GET /api/stream`, replays from `Last-Event-ID` on reconnect. |
| `analysis/` | The first exploratory error hunt (kept for the record). |
| `docs/` | Spec and planning (Chinese, internal). |

## Design decisions

- **Packet = immutable base; events = everything else.** Undo, "what changed since I last looked",
  version compare, sign-off reopening and freeze-at-filing all fall out of one append-only log.
- **Downstream propagation (planned):** `R-SUM`/`R-CARRY` lines propagate arithmetically; formula and
  tax lines are marked *stale* and their effect is estimated with the version's `tax_effect_rates`.
  Every number shows whether it is engine, adjusted, propagated or estimated.
- **Sign-offs bind to a content hash** of the signed scope (node + upstream subtree), not to an event id.
- **Filing freezes a snapshot**; after acceptance, one amendment layer sits on top.
- **Roles are enforced on the server.** The role switcher only chooses who you are.
- **Engine math is re-derived, not assumed.** 32 independent recomputations agree with v3 — the
  errors are in inputs and rules, not arithmetic.

## Deploy

`Dockerfile` builds one service (API + static frontend). On Railway, mount a volume at `/app/var`.
