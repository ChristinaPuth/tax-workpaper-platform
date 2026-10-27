# Core idea and data model

## The idea

A workpaper is not a copy of the return with ticks on it. It is the **proof** that the return is right:
for every number, where it came from, what was done to it, who checked it, and what is still open.

So the product keeps two things strictly apart:

1. **What we were given** — the packet: documents with what is actually printed on each page, what the
   pipeline read, client answers, prior-year and agency records, and three engine runs (v1–v3). It is
   loaded exactly as delivered and never edited.
2. **What people did about it** — an append-only log of events: adjustments, decisions, verifications,
   notes, questions, sign-offs, filing. Nothing is overwritten; undo is a new event.

Everything a user sees — the working return, each issue's state, the Inbox, sign-off status, the filing
gate — is **derived** from (1) + (2) on each request. Nothing derived is stored, so it can never drift
from the record, and every change keeps who made it, when and why — including the ones later undone.

## The data model

```
 Packet (immutable JSON)                         Event log (append-only, SQL)
   documents → pages → extracted values            id · at · actor · role · type · target node
   return_versions v1..v3 → lines → inputs/sources payload · layer (return | amendment) · batch_id
   client answers · messages · call notes                       │
   prior year · agency records · firm settings                  │
          │                                                     │
          ▼                                                     ▼
 Index: one graph over everything               Derived views (computed per request)
   5,383 nodes  (line, ev, page, doc, qa, msg,     working return = engine lines + live adjustments
                 asset, param, agency, person…)    issue state    = open / adjusted / decided
   14,757 edges (computed_from, sourced_from,      sign-off status = still valid / reopened (what changed)
                 read_from, same_line, refers_to…) Inbox, reports, filing gate, replay
          │
          ▼
 Checks (don't trust the engine) → Findings attached to nodes
   X  extraction: read vs printed, blank-as-zero, duplicate page, page not read
   R  independent recomputation of key figures
   P  process: payments vs IRS/FTB, identity vs documents, prior-year variance, every document used
   J  judgment: facts elsewhere in the file that should have changed a number
```

**Node ids are the shared vocabulary.** A finding, an event, a link and a sign-off all point at the same
ids (`line:v3:SchC.1`, `ev:ev-0127`, `page:D15#3`, `qa:qa-25`), so any screen can show everything known
about the thing in front of you, and any number can be traced down to the printed text or out to every
line it feeds.

**Three layers per value.** What the page prints, what the pipeline read, and what the return uses are
shown side by side. Most extraction errors are a difference between two of those layers.

**Sign-offs are snapshots.** A sign-off stores a content hash of everything it covers (the line, its
inputs and sources, decisions on them). If anything underneath changes, the sign-off reopens and says
exactly what changed — nobody has to remember to re-review.

**Roles are enforced on the server.** Preparer, reviewer, partner, quality reviewer, administrator and
the two clients each have an allowed set of event types; no one reviews or signs work they prepared;
judgments must cite their authority; the clients approve and e-sign only what the partner signed.

**Filing freezes the record.** Filing stores a snapshot; afterwards the return layer is closed and changes
go to an amendment layer, shown against what was filed. A federal e-file rejection reopens the return.

## Why this shape

- **Auditable by construction** — the log is the audit trail; the reviewer sees reasons, not just numbers.
- **Correct under change** — new documents, corrected forms and engine reruns arrive as new versions;
  derived views and sign-offs follow automatically.
- **Honest about estimates** — the engine cannot be rerun, so a change's tax effect is the change times
  the version's tax-effect rate, marked "≈" and flagged when several changes cross a threshold together.
- **Small to run** — FastAPI + SQLAlchemy (SQLite on a volume, Postgres when needed), React front end
  served by the same process; the index is rebuilt from the packet at start-up in well under a second.
