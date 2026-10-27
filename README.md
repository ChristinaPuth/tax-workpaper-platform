# Tax Workpaper Platform

A web-native tax workpaper. It proves a computed return is right: where every number came from,
what was done to it, who checked it, and what is still open.

Built around one household's 2025 return (Form 1040 and California 540NR). All people, numbers and
documents in the data are fictional.

| | |
|---|---|
| **Live app** | https://tax-workpaper.fly.dev |
| **Demo video** | [Watch on Google Drive](https://drive.google.com/file/d/1hVPVsw8LWMX8mQEojHj6_te01ZnUzAmC/view?usp=drive_link) |
| **Core idea and data model** (one page) | [docs/design.md](docs/design.md) |
| **Errors found, and how the design surfaced them** | [docs/errors-found.md](docs/errors-found.md) |

## Try it

Open the live app. Each browser tab gets its **own copy** of the workpaper: change anything, a reload
keeps your work, and other visitors never see it. The **role switcher** (top right) lets you act as the
preparer, reviewer, partner, quality reviewer, administrator or either client.

Under **Demo data** (top right):
- **Start over** — back to the packet exactly as delivered: 35 items in the preparer's inbox.
- **Load the ready-to-file example** — every issue settled, reviewed and signed, both clients approved.
  Opens as the partner on the filing page, to try filing, an e-file rejection, refiling and an amendment.

The machine sleeps when idle, so the first page can take a few seconds.

## What it does

- **Evidence tracing** — follow any number down to the exact field on its source page, and any
  document out to every line it feeds (or the reason it feeds none).
- **Three layers per value** — what the page prints, what the pipeline read, and what the return uses,
  side by side. Most extraction errors are a difference between two of them.
- **Independent checks** — rules that don't trust the tax engine: read vs printed text, blank read as
  zero, duplicate pages and sources, pages never read, cross-document reconciliation, payments against
  the IRS transcript and FTB account, identity against documents, prior-year variance, and independent
  recomputation of key figures. 18 errors found on the packet as delivered.
- **Append-only audit trail** — the packet is never edited. Every adjustment, decision, verification,
  note, question, assignment, attachment and sign-off is an event with who, when and why; undo is a
  new event.
- **Sign-offs that know when they stop holding** — a sign-off stores a SHA-256 hash of everything it
  covers; if anything underneath changes it reopens and says exactly what changed.
- **Enforced roles** — checked on the server: no one reviews their own work, every judgment cites its
  authority, clients approve (Form 8879 PIN) only what the partner signed.
- **Filing gate** — the firm's twelve required steps, each derived from the work, plus every area of
  the return considered and the Form 8867 due-diligence checklist.
- **Filing snapshot and amendment** — filing freezes the return; a federal e-file rejection reopens it;
  later changes go to an amendment layer compared against what was filed.
- **History** — engine versions v1–v3 compared line by line, a replay of the season from the record,
  and an evidence pack for the 2028 IRS letter built from the workpaper itself.
- **Reports, client portal and more** — area reports, reconciliations, a plain-language client portal,
  assignments and deadlines, notifications, live updates between sessions, sensitive-data masking.

## How it is built

Two things are stored: the **packet** exactly as delivered (immutable JSON) and an **append-only event
log** (SQL). Everything else — the working return, issue status, sign-off status, the inbox, the filing
gate, reports — is derived from those two on each request, so it can never drift from the record.

The packet is loaded into one graph (about 5,400 nodes and 15,000 edges: lines, extracted values, pages,
documents, client answers, agency records). Findings, events, links and sign-offs all point at the same
node ids, so any screen can show everything known about the item in front of you.
See [docs/design.md](docs/design.md).

**Stack:** Python, FastAPI, SQLAlchemy (SQLite on a volume; Postgres by changing `DATABASE_URL`),
React + TypeScript + Vite + Tailwind, one Docker image, deployed on Fly.io. 195 automated tests.

### Tradeoffs and limits

- **The tax engine is not rebuilt.** The packet provides the engine's results, not the engine; a second
  engine would itself need auditing. Key figures are recomputed independently instead.
- **Tax effects are estimated** — the change times the packet's tax-effect rate — always marked "≈", with
  a warning when changes are large enough to cross thresholds. A production system would rerun the engine.
- **E-filing is simulated.** Acknowledgments come from the packet's records; the snapshot, freeze,
  rejection and refiling logic around them is real.
- **Concurrency.** One instance on SQLite; the append-only log means no one overwrites anyone, but many
  simultaneous editors were not load-tested. Production: Postgres and proper authentication in place of
  the role switcher.
- **Some judgment checks are written against this household's facts** and would need generalizing.
- Not built: review sign-off of the amendment, real e-file transmission, client uploads in the portal,
  front-end automated tests.

## Run it locally

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest -q
(cd frontend && npm ci && npm run build)
.venv/bin/uvicorn app.main:app --reload        # http://127.0.0.1:8000 (API docs at /docs)
```

Or with Docker:

```bash
docker build -t tax-workpaper .
docker run --rm -p 8000:8000 -v "$PWD/var-docker:/app/var" tax-workpaper
```

- Input data is read from `data/` (override with `PACKET_PATH`); events are stored in SQLite under
  `var/` (override with `DATABASE_URL`).
- `-e SANDBOX_PER_VISITOR=1` turns on the public-demo mode: one copy per browser tab and the Demo data menu.
- `python scripts/demo_seed.py http://localhost:8000 [--approved]` works through the whole review on a
  running instance (ready for the partner, or with `--approved` ready to file).
- `fly deploy` deploys with `fly.toml`.

## Project layout

```
workpaper/   packet loader, the graph index, the checks (extraction, reconciliation, recompute, judgment)
app/         FastAPI: read API, the event log and roles, derived views (inbox, sign-offs, gate, reports,
             versions, replay, notices), demo sandboxes
frontend/    React app
tests/       pytest suite
docs/        design note and errors found
```

## Use of AI

The design decisions and the architecture are my own. Claude (Anthropic's coding assistant, Claude Code)
wrote part of the code and the tests under my direction.
