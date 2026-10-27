# Errors found, and how the design surfaced them

Return: Okafor-Lindqvist 2025, engine version v3 (2026-06-23). All findings are produced by checks that
run on the packet as delivered (`run_checks.py`, also on every server start); none are typed in by hand.

**18 errors.** If all are corrected, the estimated effect is **federal −7,713, California −3,288**
(positive = more tax or a larger balance due). Effects are the change × v3 `tax_effect_rates`, payments
1:1, and the HVAC item uses the engine's own what-if. Several corrections together cross thresholds
(SALT cap, CTC phase-out, brackets), so the totals show direction and size; the engine must recompute.

Every path below opens in the app. Start as **Priya Raman (preparer)**: the Inbox lists all of them worst
first, each with what happened, why it matters, what to do and the estimated effect.

## How the design surfaces errors

| Mechanism | What it compares | Errors it caught |
|---|---|---|
| **Three layers per value** | printed text ↔ what the pipeline read ↔ what the return uses | F-001, and the warnings F-003–F-006 |
| **Every page and document must land** | each page/document is used on a line, superseded, or carries a recorded reason | F-008, F-009, F-095 |
| **Cross-document reconciliation** | the same income or payment reported on two documents, summary vs detail | F-010, F-015, F-020 |
| **Agency records as an independent source** | return vs IRS transcript, FTB account, identity documents | F-032, F-033, F-034 |
| **Facts elsewhere in the file** | client answers, call notes, stock-plan supplements, closing statements, invoices | F-012–F-014, F-016–F-019, F-022 |
| **Independent recomputation** | our own arithmetic against the engine, using its rate tables | F-031 (and 32 checks that agreed; see below) |
| **Process gates** | prior-year variance, engine diagnostics, Form 8867, outside filings, areas considered | the items that must be decided before filing |

## The 18 errors

| # | Error | Origin | Federal | California | Check | Where to see it |
|---|---|---|---:|---:|---|---|
| F-012 | RSU lot N1 taxed on full proceeds; supplemental basis 19,100 not applied | engine rule | −6,647 | −1,222 | J1 | Return › Form 8949 › B.N1 → trace to D11 p2 and D28 p3 |
| F-013 | RSU lot N3, same (basis 19,100) | engine rule | −6,647 | −1,222 | J1 | Form 8949 › B.N3 |
| F-014 | RSU lot N4, same (basis 9,420, long-term) | engine rule | −2,242 | −320 | J1 | Form 8949 › E.N4 |
| F-015 | Schedule C gross receipts count the 1099-K 12,400 twice | engine rule | −4,402 | −384 | J2 | Reports › Area reports › Books to tax; Notice L566 evidence pack |
| F-022 | California-source wages include Halvorsen wages earned in Texas | engine rule | — | −5,685 | J9 | Reports › Area reports › State split (column E) |
| F-016 | Self-employed health insurance 14,400 although Erik could join Ngozi's employer plan | client fact | +4,464 | +605 | J3 | Sch 1 line 17 → evidence qa-25, 2024 note |
| F-017 | HVAC replacement 11,000 expensed as a repair | engine rule | +3,633 | +896 | J4 | Reports › Area reports › Rentals & passive losses (property A); what-if |
| F-019 | Home property tax includes the seller's 6,912 | engine rule | +1,462 | +332 | J6 | Reports › Area reports › Deductions (SALT); D54 vs D58 |
| F-032 | Federal estimates 13,000 vs IRS transcript 12,000 | client answer | +1,000 | — | P1 | Reports › Area reports › Payments |
| F-033 | California estimates 14,000 vs FTB 10,500 (3,500 designated to 2024) | engine rule | — | +3,500 | P2 | Reports › Area reports › Payments |
| F-008 | Mileage log page 3 is a second scan of page 2, counted twice | duplicate page | +919 | +80 | X5 | Documents › D23 page 3 |
| F-018 | Car donation at the client's 6,000 estimate; 1098-C proceeds 2,900 | engine rule | +806 | +149 | J5 | Deductions report; Notice L566 evidence pack |
| F-010 | Interest 1,840 on D28 and D29 for the same account, counted twice | duplicate source | −640 | −127 | X8 | Sch B line 2 → both sources |
| F-020 | Payoff interest 2,150 in mortgage interest twice | duplicate source | +559 | +103 | J7 | Sch A line 8a; D55 vs D56 |
| F-031 | Swedish interest converted at the 2024 rate | parameter | +43 | +9 | R6 | Sch B line 1.6 → fx rate |
| F-009 | Page 32 of D31 never read: lot M18 missing from Form 8949 | extraction | −21 | −2 | X6 | Documents › D31 ("Extraction partial: page 32 … not read") |
| F-034 | Theo's SSN on the return disagrees with D06 and D71 | client entry | — | — | P3 | Filing gate (blocks); Season replay, 13 Jul e-file rejection |
| F-001 | Child-care provider EIN misread (digits transposed, confidence 0.97) | extraction | — | — | X1 | Value ev-1045: printed vs read |
| | **Total** | | **−7,713** | **−3,288** | | |

The two largest items are worth a look in the app: the RSU lots (F-012–F-014) are the engine matching the
ESPP lot but not the RSU lots in the stock-plan supplement; the California wages (F-022) are box 16 on a
W-2 whose employer kept California as the work state after the move, contradicted by the 18 July paystub.

## Decide before filing (warnings)

These are not certain errors; each needs a recorded decision with its authority, and the gate will not
pass while they are open.

- **F-021** Phone, internet and Spotify deducted at 100% — client says 70% / 50% / personal (Sch C 25, 27a).
- **F-023** Crypto lot C6 at zero basis — client reports 3,050 paid in 2021 with only a bank line; ask for evidence.
- **F-003–F-006** Blank cost basis read as 0.00, and a basis read at confidence 0.6, feeding Form 8949.
- **F-095** Form 3922 (D13) not reflected in the return — every document must be used or explained.
- **Engine diagnostics** F-104 to F-114 (digital asset basis, Form 1099 filing, due diligence, CA AMT not computed…).
- **59 prior-year variances** over the firm's threshold, grouped into one review list; those caused by an
  error above link to it.

## Outside the return

Raised as findings because the facts in the file reveal them (check J12), shown in Reports › Area reports › Outside filings:
Form 3520 for 2023 (F-026), Forms 1099-NEC for two contractors (F-028), FBAR (F-027), Ada's own return
(F-029), Oregon and Arizona composite returns (F-030). Form 8867 due diligence is a filing step with its own
checklist.

## Client answers that contradict the records

The record wins and the conflict is noted: "no investments sold" vs 283 broker sales (F-025), "no prior IRA
basis" vs the 2024 Form 8606 (F-024); the car value and the January estimate are F-018 and F-032.

## Checked independently and agreed

Trust is shown where it is earned, too. Thirty-two independent checks agree with the engine or the records, among them: the
Schedule D tax worksheet (59,727), self-employment tax, NIIT (7,095), Additional Medicare, excess social
security (3,342), the SALT cap and CTC phase-out, the larger of itemized or standard deduction, the
California rate schedule and the 540NR ratio, carryovers against the 2024 return, and the 260 Brightpath
lots against their summary (proceeds, basis and wash sales).

## Found in review, not by a check

Honest gaps: these came from reading the file, and no automated check flags them yet — the daycare's name
on Form 2441 (D61 prints a different name), the home-office square footage carried from the prior preparer,
condo B's October HOA and staging costs after it was listed for sale, and whether the condo gain belongs in
California-source income. Each can be raised as a note or question on its line.
