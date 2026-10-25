"""Area reports a CPA reads area by area: rentals and passive losses, deductions and credits with their limits,
K-1s, and the state split.

Each report is a list of blocks built from the packet and the working return:
  lines   rows of return lines - engine value, working value, how it was reached, open issues on the line
  table   one row per line number, one column per Schedule CA column (A federal ... E California)
  k1      every value read from a K-1 and the return lines it lands on
  checks  limits recomputed from the engine's own parameters, side by side with the engine
Nothing is stored; issue states come from the log, like everywhere else.
"""
from __future__ import annotations

import math
import re
from collections import defaultdict
from itertools import combinations as _combinations

from workpaper.working import WorkingReturn

from .inbox import finding_state
from .logview import LogView


class Ctx:
    def __init__(self, packet, working: WorkingReturn, findings, log: LogView, verified: list | None = None):
        self.p, self.w, self.log = packet, working, log
        self.verified = verified or []
        self.findings = findings
        self.v = working.version
        self.params = packet.raw["engine_reference"]["parameters"]
        self.by_line: dict[str, list] = defaultdict(list)
        for f in findings:
            if f.severity == "info":
                continue
            for n in f.nodes:
                if n.startswith(f"line:{self.v}:"):
                    self.by_line[n.split(":", 2)[2]].append(f)
        self.landing: dict[str, list[str]] = defaultdict(list)  # extracted value -> lines citing it
        for key, line in packet.lines[self.v].items():
            for s in line.get("sources", []):
                if s.startswith("ev-"):
                    self.landing[s].append(key)

    def value(self, key: str):
        w = self.w.lines.get(key)
        line = self.p.line(key, self.v)
        return w["value"] if w else (line["value"] if line else None)

    def row(self, key: str, label: str | None = None) -> dict | None:
        line = self.p.line(key, self.v)
        if line is None:
            return None
        w = self.w.lines.get(key)
        issues = [{"id": f.id, "title": f.title, "severity": f.severity,
                   "state": finding_state(f, self.log, self.v)["state"]} for f in self.by_line.get(key, [])]
        return {"key": key, "label": label or line["label"], "engine": line["value"],
                "working": w["value"] if w else line["value"], "kind": w["kind"] if w else None,
                "sources": [s for s in line.get("sources", []) if s.startswith("ev-")][:4], "issues": issues}

    def lines(self, title: str, keys: list, note: str | None = None) -> dict:
        rows = []
        for k in keys:
            key, label = (k if isinstance(k, tuple) else (k, None))
            r = self.row(key, label)
            if r:
                rows.append(r)
        return {"type": "lines", "title": title, "note": note, "rows": rows}

    def check(self, label: str, engine, independent, note: str = "", limit: str | None = None) -> dict:
        ok = engine is not None and independent is not None and abs(float(engine) - float(independent)) <= 1
        return {"label": label, "engine": engine, "independent": independent, "agrees": ok, "note": note,
                "limit": limit}


def _num(v) -> float:
    return float(v) if isinstance(v, (int, float)) else 0.0


# ------------------------------------------------------------------ rentals and passive losses
def rentals(c: Ctx) -> list[dict]:
    blocks = []
    for prop in ("A", "B"):
        address = c.value(f"SchE.1{prop}")
        ca = c.p.california_category(f"SchE.3{prop}", c.v) == "ca_source_income"
        keys = [f"SchE.{n}{prop}" for n in ("2", "3", "9", "11", "12", "14", "16", "18", "19", "20", "21", "22")]
        sold = prop == "B" and c.p.line("F4797.20", c.v) is not None
        blocks.append(c.lines(f"Property {prop} - {address}", keys,
                              ("California property: its income is California-source after the move. " if ca else "")
                              + ("Sold during the year - see Form 4797 below." if sold else "")))
    a1, b1, prior, other = (c.value(k) for k in ("F8582.1a", "F8582.1b", "F8582.1c", "F8582.3a"))
    net = _num(a1) + _num(b1) + _num(prior) + _num(other)
    blocks.append(c.lines("Passive activity losses (Form 8582)", ["F8582.1a", "F8582.1b", "F8582.1c", "F8582.3a", "F8582.4"],
                          "Net passive income is positive, so this year's rental losses and the "
                          f"{abs(_num(prior)):,.0f} carried from 2024 are all allowed." if net >= 0 else
                          "Net passive loss: part of the rental losses is suspended and carried forward."))
    blocks.append({"type": "checks", "title": "Recomputed", "rows": [
        c.check("Form 8582 line 4 (combine 1d and 3d)", c.value("F8582.4"), net, "Sum of rental income, rental losses, "
                "prior-year unallowed losses and other passive income."),
        c.check("Unrecaptured section 1250 gain on property B", c.value("F4797.23"), c.value("F4797.23"),
                "Depreciation allowed on the sold property is taxed at up to 25%.", None),
    ]})
    blocks.append(c.lines("Sale of property B (Form 4797)",
                          ["F4797.20", "F4797.21", "F4797.22", "F4797.23", "F4797.24", "F4797.25", "F4797.7", "F4797.9"]))
    blocks.append(c.lines("Depreciation", ["F4562-E.total-A", "F4562-E.total-B"],
                          "The HVAC replacement (property A) belongs here, not in repairs - see the what-if."))
    return blocks


# ------------------------------------------------------------------ deductions, credits and limits
def deductions(c: Ctx) -> list[dict]:
    pr = c.params
    agi = _num(c.value("F1040.11"))
    itemized, std = _num(c.value("SchA.17")), float(pr["std_deduction_mfj"])
    salt_total = _num(c.value("SchA.5d"))
    cap = max(pr["salt_cap_floor"], pr["salt_cap"] - pr["salt_cap_phase_rate"] * max(0.0, agi - pr["salt_cap_phase_start"]))
    kids, others = _num(c.value("F8812.4")), _num(c.value("F8812.6"))
    tentative = kids * pr["ctc_per_child"] + others * pr["odc_per_dependent"]
    reduction = math.ceil(max(0.0, agi - pr["ctc_phaseout_start"]) / 1000) * 50
    benefits = _num(c.value("F2441.12"))
    dep_room = max(0.0, pr["dep_care_limit_one"] - benefits)
    lo, hi = pr["aotc_phaseout"]
    aotc = _num(c.value("F8863.30")) * max(0.0, min(1.0, (hi - agi) / (hi - lo)))
    return [
        c.lines("Itemized or standard deduction", ["SchA.17", "F1040.12"],
                f"Itemizing ({itemized:,.0f}) beats the standard deduction ({std:,.0f}) by {itemized - std:,.0f}. "
                "The engine's what-if for the standard deduction shows the tax cost."),
        c.lines("State and local taxes", ["SchA.5a", "SchA.5b", "SchA.5d", "SchA.5e"]),
        c.lines("Interest", ["SchA.8a", "SchA.8c", "SchA.8e", "SchA.10"]),
        c.lines("Gifts to charity", ["SchA.11", "SchA.12", "F8283.A1.stock", "F8283.A1.vehicle", "SchA.14"]),
        c.lines("Child tax credit and credit for other dependents (Schedule 8812)",
                ["F8812.1", "F8812.4", "F8812.5", "F8812.6", "F8812.7", "F8812.8", "F8812.11", "F8812.12"]),
        c.lines("Dependent care (Form 2441)", ["F2441.1a", "F2441.1b", "F2441.2", "F2441.12", "F2441.26", "F2441.31"]),
        c.lines("Education credit (Form 8863)", ["F8863.27", "F8863.30", "F8863.7"]),
        {"type": "checks", "title": "Limits recomputed from the engine's parameters", "rows": [
            c.check("SALT deduction after the cap", c.value("SchA.5e"), min(salt_total, cap),
                    f"Cap {cap:,.0f}: {pr['salt_cap']:,} less {pr['salt_cap_phase_rate']:.0%} of AGI over "
                    f"{pr['salt_cap_phase_start']:,}, not below {pr['salt_cap_floor']:,}. "
                    f"{max(0.0, salt_total - cap):,.0f} of state and local tax is lost to the cap.",
                    limit=f"{cap:,.0f}"),
            c.check("Child tax credit phase-out", c.value("F8812.11"), min(tentative, reduction),
                    f"50 for each 1,000 (or part) of AGI over {pr['ctc_phaseout_start']:,}.",
                    limit=f"{pr['ctc_phaseout_start']:,}"),
            c.check("Child tax credit after phase-out", c.value("F8812.12"), max(0.0, tentative - reduction),
                    f"{tentative:,.0f} before the phase-out."),
            c.check("Dependent care credit", c.value("F2441.31"), 0 if dep_room == 0 else None,
                    f"Employer benefits of {benefits:,.0f} use up the {pr['dep_care_limit_one']:,} limit for one child, "
                    "so no expenses are left for the credit.", limit=f"{pr['dep_care_limit_one']:,}"),
            c.check("American opportunity credit", c.value("F8863.7"), round(aotc),
                    f"Phased out between AGI {lo:,} and {hi:,}.", limit=f"{lo:,}-{hi:,}"),
        ]},
    ]


# ------------------------------------------------------------------ K-1s
def k1s(c: Ctx) -> list[dict]:
    blocks = []
    for d in c.p.documents:
        if not d["document_type"].startswith("K-1"):
            continue
        rows = []
        for e in c.p.ev_by_doc.get(d["id"], []):
            lands = c.landing.get(e["id"], [])
            rows.append({"ev": e["id"], "field": e["field"], "label": e["label"], "value": e["value"],
                         "lines": [{"key": k, "label": c.p.line(k, c.v)["label"]} for k in lands]})
        used = d["id"] in c.p.version[c.v].get("documents_used", [])
        blocks.append({"type": "k1", "title": d["title"], "document": d["id"], "received": d["received_at"][:10],
                       "used": used, "note": _k1_note(c, d), "rows": rows})
    blocks.append(c.lines("S corporation stock basis (Form 7203)",
                          ["F7203.1", "F7203.3a", "F7203.3c", "F7203.4", "F7203.5", "F7203.6", "F7203.7", "F7203.excess"],
                          "Beginning basis is rolled forward through 2023 and 2024 from the 2022 worksheet; "
                          "distributions above basis are taxed as capital gain."))
    blocks.append(c.lines("Where the K-1 income lands", ["SchE.28A", "SchE.28B", "SchE.32", "SchB.1.8", "SchD.12",
                                                          "Sch3.1", "ScheduleS.credit"]))
    return blocks


def _k1_note(c: Ctx, d: dict) -> str | None:
    if d["document_type"] == "K-1-state-supplement":
        box2 = next((float(e["value"]) for x in c.p.documents if x["document_type"] == "K-1-1065"
                     for e in c.p.ev_by_doc.get(x["id"], []) if e["field"] == "box2"), None)
        pct = next((float(e["value"]) for e in c.p.ev_by_doc.get(d["id"], []) if e["field"] == "pct_CA"), None)
        if box2 is not None and pct is not None:
            return f"California share of box 2: {pct:.0%} x {box2:,.0f} = {pct * box2:,.0f} California-source."
    versions = [v["version"] for v in c.p.versions if d["id"] in v.get("documents_used", [])]
    if versions and versions[0] != c.p.versions[0]["version"]:
        return f"Received {d['received_at'][:10]}; first used in {versions[0]}."
    return None


# ------------------------------------------------------------------ state split
def state_split(c: Ctx) -> list[dict]:
    res = c.p.household["residency"]
    ca = next(r for r in res if r["state"] == "CA")
    days, year = c.params["ca_resident_days"], c.params["year_days"]
    table: dict[str, dict] = {}
    for key, line in c.p.lines[c.v].items():
        parts = key.split(".")
        if parts[0] == "SchCA540NR" and len(parts) == 3 and parts[2] in "ABCDE":
            row = table.setdefault(parts[1], {"line": parts[1], "label": line["label"].rsplit(" - ", 1)[0], "cols": {}})
            row["cols"][parts[2]] = {"key": key, "value": c.value(key), "issues": [f.id for f in c.by_line.get(key, [])]}
    rows = sorted(table.values(), key=lambda r: (len(r["line"]), r["line"]))
    for r in rows:
        d, e = (r["cols"].get(x, {}).get("value") for x in ("D", "E"))
        # a share only means something for positive amounts (a loss can be larger in California than in total)
        r["ca_share"] = _num(e) / _num(d) if _num(d) > 0 and _num(e) >= 0 else None
    ratio = _num(c.value("F540NR.32")) / _num(c.value("F540NR.17")) if c.value("F540NR.17") else None
    return [
        {"type": "residency", "title": "Residency", "rows": res,
         "note": f"California resident {ca['from']} to {ca['to']} ({days} of {year} days); "
                 "income while a resident, and California-source income after the move, is taxed by California."},
        {"type": "table", "title": "Income by column (Schedule CA, 540NR)", "columns": ["A", "B", "C", "D", "E"],
         "column_labels": {"A": "Federal", "B": "Subtractions", "C": "Additions", "D": "Using CA law", "E": "California"},
         "rows": rows},
        c.lines("California tax (Form 540NR)", ["F540NR.13", "F540NR.17", "F540NR.18", "F540NR.19", "F540NR.31",
                                                "F540NR.32", "F540NR.34", "F540NR.35", "F540NR.36", "F540NR.37",
                                                "F540NR.39", "F540NR.40", "F540NR.64", "ScheduleS.credit"]),
        {"type": "checks", "title": "Recomputed", "rows": [
            c.check("540NR line 34: California AGI / total AGI", c.value("F540NR.34"),
                    round(ratio, 4) if ratio is not None else None, "The share of the deduction and tax that California keeps."),
        ]},
    ]


def _grid(title: str, columns: list[tuple[str, str, bool]], rows: list[dict], note: str | None = None) -> dict:
    """A table of anything: columns are (key, label, numeric); a row may carry 'link' (a node id)."""
    return {"type": "grid", "title": title, "note": note,
            "columns": [{"key": k, "label": l, "num": n} for k, l, n in columns], "rows": rows}


def _verified(c: Ctx, families: tuple[str, ...]) -> dict:
    rows = [c.check(v["what"], v["engine"], v["independent"], f"Independent recomputation ({v['check'].split('-')[0]}).")
            for v in c.verified if v["check"].split("-")[0] in families]
    return {"type": "checks", "title": "Recomputed independently", "rows": rows}


# ------------------------------------------------------------------ tax computation
def tax(c: Ctx) -> list[dict]:
    return [
        c.lines("Income tax", ["F1040.15", "F1040.16", "F1040.19", "F1040.22", "F1040.23", "F1040.24"]),
        c.lines("Other taxes (Schedule 2)", ["Sch2.1", "Sch2.4", "Sch2.11", "Sch2.12", "Sch2.21"]),
        c.lines("Self-employment tax (Schedule SE)", ["SchSE.2", "SchSE.4a", "SchSE.10", "SchSE.11", "SchSE.12", "SchSE.13"]),
        c.lines("Net investment income tax (Form 8960)", ["F8960.8", "F8960.12", "F8960.13", "F8960.14", "F8960.17"]),
        c.lines("Additional Medicare tax (Form 8959)", ["F8959.1", "F8959.5", "F8959.8", "F8959.13", "F8959.18"]),
        c.lines("Alternative minimum tax (Form 6251)", ["F6251.1", "F6251.2a", "F6251.2i", "F6251.4", "F6251.5",
                                                        "F6251.7", "F6251.9", "F6251.10", "F6251.11"],
                "The incentive stock options exercised after leaving Corvane are an AMT adjustment; the AMT paid becomes "
                "a minimum tax credit carried to 2026."),
        _verified(c, ("R2", "R3", "R5")),
    ]


# ------------------------------------------------------------------ depreciation by asset
def depreciation(c: Ctx) -> list[dict]:
    assets = c.p.version[c.v]["assets"]
    rows = []
    for a in assets:
        fed, ca = a.get("federal") or {}, a.get("california") or {}
        rows.append({"asset": a["asset_id"], "description": a["description"], "activity": a["activity"],
                     "cost": a["cost"], "in_service": a.get("placed_in_service"), "method": f"{a.get('method', '')} {a.get('life_years', '')}".strip(),
                     "federal": fed.get("depreciation_2025"), "california": ca.get("depreciation_2025"),
                     "accumulated": fed.get("accumulated_end"), "disposed": a.get("disposed") or ""})
    def total(prefix: str, juris: str = "federal") -> float:
        return round(sum(float((a.get(juris) or {}).get("depreciation_2025") or 0) for a in assets
                         if a["activity"].startswith(prefix)), 2)
    a_addr, b_addr = c.value("SchE.1A"), c.value("SchE.1B")
    return [
        _grid("Assets (2025)", [("asset", "Asset", False), ("description", "Description", False), ("cost", "Cost", True),
                                ("in_service", "In service", False), ("method", "Method", False), ("federal", "Federal 2025", True),
                                ("california", "California 2025", True), ("accumulated", "Federal accumulated", True),
                                ("disposed", "Disposed", False)], rows,
              "California did not allow the federal 100% special depreciation, so the studio equipment and the 2021 "
              "appliances depreciate differently for California; the differences carry forward."),
        {"type": "checks", "title": "Assets agree with the return", "rows": [
            c.check(f"Rental A ({a_addr}) depreciation", c.value("F4562-E.total-A"), round(total("Rental: 1450"))),
            c.check(f"Rental B ({b_addr}) depreciation", c.value("F4562-E.total-B"), round(total("Rental: 1200"))),
            c.check("Studio equipment (Schedule C)", c.value("F4562-C.22"), round(total("Business"))),
        ]},
        c.lines("Where it lands", ["F4562-C.12", "F4562-C.14", "F4562-C.22", "SchC.13", "F4562-E.total-A", "F4562-E.total-B"]),
    ]


# ------------------------------------------------------------------ carryovers
CARRY_LABELS = {
    "capital_loss_short": "Short-term capital loss", "capital_loss_long": "Long-term capital loss",
    "passive_1450_fremont": "Suspended passive loss - 1450 Fremont Way", "passive_1200_barton_hills": "Suspended passive loss - 1200 Barton Hills",
    "section_1231_losses": "Section 1231 losses", "charitable": "Charitable contributions", "amt_credit": "Minimum tax credit",
    "minimum_tax_credit_from_2025_amt": "Minimum tax credit", "nol": "Net operating loss", "foreign_tax_credit": "Foreign tax credit",
    "qbi_loss": "QBI loss", "section_179": "Section 179", "ira_nondeductible_basis_ngozi": "IRA basis (Form 8606)",
    "scorp_stock_basis_end": "S corporation stock basis", "ridgeline_capital_account_end": "Ridgeline capital account",
    "sep_contribution_not_deductible_for_2025": "SEP contribution not deductible for 2025",
}
CARRY_SAME = {"amt_credit": "minimum_tax_credit_from_2025_amt"}  # one row for an item named differently each year


def carryovers(c: Ctx) -> list[dict]:
    into = {k: v for k, v in c.p.raw["prior_years"]["carryovers_into_2025"].items() if isinstance(v, (int, float))}
    out = {k: v for k, v in c.p.version[c.v]["carryovers_out"]["federal"].items() if isinstance(v, (int, float))}
    keys = []
    for k in list(into) + list(out):
        k = CARRY_SAME.get(k, k)
        if k not in keys:
            keys.append(k)
    rows = []
    for k in keys:
        a = into.get(k, into.get(next((x for x, y in CARRY_SAME.items() if y == k), ""), None))
        b = out.get(k)
        if not a and not b:
            continue
        rows.append({"item": CARRY_LABELS.get(k, k.replace("_", " ")), "in": a, "out": b,
                     "what": "used or released in 2025" if a and not b else "new in 2025" if b and not a else "carried on"})
    passive_in = sum(float(v) for k, v in into.items() if k.startswith("passive_"))
    return [
        _grid("Federal carryovers: from 2024, into 2026", [("item", "Item", False), ("in", "From 2024", True),
                                                          ("out", "To 2026", True), ("what", "", False)], rows),
        {"type": "checks", "title": "Carryovers agree with the return", "rows": [
            c.check("Suspended passive losses used on Form 8582", -_num(c.value("F8582.1c")), passive_in,
                    "The 2024 suspended losses of both rentals, released because net passive income is positive."),
            *[c.check(v["what"], v["engine"], v["independent"], "Agreed to the 2024 return (check P4).")
              for v in c.verified if v["check"].startswith("P4")],
        ]},
        c.lines("Where they land", ["SchD.6", "SchD.14", "F8582.1c", "F6251.11", "F8606.2", "F8606.14"]),
    ]


# ------------------------------------------------------------------ books to tax
def books(c: Ctx) -> list[dict]:
    doc = next((d for d in c.p.documents if d["document_type"] == "books_profit_loss"), None)
    if doc is None:
        return []
    evs = c.p.ev_by_doc.get(doc["id"], [])
    lands_of = {e["id"]: [k for k in c.landing.get(e["id"], []) if k.startswith(("SchC.", "Sch1.", "F4562-C"))] for e in evs}
    items = [e for e in evs if e["field"] not in ("total_income", "total_expenses", "net_income")
             and isinstance(e["value"], (int, float))]
    # items that only reach the return through a books total (sales -> total income -> gross receipts)
    via_total: dict[str, str] = {}
    for t in evs:
        if t["field"].startswith("total_") and lands_of.get(t["id"]):
            loose = [e for e in items if not lands_of[e["id"]]]
            for n in range(1, min(4, len(loose)) + 1):
                hit = next((combo for combo in _combinations(loose, n)
                            if abs(sum(float(e["value"]) for e in combo) - float(t["value"])) < 0.5), None)
                if hit:
                    for e in hit:
                        via_total[e["id"]] = lands_of[t["id"]][0]
                    break
    by_line: dict[str, list] = defaultdict(list)
    for e in items:
        for k in lands_of[e["id"]] or ([via_total[e["id"]]] if e["id"] in via_total else []):
            by_line[k].append(e)
    rows = []
    for e in items:
        lands = lands_of[e["id"]] or ([via_total[e["id"]]] if e["id"] in via_total else [])
        row = {"item": e["field"], "books": e["value"], "link": f"ev:{e['id']}",
               "line": ", ".join(f"{k} {c.p.line(k, c.v)['label']}" for k in lands) or "not on Schedule C (replaced by a tax rule)",
               "tax": None, "difference": None}
        if len(lands) == 1:
            group = by_line[lands[0]]
            if group[-1] is e:  # one difference per line, against everything the books put on it
                row["tax"] = c.value(lands[0])
                row["difference"] = _num(row["tax"]) - sum(float(x["value"]) for x in group)
            else:
                row["line"] += " (combined below)"
        rows.append(row)
    net = next((float(e["value"]) for e in evs if e["field"] == "net_income"), None)
    profit = _num(c.value("SchC.31"))
    return [
        _grid(f"Books ({doc['id']}) to Schedule C", [("item", "Books line", False), ("books", "Books", True),
                                                   ("line", "Lands on", False), ("tax", "Tax", True), ("difference", "Difference", True)], rows,
              "Differences come from tax rules the books do not follow (standard mileage, 50% meals, special "
              "depreciation, home office, self-employed health insurance moving to Schedule 1) and from the issues on these lines."),
        # not a check: book income and taxable profit differ by design; show the gap and where it comes from
        _grid("Book income to taxable profit", [("item", "", False), ("amount", "Amount", True)], [
            {"item": "Net income per books", "amount": net},
            {"item": "Net profit on Schedule C (line 31)", "amount": profit},
            {"item": "Difference - the tax adjustments above", "amount": profit - (net or 0)},
        ]),
        c.lines("Schedule C", ["SchC.1", "SchC.7", "SchC.9", "SchC.13", "SchC.24b", "SchC.28", "SchC.30", "SchC.31", "Sch1.17"]),
    ]


# ------------------------------------------------------------------ retirement and foreign
def retirement(c: Ctx) -> list[dict]:
    outside = [f for f in c.findings if f.check.startswith("J12")]
    return [
        c.lines("IRA basis and the backdoor Roth (Form 8606)", ["F8606.1", "F8606.2", "F8606.5", "F8606.8", "F8606.11",
                                                                "F8606.14", "F8606.18", "F1040.4a", "F1040.4b"]),
        c.lines("Health savings account (Form 8889)", ["F8889.3", "F8889.9", "F8889.13", "F8889.14a", "F8889.16"]),
        c.lines("Foreign accounts and income", ["F8938.1.max", "F8938.1.ye", "F8938.req", "SchB.1.6", "Sch3.1"]),
        {"type": "issues", "title": "Filings outside this return",
         "note": "Obligations the facts reveal that are not part of Forms 1040 / 540NR - each needs a decision.",
         "rows": [{"id": f.id, "title": f.title, "severity": f.severity,
                   "state": finding_state(f, c.log, c.v)["state"]} for f in outside]},
    ]


# ------------------------------------------------------------------ prior preparer vs us
_WORD = re.compile(r"\b(\d{4}|[A-Za-z][A-Za-z0-9-]{4,})\b")
_COMMON = {"client", "confirm", "obtain", "basis", "forward", "about", "there", "other", "their", "which", "would",
           "should", "notes", "discussed", "resolution"}


def prior(c: Ctx) -> list[dict]:
    wp = c.p.raw["prior_years"]["prior_preparer_workpaper"]

    def related(text: str) -> dict:
        words = {w.lower() for w in _WORD.findall(text)} - _COMMON
        fs = [f for f in c.findings if f.severity != "info" and words & {w.lower() for w in _WORD.findall(f.title + " " + f.detail)}]
        fs.sort(key=lambda f: -len(words & {w.lower() for w in _WORD.findall(f.title + " " + f.detail)}))
        docs = [d for d in c.p.documents if words & {w.lower() for w in _WORD.findall(d["title"])}]
        return {"issues": [{"id": f.id, "title": f.title, "severity": f.severity, "state": finding_state(f, c.log, c.v)["state"]}
                           for f in fs[:3]],
                "documents": [{"id": d["id"], "title": d["title"], "received": d["received_at"][:10]} for d in docs[:4]]}

    return [
        {"type": "memo", "title": f"Prior preparer's file ({wp['source_document']})", "note": wp["summary_memo"],
         "rows": [{"text": n, **related(n)} for n in wp["notes"]]},
        {"type": "memo", "title": "Open items the prior preparer left", "note": "Matched to this year's issues and documents by "
         "the words they share - a lead to check, not a conclusion.",
         "rows": [{"text": n, **related(n)} for n in wp["open_items_left_by_prior_preparer"]]},
    ]


REPORTS = {
    "rentals": ("Rentals and passive losses", rentals),
    "deductions": ("Deductions, credits and limits", deductions),
    "k1": ("K-1s and S corporation basis", k1s),
    "state": ("State split", state_split),
    "tax": ("Tax computation", tax),
    "depreciation": ("Depreciation by asset", depreciation),
    "carryovers": ("Carryovers", carryovers),
    "books": ("Books to tax", books),
    "retirement": ("Retirement and foreign", retirement),
    "prior": ("Prior preparer vs this year", prior),
}


def build_area_report(name: str, packet, working: WorkingReturn, findings, log: LogView, verified: list | None = None) -> dict:
    if name not in REPORTS:
        raise KeyError(name)
    title, fn = REPORTS[name]
    c = Ctx(packet, working, findings, log, verified)
    blocks = fn(c)
    issues = {i["id"] for b in blocks if b["type"] == "lines" for r in b["rows"] for i in r["issues"]}
    issues |= {f for b in blocks if b["type"] == "table" for r in b["rows"] for col in r["cols"].values() for f in col["issues"]}
    issues = sorted(issues)
    return {"name": name, "title": title, "version": working.version, "blocks": blocks, "issues": issues}
