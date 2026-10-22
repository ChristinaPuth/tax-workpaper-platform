# Tax Workpaper Platform

A web-native tax workpaper. It proves a computed return is right: where every number came from,
what was done to it, who checked it, and what is still open.

## Features

- **Evidence tracing** — follow any number down to the exact field on its source document, and any
  document out to everywhere it landed (or why it didn't).
- **Independent checks** — rules that don't trust the tax engine: extraction vs printed text,
  duplicate sources, cross-document reconciliation, payments vs agency records, identity checks,
  and independent recomputation of key figures.
- **Audit trail** — source data is never overwritten. Every adjustment, verification, note,
  question and sign-off is an append-only event with who, when and why; undo is a new event.
- **Enforced roles** — preparer, reviewer, partner, quality reviewer, administrator and client,
  checked on the server (e.g. no one reviews their own work).
- **Live collaboration** — changes stream to every open session; each user sees what changed since
  they last looked.

## Quick start

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest -q
.venv/bin/uvicorn app.main:app --reload   # API docs at http://127.0.0.1:8000/docs
```

Input data is read from `data/` (override with `PACKET_PATH`); events are stored in SQLite under
`var/` (override with `DATABASE_URL`). `Dockerfile` builds a single service.
