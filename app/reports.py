"""CPA reports derived from the packet, the findings and the log: the return against last year, one card per
area, and every reconciliation - what agrees and what does not.

Like the Inbox and the gate, nothing here is stored: each report is rebuilt on request, so it always shows
the working return (engine values plus people's adjustments) and the current state of every issue.
"""
from __future__ import annotations

from collections import defaultdict

from workpaper.working import WorkingReturn

from .inbox import AREAS, GROUPED, SEVERITY_RANK, _DOC_AREA, area_of, finding_state
from .logview import LogView

VARIANCE_PCT, VARIANCE_ABS = 0.10, 1000  # firm threshold for prior-year variances (check P5)

# (label, 2025 line, 2024 line). Balance rows are signed: positive = owed, negative = refund.
FEDERAL_ROWS = [
    ("Wages", "F1040.1a", "F1040.1a"),
    ("Taxable interest", "F1040.2b", "F1040.2b"),
    ("Ordinary dividends", "F1040.3b", "F1040.3b"),
    ("Capital gain or (loss)", "F1040.7", "F1040.7"),
    ("Additional income (Schedule 1)", "F1040.8", "F1040.8"),
    ("Total income", "F1040.9", "F1040.9"),
    ("Adjustments to income", "F1040.10", "F1040.10"),
    ("Adjusted gross income", "F1040.11", "F1040.11"),
    ("Standard or itemized deduction", "F1040.12", "F1040.12"),
    ("Qualified business income deduction", "F1040.13", "F1040.13"),
    ("Taxable income", "F1040.15", "F1040.15"),
    ("Tax", "F1040.16", "F1040.16"),
    ("Child tax credit / other dependents", "F1040.19", "F1040.19"),
    ("Other taxes", "F1040.23", "F1040.23"),
    ("Total tax", "F1040.24", "F1040.24"),
    ("Federal income tax withheld", "F1040.25a", "F1040.25a"),
    ("Estimated tax payments", "F1040.26", "F1040.26"),
    ("Total payments", "F1040.33", "F1040.33"),
]
CALIFORNIA_ROWS = [  # 2024: form 540 (full-year resident); 2025: form 540NR (part-year)
    ("Federal AGI", "F540NR.13", "CA540.13"),
    ("AGI using California law (all income)", "F540NR.17", "CA540.17"),
    ("California AGI (California-source)", "F540NR.32", "CA540.17"),
    ("Taxable income", "F540NR.19", "CA540.19"),
    ("Tax on taxable income", "F540NR.31", "CA540.31"),
    ("Total tax", "F540NR.64", "CA540.64"),
    ("California income tax withheld", "F540NR.71", "CA540.71"),
    ("Estimated tax payments", "F540NR.72", "CA540.72"),
]

# area key -> the firm's budget line (packet firm.budget_hours)
BUDGET_KEY = {"intake": "intake_and_engagement", "wages": "wages_and_stock_compensation",
              "investments": "investments_and_digital_assets", "business": "business", "rentals": "rentals_and_sale",
              "passthroughs": "pass_throughs_and_basis", "deductions": "deductions_and_credits",
              "california": "california"}

RECONCILIATION_KINDS = [  # (check family, heading, what is compared)
    ("X7", "Documents agree with their own totals", "broker summary vs the sum of its lots"),
    ("X8", "Income reported once", "the same income on two documents"),
    ("J2", "Income reported once", "1099-K deposits vs the books"),
    ("J7", "Income reported once", "the same interest on two statements"),
    ("R1", "Our recomputation agrees with the engine", "line arithmetic"),
    ("R2", "Our recomputation agrees with the engine", "federal tax"),
    ("R3", "Our recomputation agrees with the engine", "self-employment tax and surtaxes"),
    ("R4", "Our recomputation agrees with the engine", "depreciation, basis and carryovers"),
    ("R5", "Our recomputation agrees with the engine", "California tax"),
    ("R6", "Our recomputation agrees with the engine", "foreign currency"),
    ("P1", "Payments agree with the agencies", "estimated and extension payments vs the IRS transcript"),
    ("P2", "Payments agree with the agencies", "estimated payments vs the FTB account"),
    ("P3", "Identity agrees with the documents", "names and SSNs vs identity documents and the 2024 return"),
    ("P4", "Carryovers agree with last year", "2025 carryovers in vs the 2024 return"),
]


# Formula lines the engine would recompute: after a change their working value is the estimate
# (change x tax-effect rate) from the working summary, not the engine's stale number.
ESTIMATED = {"F1040.24": "total_tax", "F540NR.64": "ca_total_tax"}
BALANCE = {"F1040.37": "balance_due", "F540NR.91": "ca_balance_due"}


def _value(working: WorkingReturn, packet, key: str) -> tuple[float | None, float | None]:
    """(engine, working) for a current-version line."""
    line = packet.line(key, working.version)
    if line is None:
        return None, None
    if key in ESTIMATED and working.summary.get(ESTIMATED[key]):
        return line["value"], working.summary[ESTIMATED[key]]["value"]
    w = working.lines.get(key)
    return line["value"], (w["value"] if w else line["value"])


def summary_vs_prior(packet, working: WorkingReturn, findings, log: LogView) -> dict:
    prior = packet.raw["prior_years"]["return_2024"]
    p5 = {}
    for f in findings:
        if f.check.startswith("P5"):
            for n in f.nodes:
                if n.startswith("line:"):
                    p5.setdefault(n.split(":", 2)[2], f)

    def row(label: str, key: str, py_key: str) -> dict:
        engine, now = _value(working, packet, key)
        before = prior["lines"].get(py_key)
        change = None if now is None or before is None else now - before
        over = (change is not None and abs(change) > VARIANCE_ABS
                and (before == 0 or abs(change) > VARIANCE_PCT * abs(before)))
        f = p5.get(key)
        return {"label": label, "key": key, "prior_key": py_key, "prior": before,
                "prior_source": prior["line_sources"].get(py_key), "engine": engine, "working": now,
                "adjusted": now != engine, "estimated": key in ESTIMATED and now != engine, "change": change,
                "pct": None if change is None or not before else change / abs(before),
                "over_threshold": over, "finding_id": f.id if f else None,
                "finding_state": finding_state(f, log, working.version)["state"] if f else None}

    def balance(owe_key: str, refund_key: str, py_owe: str, py_refund: str) -> dict:
        def signed(get, owe, refund):
            o, r = get(owe), get(refund)
            return None if o is None and r is None else (o or 0) - (r or 0)
        engine = signed(lambda k: _value(working, packet, k)[0], owe_key, refund_key)
        est = working.summary.get(BALANCE.get(owe_key, ""))
        now = est["value"] if est and est.get("value") is not None else signed(lambda k: _value(working, packet, k)[1], owe_key, refund_key)
        before = signed(lambda k: prior["lines"].get(k), py_owe, py_refund)
        key = owe_key if packet.line(owe_key, working.version) is not None else refund_key  # link the line that exists
        py_key = py_owe if py_owe in prior["lines"] else py_refund
        return {"label": "Amount owed (refund shown negative)", "key": key, "prior_key": py_key, "prior": before,
                "prior_source": prior["line_sources"].get(py_key),
                "engine": engine, "working": now, "adjusted": now != engine, "estimated": now != engine,
                "change": None if now is None or before is None else now - before, "pct": None,
                "over_threshold": False, "finding_id": None, "finding_state": None}

    return {
        "version": working.version,
        "prior_prepared_by": prior["prepared_by"],
        "prior_filed": prior["filed"],
        "threshold": {"pct": VARIANCE_PCT, "abs": VARIANCE_ABS},
        "sections": [
            {"key": "federal", "title": "Federal (Form 1040)", "note": None,
             "rows": [row(*r) for r in FEDERAL_ROWS] + [balance("F1040.37", "F1040.34", "F1040.37", "F1040.34")]},
            {"key": "california", "title": "California",
             "note": f"2024: {prior['residency']} (form 540). 2025: part-year resident (form 540NR), so "
                     "California-source income is only part of the total - the two years are not like for like.",
             "rows": [row(*r) for r in CALIFORNIA_ROWS] + [balance("F540NR.91", "F540NR.97", "CA540.111", "CA540.115")]},
        ],
    }


def areas(packet, working: WorkingReturn, findings, log: LogView) -> list[dict]:
    budget = packet.firm.get("budget_hours", {})
    cards = {k: {"key": k, "label": label, "budget_hours": budget.get(BUDGET_KEY.get(k, ""), None),
                 "issues": {"error": 0, "warning": 0, "info": 0}, "open": {"error": 0, "warning": 0},
                 "handled": 0, "reviewed": 0, "open_effect": {"federal": 0, "california": 0},
                 "changes": 0, "change_effect": {"federal": 0, "california": 0}, "documents": 0, "worst": [],
                 "inbox_open": 0, "grouped_open": {}}
             for k, label in AREAS.items()}
    for f in findings:
        card = cards[area_of(f.nodes, packet)]
        card["issues"][f.severity] += 1
        if f.severity == "info":
            continue
        st = finding_state(f, log, working.version)["state"]
        if st == "open":
            card["open"][f.severity] += 1
            card["open_effect"]["federal"] += f.federal_effect or 0
            card["open_effect"]["california"] += f.california_effect or 0
            card["worst"].append(f)
            family = f.check.split("-")[0]
            if family in GROUPED:  # the Inbox shows these inside one batch card, not under the area
                card["grouped_open"][family] = card["grouped_open"].get(family, 0) + 1
            else:
                card["inbox_open"] += 1
        elif st == "reviewed":
            card["reviewed"] += 1
        else:
            card["handled"] += 1
    for a in working.adjustments:
        card = cards[area_of([f"line:{working.version}:{a.key}"], packet)]
        card["changes"] += 1
        card["change_effect"]["federal"] += a.effect.get("federal") or 0
        card["change_effect"]["california"] += a.effect.get("california") or 0
    for d in packet.documents:
        cards[_DOC_AREA.get(d["document_type"], "intake")]["documents"] += 1
    out = []
    for c in cards.values():
        worst = sorted(c.pop("worst"), key=lambda f: (SEVERITY_RANK[f.severity],
                                                       -max(abs(f.federal_effect or 0), abs(f.california_effect or 0))))
        c["top_open"] = [{"id": f.id, "title": f.title, "severity": f.severity} for f in worst[:3]]
        for k in ("open_effect", "change_effect"):
            c[k] = {j: round(v) for j, v in c[k].items()}
        c["status"] = ("errors" if c["open"]["error"] else "warnings" if c["open"]["warning"]
                       else "review" if c["handled"] or c["changes"] else "clear")
        out.append(c)
    return out


def reconciliations(packet, verified: list[dict], findings, log: LogView, version: str) -> list[dict]:
    groups: dict[str, dict] = {}
    for family, heading, what in RECONCILIATION_KINDS:
        g = groups.setdefault(heading, {"title": heading, "agree": [], "differ": [], "covers": []})
        if what not in g["covers"]:
            g["covers"].append(what)
    family_of = {fam: heading for fam, heading, _ in RECONCILIATION_KINDS}
    for v in verified:
        heading = family_of.get(v["check"].split("-")[0])
        if heading:
            groups[heading]["agree"].append({"check": v["check"], "what": v["what"], "engine": v["engine"],
                                             "independent": v["independent"], "nodes": v["nodes"]})
    for f in findings:
        heading = family_of.get(f.check.split("-")[0])
        if heading and f.severity != "info":
            groups[heading]["differ"].append({
                "finding_id": f.id, "check": f.check, "title": f.title, "severity": f.severity,
                "state": finding_state(f, log, version)["state"],
                "corrections": [{"line": c.line, "current": c.current, "proposed": c.proposed} for c in f.corrections],
                "effect": {"federal": f.federal_effect, "california": f.california_effect}, "nodes": f.nodes[:4]})
    return list(groups.values())
