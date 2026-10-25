"""Checks that don't trust the engine: re-derive results from inputs and the engine's own published parameters."""
from __future__ import annotations

import math
import re

from ..findings import Correction
from .base import Ctx, check, fmt

TOL = 2.0  # whole-dollar rounding across several steps


def _bracket_tax(income: float, brackets: list) -> float:
    tax, lower = 0.0, 0.0
    for upper, rate in brackets:
        top = income if upper is None else min(income, upper)
        if top > lower:
            tax += (top - lower) * rate
        if upper is None or income <= upper:
            break
        lower = upper
    return tax


def _compare(c: Ctx, check_id: str, key: str, independent: float, what: str, extra_nodes=()):
    engine = c.p.line_value(key)
    if engine is None or isinstance(engine, str):
        return
    if abs(float(engine) - independent) <= TOL:
        c.ok(check_id, what, engine, round(independent, 2), [c.L(key)])
    else:
        c.add(check_id, f"{key} = {fmt(engine)} but independent recomputation gives {fmt(round(independent))}",
              "error", "engine", f"{what}. Engine {fmt(engine)}, recomputed {fmt(round(independent, 2))}.",
              nodes=[c.L(key), *extra_nodes])


@check("R1-line-arithmetic")
def line_arithmetic(c: Ctx):
    """Every R-SUM / R-CARRY line must equal its inputs (sum, or first minus the rest)."""
    bad = 0
    for key, line in c.p.lines[c.ver].items():
        if line["rule"] not in ("R-SUM", "R-CARRY") or not line["inputs"] or isinstance(line["value"], str):
            continue
        vals = [c.p.line_value(i) for i in line["inputs"]]
        if any(isinstance(v, str) or v is None for v in vals):
            continue
        v = float(line["value"])
        candidates = [sum(vals), vals[0] - sum(vals[1:]), abs(vals[0] - sum(vals[1:])), *vals]
        m = re.match(r"^SchCA540NR\.(\w+)\.D$", key)
        if m:  # Schedule CA column D = A - B + C
            col = lambda x: float(c.p.line_value(f"SchCA540NR.{m[1]}.{x}", default=0) or 0)
            candidates.append(col("A") - col("B") + col("C"))
        if not any(abs(v - x) <= 1.0 for x in candidates):
            bad += 1
            c.add("R1-line-arithmetic", f"{key} = {fmt(v)} does not follow from its inputs",
                  "error", "engine", f"Inputs {dict(zip(line['inputs'], vals))}.", nodes=[c.L(key)])
    if not bad:
        c.ok("R1-line-arithmetic", "All R-SUM / R-CARRY lines equal their inputs", 0, 0, [])


@check("R2-federal-tax")
def federal_tax(c: Ctx):
    """Regular tax via the Schedule D tax worksheet, from the engine's own brackets."""
    P, v = c.p.params, c.p.line_value
    br = P["brackets_mfj"]
    ti, qd = float(v("F1040.15")), float(v("F1040.3a"))
    d15, d16, d18, d19 = (float(v(k)) for k in ("SchD.15", "SchD.16", "SchD.18", "SchD.19"))
    ncg = max(0.0, min(d15, d16))
    l10 = qd + ncg
    l11 = d18 + d19
    l12 = min(ncg, l11)
    l13 = l10 - l12
    l14 = max(0.0, ti - l13)
    l16 = min(ti, P["ltcg_0_top"])
    l17 = min(l14, l16)
    l18 = max(0.0, ti - l10)
    top24 = next(u for u, r in br if r == 0.24)
    l20 = min(l14, min(ti, top24))
    l21 = max(l18, l20)
    l22 = l16 - l17
    l23 = min(ti, l13)
    l25 = l23 - l22
    l29 = max(0.0, min(ti, P["ltcg_15_top"]) - (l21 + l22))
    l30 = min(l25, l29)
    l33 = l23 - (l22 + l30)
    tax = l30 * 0.15 + l33 * 0.20
    l39 = max(0.0, min(ncg, d19) - max(0.0, (l10 + l21) - ti))
    tax += l39 * 0.25
    l42 = ti - (l21 + l22 + l30 + l33 + l39)
    tax += max(0.0, l42) * 0.28
    tax += _bracket_tax(l21, br)
    tax = min(tax, _bracket_tax(ti, br))
    _compare(c, "R2-federal-tax", "F1040.16", tax, "Schedule D tax worksheet on taxable income "
             f"{fmt(ti)} (qualified dividends {fmt(qd)}, net capital gain {fmt(ncg)}, unrecaptured 1250 {fmt(d19)})")


@check("R3-self-employment-and-surtaxes")
def se_and_surtaxes(c: Ctx):
    P, v = c.p.params, c.p.line_value
    profit = float(v("SchC.31"))
    ne = round(profit * P["se_factor"])
    _compare(c, "R3-self-employment-and-surtaxes", "SchSE.4a", ne, "Net SE earnings = Schedule C x 92.35%")
    ss = min(ne, P["ss_wage_base"]) * 0.124   # Erik has no W-2 wages; wage base applies per person
    _compare(c, "R3-self-employment-and-surtaxes", "SchSE.10", ss, "SE social security portion (spouse with no wages)")
    _compare(c, "R3-self-employment-and-surtaxes", "SchSE.11", ne * 0.029, "SE Medicare portion")
    magi = float(v("F1040.11"))
    nii = float(v("F8960.12"))
    _compare(c, "R3-self-employment-and-surtaxes", "F8960.17", 0.038 * max(0.0, min(nii, magi - P["niit_threshold"])),
             "Net investment income tax 3.8% x lesser of NII or MAGI over threshold")
    wages = float(v("F8959.1"))
    addl = 0.009 * max(0.0, wages - P["addl_medicare_threshold"]) + \
        0.009 * max(0.0, ne - max(0.0, P["addl_medicare_threshold"] - wages))
    _compare(c, "R3-self-employment-and-surtaxes", "F8959.18", addl, "Additional Medicare tax on wages and SE income")
    w2_ss = [c.p.ev[s] for s in c.p.line("Sch3.11")["sources"] if c.p.ev[s]["field"] == "box4"]
    excess = sum(float(e["value"]) for e in w2_ss) - P["ss_wage_base"] * 0.062
    _compare(c, "R3-self-employment-and-surtaxes", "Sch3.11", excess, "Excess social security withheld by two employers")


@check("R4-limits-and-phaseouts")
def limits(c: Ctx):
    P, v = c.p.params, c.p.line_value
    agi = float(v("F1040.11"))
    cap = P["salt_cap"] if agi <= P["salt_cap_phase_start"] else max(
        P["salt_cap_floor"], P["salt_cap"] - P["salt_cap_phase_rate"] * (agi - P["salt_cap_phase_start"]))
    _compare(c, "R4-limits-and-phaseouts", "SchA.5e", min(float(v("SchA.5d")), cap), f"SALT cap {fmt(cap)} at AGI {fmt(agi)}")
    red = math.ceil(max(0.0, agi - P["ctc_phaseout_start"]) / 1000) * 50
    _compare(c, "R4-limits-and-phaseouts", "F8812.11", min(red, float(v("F8812.8"))), "Child tax credit phase-out $50 per $1,000")
    sep_limit = 0.2 * (float(v("SchC.31")) - float(v("SchSE.13")))
    contrib = float(c.p.ev[c.p.line("Sch1.16")["sources"][0]]["value"])
    _compare(c, "R4-limits-and-phaseouts", "Sch1.16", min(contrib, sep_limit), "SEP limit 20% of (net profit - half SE tax)")
    _compare(c, "R4-limits-and-phaseouts", "F1040.12", max(float(v("SchA.17")), P["std_deduction_mfj"]),
             "Larger of itemized or standard deduction")


@check("R5-california-tax")
def california_tax(c: Ctx):
    P, v = c.p.params, c.p.line_value
    ti = float(v("F540NR.19"))
    _compare(c, "R5-california-tax", "F540NR.31", _bracket_tax(ti, P["ca_brackets_mfj"]),
             f"California rate schedule on total taxable income {fmt(ti)}")
    ratio = float(v("F540NR.32")) / float(v("F540NR.17"))
    if abs(ratio - float(v("F540NR.34"))) > 0.0002:
        c.add("R5-california-tax", "540NR deduction percentage does not equal line 32 / line 17", "error", "engine",
              f"{ratio:.4f} vs {v('F540NR.34')}", nodes=[c.L("F540NR.34")])
    else:
        c.ok("R5-california-tax", "540NR line 34 = CA AGI / total AGI", v("F540NR.34"), round(ratio, 4), [c.L("F540NR.34")])


@check("R6-fx-rate-period")
def fx_rate_period(c: Ctx):
    """Income must be translated at a rate for the tax year, not a prior year."""
    year = str(c.p.tax_year)
    for key, line in c.p.lines[c.ver].items():
        fx = [s for s in line["sources"] if s.startswith("ref:fx.")]
        for ref in fx:
            cur, rname = ref[len("ref:fx."):].split(".", 1)
            m = re.match(r"(\d{4})_", rname)
            if not m or m[1] == year:
                continue
            right = f"{year}_average"
            rate_used, rate_right = c.p.params["fx"][cur][rname], c.p.params["fx"][cur][right]
            foreign = next(float(c.p.ev[s]["value"]) for s in line["sources"] if s.startswith("ev-"))
            new = round(foreign / rate_right)
            cat = "interest" if key.startswith("SchB") else "ordinary_income"
            c.add("R6-fx-rate-period", f"{key} converts {cur} {fmt(foreign)} at the {rname.replace('_', ' ')} rate",
                  "error", "engine",
                  f"Converted at {rate_used} ({rname}); the {year} average is {rate_right}. "
                  f"{fmt(line['value'])} should be {fmt(new)}.",
                  nodes=[c.L(key), f"fx:{cur}.{rname}"], evidence=[f"fx:{cur}.{right}"],
                  corrections=[Correction(key, line["value"], new, cat)], deltas=[(cat, new - line["value"], c.p.california_category(key))])
