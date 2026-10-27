# Tax Workpaper Features

Everything the workpaper does, area by area: what each feature is for and where to find it in the app. It is built around one household's 2025 federal and California return; the data is fictional.

- **Live app:** https://tax-workpaper.fly.dev
- **Demo video:** https://drive.google.com/file/d/1hVPVsw8LWMX8mQEojHj6_te01ZnUzAmC/view?usp=drive_link
- **Core idea and data model:** https://github.com/ChristinaPuth/tax-workpaper-platform/blob/main/docs/design.md
- **Errors found:** https://github.com/ChristinaPuth/tax-workpaper-platform/blob/main/docs/errors-found.md

**65 features built** and checked in the app, in 9 areas; **12 not built**, listed at the end with the reason.

In the live app each browser tab gets its own copy of the workpaper. Under **Demo data** (top right), **Start over** returns to the packet as delivered, and **Load the ready-to-file example** opens a fully reviewed return to try filing. Paths use the names shown in the app.

## Evidence and tracing

Every number linked to where it came from, down to the field on the page.

| Feature | What it does | Where to find it |
|---|---|---|
| Trace any number to its source | Each return line shows how it was built: its inputs, the extracted values, and the exact field on the source page. | Return › any line › How it was built |
| Source document viewer | Page text rendered with every extracted field highlighted; select a field to see what it feeds. | Documents › any document |
| Three layers per value | What the page prints, what the pipeline read, and what the return uses, side by side. A 97%-confident read of a tax ID that isn't on the page shows up here. | Documents › D62 › Provider tax ID |
| Where each document landed | For every document: the values used, the lines they feed, or the recorded reason it isn't used. | Documents › any document › Where this document went |
| Document index | All 74 documents with type, date received, extraction status and how many values reached the return. | Documents |
| Corrected documents | A corrected form is paired with its original; every changed value is listed with the lines the old and new values landed on. | Documents › D31 › What this correction changed |
| Related items | Last year's value for the line, the related returns it depends on (K-1 issuers, a dependent's own return), and links people add, shown on both sides. | Return › any line › Related |
| Verification records | Record how a number was checked: agreed to source, recalculated, confirmed with client, agreed to prior year or to a third-party record. | any item › Review & notes › Mark verified |
| Attachments | Upload a file onto any line, value or document (up to 5 MB) and download it later. Clients see only their own uploads. | any item › Review & notes › Attach file |
| Search | Search amounts and text across lines, documents and values, with keyboard selection. | Top bar search (⌘K) |

## Independent checks

Rules that don't trust the tax engine. 18 errors found on the packet as delivered.

| Feature | What it does | Where to find it |
|---|---|---|
| Extraction checks | Read value vs printed text, blank read as zero, low-confidence values in use, duplicate pages, pages never read, the same income on two documents, duplicate documents. | Inbox › Findings |
| Judgment checks | Facts elsewhere in the file that should have changed a number: stock-plan supplements, client answers, call notes, closing statements, invoices, residency dates. | Inbox › Findings |
| Agency and identity checks | Estimated payments against the IRS transcript and FTB account; names and SSNs against identity documents; carryovers against the 2024 return. | Reports › Area reports › Payments |
| Independent recomputation | Key figures recomputed with the engine's own rate tables: the Schedule D tax worksheet, SE tax, NIIT, Additional Medicare Tax, SALT cap, CTC phase-out, California tax and the 540NR ratio. | Reports › Area reports › Tax computation |
| Reconciliations | Figures that should agree, side by side: document totals, our recomputation vs the engine, agency payments, double counting. Differences link to their issue. | Reports › Reconciliations |
| Prior-year variance | Lines that moved more than the firm threshold (10% and 1,000) are grouped for review; ones caused by an error link to it. | Inbox › Batch reviews |
| Estimated tax effect per issue | Each issue carries its federal and California effect: the change times the packet's tax-effect rate, marked as an estimate. | Inbox › any issue |

## Changes and audit trail

The packet is never edited; every action is an event with who, when and why.

| Feature | What it does | Where to find it |
|---|---|---|
| Adjust without losing the original | A change needs a reason; the engine value stays, crossed out, with the estimated tax effect and an undo. | Return › any line › Adjust this number |
| Propagation and status badges | Sums and carries follow a change; formula lines are marked as needing a recompute. Every number shows whether it is engine, adjusted, propagated or stale. | Return › any form |
| Append-only event log | Adjustments, decisions, notes, questions, assignments, attachments, sign-offs and filing are all appended events. Undo is a new event; nothing is deleted. | any item › Changes to this line |
| Bulk actions with one undo | Settle several issues with one decision, or sign several items at once, then take the whole batch back in one click. | Findings › One decision for the selected › Undo all |
| Live updates | Changes stream to every open session; a toast says who did what. | Top bar › live |
| What changed since I last looked | Work by others since you last marked it read: who, what, where, when. | Top bar › N new |
| Version comparison | Compare any two of v1, v2, v3, the working return and the amended return: why it was recomputed, documents added or replaced, summary and line differences. | Reports › Versions |
| What-ifs | The engine's alternative scenarios with their federal, California and penalty effects; record one as an election with its authority. | Reports › What-if |

## Review and collaboration

Roles enforced on the server, sign-offs that know when they stop holding.

| Feature | What it does | Where to find it |
|---|---|---|
| Role-based inbox | Preparer, reviewer, partner, quality reviewer, administrator and client each get their own inbox, worst first, saying what happened, why it matters and what to do. | Inbox |
| Enforced roles | Checked on the server, not just hidden in the interface: who may adjust, review, sign, file or approve. | Role switcher › any action |
| Sign-offs that reopen | A sign-off stores a SHA-256 hash of everything it covers. If anything underneath changes, it reopens and lists what changed. No one can sign off work they prepared. | any line › Review & notes › Sign off |
| Questions that become evidence | Ask a colleague or the client about any item; the answer attaches to it as evidence and shows in the asker's inbox. | any item › Review & notes › Ask someone |
| Review notes that block filing | A blocking review note stops filing until a reviewer or partner resolves it. | any item › Review & notes › Review note |
| Assignments, deadlines, notifications | Assign an item to a person with a due date; the firm's deadlines are counted from the file's date; a bell lists what is waiting for you. | Inbox › Deadlines › bell |
| Client portal | Plain-language progress, questions to answer, this year against last year, and nothing internal to the firm. | Role switcher › a client › Portal |
| Client approval and e-signature | Both spouses approve with their full name and a five-digit PIN (Form 8879, FTB 8879) after the partner signs. The PIN is checked, never stored; the approval reopens if the return changes. | Portal › Approve and sign |

## Completeness and judgment

Proof that nothing was missed, and decisions recorded with their authority.

| Feature | What it does | Where to find it |
|---|---|---|
| Every document accounted for | Each document is used, superseded or carries a recorded reason before filing. | Filing › Can we file? › step 4 |
| Every area considered | The firm's nine budget areas, each with its lines, documents, open issues and hours; recorded as considered or not applicable with the basis. | Filing › Areas considered |
| Decisions with authority | Judgments, elections, due diligence, penalty decisions and explanations, each with the authority relied on (required). | any issue › Record decision |
| Outside filings | Filings the facts reveal beyond this return: FBAR, Form 3520, Forms 1099-NEC, composite returns, a dependent's own return, with deadlines. | Reports › Area reports › Outside filings |
| Form 8867 due diligence | The knowledge requirements for each dependent's credit, worked out from the file. An item that is still a problem can't be ticked. | Filing › step 8 › Open the Form 8867 checklist |
| Client answers vs records | When a client's answer contradicts a document or a filed return, the record wins and the conflict is shown. | Findings |

## Filing and history

A gate before filing, a frozen record after it, and the history behind it.

| Feature | What it does | Where to find it |
|---|---|---|
| Filing gate | The firm's twelve required steps, each derived from the work, plus blockers: open errors, unreviewed changes, changes over 1,000 without a partner, reopened sign-offs. | Filing › Can we file? |
| Filing snapshot and freeze | Only the partner files, and only when the gate passes. Filing stores a snapshot; the filed return then takes no changes. | Filing › File the return |
| E-file acknowledgments | Record the IRS and FTB acknowledgments. A federal rejection reopens the return to fix and file again; acceptance freezes it again. | Filing › E-file acknowledgments |
| Amendment layer | After filing, changes go to an amendment (Form 1040-X; California 540NR with Schedule X), compared against what was filed. It does not reopen the filed sign-offs. | Filing › Compare as filed vs amended |
| Season replay | Any day of the season from the scenario's record: stage, documents received, engine version, e-file results, the IRS account, notices and deadlines. | Filing › Season replay |
| Notice evidence pack | For the 2028 IRS Letter 566: the lines as filed, the reconciliation to five Forms 1099-NEC, the issues and how they were settled, sign-offs and source pages. | Season replay › Build the evidence pack |
| Roll forward to 2026 | Carryovers, assets still in service, open items and this year's elections, ready for next year. | Reports › Area reports › Roll forward to 2026 |

## Reports for the CPA

Area schedules a reviewer expects, each tied back to the lines and issues.

| Feature | What it does | Where to find it |
|---|---|---|
| Summary vs last year | Main 1040 and California lines for 2024 and 2025, with change and percentage; large moves link to their review. | Reports › Summary vs 2024 |
| Area summaries | One card per area: open issues and their effect, changes, documents and budget hours. | Reports › Areas |
| Sales detail (Form 8949) | 302 sales: search, group by box with subtotals (including the new digital-asset boxes), sort by amount, shown a page at a time. | Return › Form 8949 |
| Books to tax | Each line of the business books mapped to Schedule C, with the 12,400 gap from the 1099-K counted twice. | Area reports › Books to tax |
| Rentals and passive losses | Both properties line by line, the passive loss release, and the sale of property B. | Area reports › Rentals & passive losses |
| K-1s and S corporation basis | Every K-1 box and the line it lands on; the basis roll-forward. | Area reports › K-1s & S corporation basis |
| Deductions, credits and limits | Itemized vs standard, SALT, interest, charity, credits, with the limits recomputed independently. | Area reports › Deductions, credits & limits |
| Payments | Each estimated payment: confirmation in the file against the IRS and FTB records. | Area reports › Payments |
| State split | Residency dates, Schedule CA columns with the California share, and the 540NR ratio recomputed. | Area reports › State split |
| Depreciation, carryovers and more | Depreciation by asset, carryovers in and out, retirement and foreign items, tax computation, and the prior preparer's open items. | Reports › Area reports |

## Usability and security

Easy for a new hire, safe with sensitive data.

| Feature | What it does | Where to find it |
|---|---|---|
| Simple and expert views | Simple hides technical ids and explains terms; expert shows everything, denser. | Help › Settings |
| Quick start for new hires | A short checklist that ticks itself as the person actually does each step; on by default for new, unlicensed staff. | Help › Quick start |
| Glossary | Plain-language explanations of 28 tax terms, shown on hover and searchable. | Help › Glossary |
| Sensitive-data masking | SSNs, PINs and account numbers are masked for everyone without clearance; cleared staff reveal one field at a time, and every view is logged. | any page › Show |
| Role switcher | Act as any of the six staff or two clients to see their view. It stands in for real login. | Top right |

## Platform and delivery

How it runs, how it is deployed, and what was delivered.

| Feature | What it does | Where to find it |
|---|---|---|
| Saves everything | Every action is stored in SQL (SQLite on a volume; Postgres by changing one setting). A reload keeps all work. | any page |
| Live public demo | Deployed on Fly.io. Each browser tab gets its own copy; Start over resets it; the ready-to-file example jumps to a fully reviewed return. | Live app › Demo data |
| One image, tested | One Docker image serves the API and the app; 195 automated tests. | Source code |
| Delivered documents | A one-page design note, the errors write-up, a demo video and a note on how AI was used. | Links at the top |

## Not built

Left out on purpose, with the reason. Lower-priority items first.

| Feature | Why not |
|---|---|
| Extensions | Lower priority. The extension filed in April is shown in the deadlines and the replay, but there is no workflow to prepare one. |
| The client's copy | Lower priority. No packaged PDF copy of the filed return for the client. |
| Plan next year | Lower priority. The roll-forward lists what carries into 2026; no tax projection. |
| After filing: payments and refunds | Lower priority. Balance-due payment and refund tracking after filing are visible only in the replay. |
| Firm-wide standards | Lower priority. The firm's rules from the packet are applied; editing them in the app is not built. |
| Time against budget | Lower priority. Budget hours per area are shown; actual time is not tracked. |
| Seven-year retention | Lower priority. Nothing is ever deleted, but there is no retention schedule or archive. |
| Basis by year | Lower priority. Basis is shown in the K-1 and roll-forward reports, not as its own multi-year schedule. |
| Review of the amendment | Changes on the amendment are recorded and compared, but have no review sign-off of their own yet. |
| Real e-file transmission | Acknowledgments come from the scenario's records; there is no connection to the IRS or FTB. |
| Client uploads in the portal | The server accepts client uploads, but the portal has no upload button yet. |
| Front-end automated tests | The server has 195 tests; the screens were checked by hand and by scripted browser runs. |
