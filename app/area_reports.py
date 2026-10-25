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
from collections import defaultdict

from workpaper.working import WorkingReturn

from .inbox import finding_state
from .logview import LogView


class Ctx:
    def __init__(self, packet, working: WorkingReturn, findings, log: LogView):
        self.p, self.w, self.log = packet, working, log
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

    def check(self, label: str, engine, independent, note: str, limit: str | None = None) -> dict:
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


REPORTS = {
    "rentals": ("Rentals and passive losses", rentals),
    "deductions": ("Deductions, credits and limits", deductions),
    "k1": ("K-1s and S corporation basis", k1s),
    "state": ("State split", state_split),
}


def build_area_report(name: str, packet, working: WorkingReturn, findings, log: LogView) -> dict:
    if name not in REPORTS:
        raise KeyError(name)
    title, fn = REPORTS[name]
    c = Ctx(packet, working, findings, log)
    blocks = fn(c)
    issues = {i["id"] for b in blocks if b["type"] == "lines" for r in b["rows"] for i in r["issues"]}
    issues |= {f for b in blocks if b["type"] == "table" for r in b["rows"] for col in r["cols"].values() for f in col["issues"]}
    issues = sorted(issues)
    return {"name": name, "title": title, "version": working.version, "blocks": blocks, "issues": issues}
