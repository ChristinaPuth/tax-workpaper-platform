"""The working return: the engine's latest version with people's adjustments applied.

The engine cannot be rerun. So an adjustment flows downstream only where the arithmetic is
known (Plan C):

- Lines whose rule is R-SUM / R-CARRY are recomputed from their (working) inputs, using the same
  operator the engine used. R-SUM is not one operator - some lines add, some subtract, Schedule CA
  column D is A - B + C - so the operator is inferred per line from the engine's own numbers.
- Any other line that depends on a change keeps its engine value and is marked stale
  ("needs recompute"): tax brackets, phase-outs, limits and formulas are the engine's job.
- The tax effect of each adjustment is estimated the way the packet prescribes: change x the
  version's tax_effect_rates for the adjustment's category. Payments are not estimated - they
  flow through the payment lines arithmetically.

Every line reports how its number came to be: engine | adjusted | propagated | stale.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .packet import Packet

ARITH = ("R-SUM", "R-CARRY")
TOL = 1.0

# AGI thresholds where a first-order estimate stops being trustworthy (engine_reference.parameters)
AGI_THRESHOLDS = [
    ("niit_threshold", "net investment income tax threshold"),
    ("ctc_phaseout_start", "child tax credit phase-out start"),
    ("salt_cap_phase_start", "SALT cap phase-down start"),
]


def _num(v) -> float | None:
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


# ------------------------------------------------------------------ operators
def infer_operator(p: Packet, version: str, key: str) -> tuple[str, list[str]] | None:
    """(operator, dependency keys) that reproduce the engine's value for an R-SUM / R-CARRY line."""
    line = p.line(key, version)
    if line is None or line["rule"] not in ARITH or not line["inputs"]:
        return None
    value = _num(line["value"])
    inputs = line["inputs"]
    vals = [_num(p.line_value(i, version, default=None)) for i in inputs]
    if value is None or any(v is None for v in vals):
        return None
    candidates: list[tuple[str, float]] = [("sum", sum(vals))]
    if len(vals) > 1:
        candidates += [("diff", vals[0] - sum(vals[1:])), ("rdiff", sum(vals[1:]) - vals[0])]
    candidates += [(f"pick:{i}", v) for i, v in enumerate(vals)]
    for op, x in candidates:
        if abs(value - x) <= TOL:
            return op, list(inputs)
    m = re.match(r"^SchCA540NR\.(\w+)\.D$", key)  # Schedule CA column D = A - B + C
    if m:
        cols = [f"SchCA540NR.{m[1]}.{c}" for c in "ABC"]
        a, b, c = (_num(p.line_value(k, version, default=0)) or 0.0 for k in cols)
        if abs(value - (a - b + c)) <= TOL:
            return "ca_col", [k for k in cols if p.line(k, version) is not None]
    return None


def apply_operator(op: str, deps: list[str], get) -> float:
    vals = [get(k) for k in deps]
    if op == "sum":
        return sum(vals)
    if op == "diff":
        return vals[0] - sum(vals[1:])
    if op == "rdiff":
        return sum(vals[1:]) - vals[0]
    if op.startswith("pick:"):
        return vals[int(op.split(":")[1])]
    if op == "ca_col":
        by = dict(zip(deps, vals))
        col = lambda c: next((v for k, v in by.items() if k.endswith(f".{c}")), 0.0)
        return col("A") - col("B") + col("C")
    raise ValueError(op)


# ------------------------------------------------------------------ estimate categories
_SCHC_INCOME = {"1", "5", "7", "29", "31"}


def infer_category(key: str) -> tuple[str, int] | None:
    """(tax_effect_rates category, sign) for a change to this line, or None if not estimable.

    sign converts a change in the line into a change in the category's base: an expense line
    going up lowers profit (-1). 'payment' / 'ca_payment' flow arithmetically and are not estimated;
    'credit' / 'ca_credit' change tax 1:1.
    """
    form, _, rest = key.partition(".")
    if form == "F8949":
        box = rest.split(".")[0]
        return ("ltcg" if box in "DEFK" else "stcg"), 1
    if form == "SchD":
        n = re.match(r"\d+", rest)
        return (("stcg" if n and int(n.group()) <= 7 else "ltcg"), 1) if n else None
    if form == "SchC":
        base = rest.split(".")[0]
        if base in _SCHC_INCOME:
            return "schc_profit", 1
        if re.fullmatch(r"\d+[a-z]?", base) and (8 <= int(re.match(r"\d+", base).group()) <= 30):
            return "schc_profit", -1
        return None
    if form == "F4562-C":
        return "schc_profit", -1
    if form == "SchB" or key in ("F1040.2b", "F1040.3b", "F1040.3a"):
        return "interest", 1
    if key in ("F1040.1a", "F1040.1z"):
        return "wages", 1
    if key in ("Sch1.13", "Sch1.15", "Sch1.16", "Sch1.17", "Sch1.26", "F1040.10"):
        return "adjustment", 1
    if form == "SchA":
        return ("salt", 1) if rest.startswith(("5", "7")) else ("itemized", 1)
    if form == "F8283":
        return "itemized", 1
    if form == "SchE":
        m = re.match(r"(\d+)", rest)
        if m and 9 <= int(m.group(1)) <= 20:
            return "ordinary_income", -1
        return "ordinary_income", 1
    if form == "F4562-E":
        return "ordinary_income", -1
    if key.startswith(("F1040.25", "F1040.26")) or key in ("F1040.31", "F1040.33", "Sch3.10", "Sch3.11", "Sch3.15"):
        return "payment", 1
    if key.startswith(("F540NR.71", "F540NR.72", "F540NR.73", "F540NR.78")):
        return "ca_payment", 1
    if key in ("F1040.19", "F1040.20", "Sch3.1", "Sch3.8", "F8812.12"):
        return "credit", 1
    if key == "ScheduleS.credit":
        return "ca_credit", 1
    if form == "SchCA540NR" and key.endswith(".E"):
        return "ca_source_income", 1
    return None


def estimate(p: Packet, key: str, delta: float, category: str | None = None,
             version: str | None = None) -> dict:
    """First-order tax effect of changing one line by delta: {category, federal, california, estimated}."""
    if category:
        cat, sign = category, 1
    else:
        inferred = infer_category(key)
        if inferred is None:
            return {"category": None, "federal": None, "california": None, "estimated": False}
        cat, sign = inferred
    base = delta * sign
    if cat in ("payment", "ca_payment"):  # flows through the payment lines; no estimate needed
        return {"category": cat, "federal": 0.0, "california": 0.0, "estimated": False}
    if cat == "credit":
        return {"category": cat, "federal": -base, "california": 0.0, "estimated": True}
    if cat == "ca_credit":
        return {"category": cat, "federal": 0.0, "california": -base, "estimated": True}
    rf, rc = p.tax_effect_rate(cat, version)
    return {"category": cat, "federal": round(base * rf, 2), "california": round(base * rc, 2), "estimated": True}


# ------------------------------------------------------------------ the working return
@dataclass
class Adjustment:
    event_id: int
    key: str
    engine: float | str | None
    new: float | str
    actor: str
    reason: str
    at: str
    category: str | None = None
    effect: dict = field(default_factory=dict)


@dataclass
class WorkingReturn:
    version: str
    lines: dict[str, dict]            # only lines whose number or status differs from the engine
    adjustments: list[Adjustment]
    estimate: dict
    summary: dict
    warnings: list[str]

    def to_dict(self) -> dict:
        return {"version": self.version, "lines": self.lines,
                "adjustments": [a.__dict__ for a in self.adjustments], "estimate": self.estimate,
                "summary": self.summary, "warnings": self.warnings}


def active_adjustments(events: list[dict]) -> list[dict]:
    """Adjust events not undone, latest per target winning."""
    undone = {e["payload"].get("event_id") for e in events if e["type"] == "undo"}
    latest: dict[str, dict] = {}
    for e in events:
        if e["type"] == "adjust" and e["id"] not in undone and e.get("target"):
            latest[e["target"]] = e
    return sorted(latest.values(), key=lambda e: e["id"])


def build(p: Packet, index, events: list[dict], version: str | None = None) -> WorkingReturn:
    version = version or p.latest["version"]
    lines = p.lines[version]
    adj = active_adjustments(events)

    overrides: dict[str, Adjustment] = {}
    touched_sources: set[str] = set()  # lines citing an adjusted extracted value
    for e in adj:
        target = e["target"]
        if target.startswith(f"line:{version}:"):
            key = target.split(":", 2)[2]
            if key not in lines:
                continue
            new = e["payload"]["new_value"]
            overrides[key] = Adjustment(e["id"], key, lines[key]["value"], new, e["actor"],
                                        e["payload"].get("reason", ""), e["at"], e["payload"].get("category"))
        elif target.startswith("ev:"):
            for lid in index.sources(target, "sourced_from"):
                if lid.startswith(f"line:{version}:"):
                    touched_sources.add(lid.split(":", 2)[2])

    ops = {k: infer_operator(p, version, k) for k, l in lines.items() if l["rule"] in ARITH}
    deps = {k: (ops[k][1] if ops.get(k) else lines[k]["inputs"]) for k in lines}

    memo: dict[str, tuple[float | str | None, str, bool]] = {}  # key -> (value, kind, partial)

    def resolve(key: str, stack: tuple = ()) -> tuple[float | str | None, str, bool]:
        if key in memo:
            return memo[key]
        line = lines.get(key)
        if line is None:
            return (None, "engine", False)
        if key in overrides:
            out = (overrides[key].new, "adjusted", False)
        elif key in stack:  # defensive: the engine's graph is acyclic
            out = (line["value"], "engine", False)
        else:
            results = {d: resolve(d, stack + (key,)) for d in deps[key] if d in lines}
            changed = [d for d, r in results.items() if r[1] != "engine"]
            if key in touched_sources:
                out = (line["value"], "stale", False)
            elif not changed:
                out = (line["value"], "engine", False)
            elif ops.get(key) and all(_num(r[0]) is not None for r in results.values()):
                op, ds = ops[key]
                value = apply_operator(op, ds, lambda d: _num(results[d][0]) if d in results else 0.0)
                partial = any(r[1] == "stale" or r[2] for r in results.values())
                if partial and _num(line["value"]) is not None and abs(value - float(line["value"])) <= TOL:
                    out = (line["value"], "stale", False)  # only stale inputs moved it: nothing known changed
                else:
                    out = (round(value, 2), "propagated", partial)
            else:
                out = (line["value"], "stale", False)
        memo[key] = out
        return out

    changed_lines: dict[str, dict] = {}
    for key in lines:
        value, kind, partial = resolve(key)
        if kind != "engine":
            changed_lines[key] = {"engine": lines[key]["value"], "value": value, "kind": kind, "partial": partial}

    fed = ca = 0.0
    not_estimated = []
    for a in overrides.values():
        eng, new = _num(a.engine), _num(a.new)
        if eng is None or new is None:
            a.effect = {"category": None, "federal": None, "california": None, "estimated": False}
            continue
        a.effect = estimate(p, a.key, new - eng, a.category, version)
        a.category = a.effect["category"]
        if a.effect["estimated"]:
            fed += a.effect["federal"]
            ca += a.effect["california"]
        elif a.category not in ("payment", "ca_payment"):
            not_estimated.append(a.key)

    def working(key: str) -> float | None:
        return _num(resolve(key)[0])

    def engine_v(key: str) -> float | None:
        return _num(p.line_value(key, version, default=None))

    s = p.version[version]["summary"]
    summary = {
        "agi": {"engine": engine_v("F1040.11"), "value": working("F1040.11"), "kind": resolve("F1040.11")[1]},
        "total_tax": {"engine": s["federal"]["total_tax"], "value": round(s["federal"]["total_tax"] + fed)},
        "balance_due": {"engine": s["federal"]["balance_due"],
                        "value": round((working("F1040.37") or 0) + fed)},
        "ca_total_tax": {"engine": s["california"]["total_tax"], "value": round(s["california"]["total_tax"] + ca)},
        "ca_balance_due": {"engine": s["california"]["balance_due"],
                           "value": round(-(working("F540NR.97") or 0) + ca)},
    }

    warnings = []
    params = p.raw["engine_reference"]["parameters"]
    a0, a1 = summary["agi"]["engine"], summary["agi"]["value"]
    if a0 is not None and a1 is not None:
        for name, label in AGI_THRESHOLDS:
            t = params.get(name)
            if t is not None and (a0 - t) * (a1 - t) < 0:
                warnings.append(f"AGI moves across the {label} ({t:,.0f}): the estimate may be off - the engine "
                                f"must recompute.")
    if s["federal"]["total_tax"] and abs(fed) > 0.05 * s["federal"]["total_tax"]:
        warnings.append("Adjustments change federal tax by more than 5%: rates are first-order, so treat the "
                        "estimate as a direction, not a number.")
    if not_estimated:
        warnings.append("No rate applies to " + ", ".join(sorted(not_estimated)) + " - effect not estimated.")

    return WorkingReturn(version, changed_lines, list(overrides.values()),
                         {"federal": round(fed), "california": round(ca), "method": "change x tax_effect_rates"},
                         summary, warnings)
