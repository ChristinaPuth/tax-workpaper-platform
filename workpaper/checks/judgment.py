"""Checks that connect facts stated in one place (client answers, call notes, supplemental statements, closing
documents) to the line they should have changed. They are written against this packet's records, but each one is
the instance of a reusable rule stated in its docstring - the rule is what a production system would keep.
"""
from __future__ import annotations

from ..findings import Correction
from .base import Ctx, check, fmt, held_long_term


def _ev(c: Ctx, doc: str, field: str) -> dict:
    return next(e for e in c.p.ev_by_doc[doc] if e["field"] == field)


@check("J1-supplemental-basis-not-applied")
def supplemental_basis(c: Ctx):
    """Rule: a lot with no broker basis must use a matching supplemental statement (same acquisition date & quantity)."""
    supp = {}
    for e in c.p.extracted_values:
        if e["field"].endswith("_adjusted_basis"):
            lot = e["field"][: -len("_adjusted_basis")]
            acq = next((x for x in c.p.ev_by_doc[e["document_id"]] if x["field"] == f"{lot}_acquired"), None)
            if acq:
                supp[acq["value"]] = (lot, e)
    for key, line in c.p.lines[c.ver].items():
        if line["rule"] != "R-8949-LOT":
            continue
        evs = [c.p.ev[s] for s in line["sources"] if s.startswith("ev-")]
        basis = next((e for e in evs if e["field"].endswith("_basis")), None)
        acq = next((e for e in evs if e["field"].endswith(("_acquired", "_acq"))), None)
        sold = next((e["value"] for e in evs if e["field"].endswith("_sold")), None)
        if not basis or not acq or basis["text_as_read"] != "" or any(s.startswith("ev-") and c.p.ev[s]["field"].endswith("_adjusted_basis") for s in line["sources"]):
            continue
        hit = supp.get(acq["value"])
        if not hit:
            continue
        lot, se = hit
        proceeds = next(float(e["value"]) for e in evs if e["field"].endswith("_proceeds"))
        new = round(proceeds - float(se["value"]), 2)
        term = "ltcg" if key.split(".")[1] in "DEFK" else "stcg"
        c.add("J1-supplemental-basis-not-applied",
              f"{key}: RSU lot taxed on full proceeds - supplemental basis {fmt(se['value'])} not applied",
              "error", "engine",
              f"Broker basis is blank (noncovered RSU shares). {se['document_id']} lot {lot} (acquired {acq['value']}) "
              f"gives adjusted basis {fmt(se['value'])} - the vest value already taxed as W-2 wages. Gain should be "
              f"{fmt(new)}, not {fmt(line['value'])}. The engine matched the ESPP lot but not the RSU lots.",
              nodes=[c.L(key), f"ev:{basis['id']}", f"ev:{se['id']}"],
              evidence=[f"page:{se['document_id']}#{se['page']}", f"page:{basis['document_id']}#{basis['page']}"],
              corrections=[Correction(key, line["value"], new, term)],
              deltas=[(term, new - line["value"], c.ca_category_for_sale(sold) if sold else None)])


@check("J2-card-receipts-already-in-books")
def card_receipts_in_books(c: Ctx):
    """Rule: Form 1099-K is added to gross receipts only if the books did not already record the deposits."""
    line = c.p.line("SchC.1")
    k = _ev(c, "D21", "box1a")
    via = _ev(c, "D15", "atlas_paywell")
    books = _ev(c, "D14", "total_income")
    if float(via["value"]) == float(k["value"]) and line["value"] > float(books["value"]):
        c.add("J2-card-receipts-already-in-books",
              f"SchC.1 counts the 1099-K {fmt(k['value'])} twice", "error", "engine",
              f"Books revenue {fmt(books['value'])} already includes the Paywell card deposits: the transaction detail says "
              f"Atlas paid {fmt(_ev(c, 'D15', 'atlas_total')['value'])}, of which {fmt(via['value'])} arrived through Paywell "
              f"and was deposited gross. The engine could not match it (R-SCHC-GROSS) and added it again: "
              f"{fmt(line['value'])} = {fmt(books['value'])} + {fmt(k['value'])}. Gross receipts reconcile to 1099-NEC 142,000 "
              f"+ non-1099 clients {fmt(_ev(c, 'D15', 'unreported_small')['value'])} = {fmt(books['value'])}.",
              nodes=[c.L("SchC.1"), f"ev:{k['id']}", f"ev:{via['id']}"],
              evidence=[f"page:D15#{via['page']}", f"page:D21#1", f"page:D14#1"],
              corrections=[Correction("SchC.1", line["value"], float(books["value"]), "schc_profit")],
              deltas=[("schc_profit", float(books["value"]) - line["value"])], generic=False,
              effect_note="Also the item the IRS examines in 2028 (Letter 566): this reconciliation is the answer.")


@check("J3-sehi-eligible-for-employer-plan")
def sehi(c: Ctx):
    """Rule: no self-employed health insurance deduction for months the person was eligible for an employer plan
    (own or spouse's)."""
    line = c.p.line("Sch1.17")
    qa = c.p.qa["qa-25"]
    if line["value"] and qa["answer"].lower().startswith("yes"):
        c.add("J3-sehi-eligible-for-employer-plan", f"Sch1.17 deducts {fmt(line['value'])} although Erik could join Ngozi's employer plan",
              "error", "engine",
              f"qa-25: \"{qa['answer']}\" Both W-2s show employer health coverage (box 12 DD). The prior preparer "
              f"took no deduction in 2024 for the same reason (2024 note: {c.p.prior['return_2024']['notes']['Sch1.17']})",
              nodes=[c.L("Sch1.17"), "qa:qa-25"], evidence=["qa:qa-25", "ev:ev-0025", "ev:ev-0044", "py:/return_2024/notes"],
              corrections=[Correction("Sch1.17", line["value"], 0, "adjustment")],
              deltas=[("adjustment", -line["value"])], generic=False,
              effect_note="Adjustment rate; the QBI deduction also moves (not captured by the rate).")


@check("J4-repair-is-an-improvement")
def hvac(c: Ctx):
    """Rule: replacing a whole building system is an improvement (capitalize, 27.5 years), not a repair."""
    alt = next(a for a in c.p.raw["what_if"]["alternatives"] if a["id"] == "hvac_improvement")
    line = c.p.line("SchE.14A")
    c.add("J4-repair-is-an-improvement", "HVAC replacement 11,000 expensed as a repair at 1450 Fremont Way",
          "error", "engine",
          "Invoice D47: removed the failed furnace and condenser, installed a new heat pump system with air handler, "
          "line set and thermostat (permit B25-31877). Call notes confirm the whole system was replaced. That is a "
          "restoration of a building system - capitalize. The engine kept it inside repairs because the owner statement "
          "lists it there. The what-if 'hvac_improvement' is the engine's own result for the correct treatment.",
          nodes=[c.L("SchE.14A"), "ev:ev-1001", "doc:D47"], evidence=["page:D47#1", "call:call-01", "qa:qa-37"],
          corrections=[Correction(x["key"], x.get("old"), x.get("new"), None) for x in alt["changed_lines"]][:6],
          effect=(alt["federal"]["total_tax_change"], alt["california"]["total_tax_change"]), generic=False,
          effect_note="Engine-computed what-if (what_if.alternatives.hvac_improvement).")


@check("J5-vehicle-donation-limited-to-proceeds")
def vehicle(c: Ctx):
    """Rule: a donated vehicle the charity sells is deductible at the gross proceeds on Form 1098-C."""
    line = c.p.line("F8283.A1.vehicle")
    proceeds = _ev(c, "D66", "box4c")
    if line["value"] > float(proceeds["value"]):
        c.add("J5-vehicle-donation-limited-to-proceeds",
              f"Car donation claimed at {fmt(line['value'])} (client's Blue Book estimate); 1098-C proceeds {fmt(proceeds['value'])}",
              "error", "engine",
              "Form 1098-C box 4a is checked: the charity sold the car at arm's length on 09/09/2025 for "
              f"{fmt(proceeds['value'])}. The engine used the value from qa-39 (R-NONCASH-GIFT: value stated by the donor).",
              nodes=[c.L("F8283.A1.vehicle"), f"ev:{proceeds['id']}", "qa:qa-39"],
              evidence=["page:D66#1", "call:call-01"],
              corrections=[Correction("F8283.A1.vehicle", line["value"], float(proceeds["value"]), "itemized")],
              deltas=[("itemized", float(proceeds["value"]) - line["value"])], generic=False,
              effect_note="Also an item under IRS examination in 2028.")


@check("J6-purchase-year-property-tax")
def property_tax(c: Ctx):
    """Rule: in the purchase year the buyer deducts only the tax for their period of ownership; the seller's share
    credited at closing is not the buyer's deduction."""
    line = c.p.line("SchA.5b")
    credit = _ev(c, "D54", "tax_credit")
    new = line["value"] - float(credit["value"])
    salt_total = c.p.line_value("SchA.5a") + new
    cap = c.p.line_value("SchA.5e")
    fed_change = min(salt_total, cap) - c.p.line_value("SchA.5e")
    rf_item = c.p.tax_effect_rate("itemized")[0]
    rc_salt = c.p.tax_effect_rate("salt")[1]
    c.add("J6-purchase-year-property-tax",
          f"Home property tax {fmt(line['value'])} includes the seller's {fmt(credit['value'])} (bought 07/08/2025)",
          "error", "engine",
          f"Travis County billed {fmt(line['value'])} for all of 2025 (D58: owner of record on 01/01/2025 was the prior "
          f"owner). At closing the seller credited the buyers {fmt(credit['value'])} for 01/01-07/07 (D54). The buyers' "
          f"deduction is {fmt(new)}. SALT drops below the 40,000 cap, so the federal deduction falls by {fmt(-fed_change)}.",
          nodes=[c.L("SchA.5b"), c.L("SchA.5e"), f"ev:{credit['id']}"], evidence=["page:D54#1", "page:D58#1", "page:D57#1"],
          corrections=[Correction("SchA.5b", line["value"], new, "salt"),
                       Correction("SchA.5e", cap, min(salt_total, cap), "itemized")],
          effect=(round(fed_change * rf_item), round(-float(credit["value"]) * rc_salt)), generic=False)


@check("J7-interest-counted-twice")
def payoff_interest(c: Ctx):
    """Rule: a lender statement is not a second source of interest the lender already reported on Form 1098."""
    line = c.p.line("SchA.8a")
    payoff = _ev(c, "D56", "interest")
    text = c.p.page_text[("D56", 1)]
    if payoff["id"] in line["sources"] and "reported on the 2025 Form 1098" in text:
        c.add("J7-interest-counted-twice", f"Mortgage interest includes payoff interest {fmt(payoff['value'])} twice",
              "error", "engine",
              f"Lonestar's 1098 box 1 (13,900) 'includes ... interest paid at payoff 11/20/2025'; the payoff statement "
              f"says the same interest 'is reported on the 2025 Form 1098'. R-MORTGAGE-INTEREST adds every 1098 and lender "
              f"statement, so {fmt(payoff['value'])} is in SchA.8a twice.",
              nodes=[c.L("SchA.8a"), f"ev:{payoff['id']}", "ev:ev-1029"], evidence=["page:D55#1", "page:D56#1"],
              corrections=[Correction("SchA.8a", line["value"], line["value"] - float(payoff["value"]), "itemized")],
              deltas=[("itemized", -float(payoff["value"]))], generic=False)


@check("J8-business-use-not-applied")
def business_use(c: Ctx):
    """Rule: mixed-use costs are deducted at the business-use share the client states; personal items come out."""
    call = c.p.call["call-01"]
    phone_v, internet_v = float(_ev(c, "D14", "Telephone")["value"]), float(_ev(c, "D14", "Internet")["value"])
    spot = float(_ev(c, "D15", "spotify")["value"])
    util_new = round(phone_v * 0.70 + internet_v * 0.50)
    util = c.p.line("SchC.25")
    soft = c.p.line("SchC.27a.1")
    delta = (util["value"] - util_new) + spot
    c.add("J8-business-use-not-applied",
          f"Phone, internet and Spotify deducted at 100% (client says 70% / 50% / personal)", "warning", "client",
          "Call 03/26: " + " | ".join(call["notes"][:3]) + f". Books deduct telephone {fmt(phone_v)} (family plan, 4 lines) and "
          f"home internet {fmt(internet_v)} in full and include Spotify Family {fmt(spot)} in software.",
          nodes=[c.L("SchC.25"), c.L("SchC.27a.1"), "call:call-01"], evidence=["call:call-01", "page:D15#1", "page:D15#2"],
          corrections=[Correction("SchC.25", util["value"], util_new, "schc_profit"),
                       Correction("SchC.27a.1", soft["value"], soft["value"] - spot, "schc_profit")],
          deltas=[("schc_profit", delta)], generic=False,
          effect_note="Judgment: percentages are the client's estimate - record the basis.")


@check("J9-state-source-wages-after-move")
def ca_wages(c: Ctx):
    """Rule: for a part-year resident, state-source wages stop at the move date - box 16 is what the employer
    reported, not the sourcing answer."""
    line = c.p.line("SchCA540NR.1.E")
    corvane = float(_ev(c, "D08", "box16")["value"])
    stub = _ev(c, "D73", "ytd_ca_wages")
    new = corvane + float(stub["value"])
    move = c.p.household["residency"][0]["to"]
    c.add("J9-state-source-wages-after-move",
          f"California-source wages {fmt(line['value'])} include Halvorsen wages earned in Texas", "error", "engine",
          f"R-CA-WAGES-SOURCE uses W-2 box 16. Halvorsen kept California as the work state through 09/30 by mistake "
          f"(D09 note; qa-45). Residency ended {move}. The 07/18 paystub (D73) shows California wages from 06/02 to the "
          f"move of {fmt(stub['value'])}. California-source wages = Corvane {fmt(corvane)} + {fmt(stub['value'])} = {fmt(new)}.",
          nodes=[c.L("SchCA540NR.1.E"), f"ev:{stub['id']}", "ev:ev-0047"],
          evidence=["page:D73#1", "page:D09#1", "qa:qa-45", "qa:qa-02"],
          corrections=[Correction("SchCA540NR.1.E", line["value"], new, "ca_source_income")],
          deltas=[("ca_source_income", new - line["value"])], generic=False,
          effect_note="California withholding after the move is still a credit (refund), unchanged.")


@check("J10-client-supplied-basis")
def crypto_basis(c: Ctx):
    """Rule: a client-supplied basis replaces zero basis only with evidence; holding period follows the original
    purchase date."""
    line = c.p.line("F8949.H.C6")
    msg = c.p.msg["msg-07"]
    basis, acquired, sold = 3050.0, "2021-03-15", "2025-06-18"
    proceeds = line["value"]
    new_gain = proceeds - basis
    lt = held_long_term(acquired, sold)
    c.add("J10-client-supplied-basis", f"Crypto lot C6 at zero basis; client reports {fmt(basis)} paid 03/15/2021",
          "warning", "client",
          f"msg-07: \"{msg['text']}\" With that basis the lot is {'long' if lt else 'short'}-term (held since 2021), "
          f"gain {fmt(new_gain)} instead of a {fmt(proceeds)} short-term gain. Evidence is one bank statement line - "
          "decide and record whether it is sufficient.",
          nodes=[c.L("F8949.H.C6"), "msg:msg-07", "ev:ev-0918", "ev:ev-0919"], evidence=["msg:msg-07", "page:D35#1"],
          corrections=[Correction("F8949.H.C6", proceeds, 0, "stcg"),
                       Correction("F8949.K.C6", None, new_gain, "ltcg" if lt else "stcg")],
          deltas=[("stcg", -proceeds, c.ca_category_for_sale(sold)),
                  ("ltcg" if lt else "stcg", new_gain, c.ca_category_for_sale(sold))], generic=False)


@check("J11-client-answer-contradicts-records")
def ira_basis(c: Ctx):
    """Rule: when a client answer contradicts a filed return or third-party form, the record wins and the conflict
    is documented."""
    qa = c.p.qa["qa-31"]
    c.add("J11-client-answer-contradicts-records", "Client says no prior IRA basis; 2024 Form 8606 and 2024 Form 5498 show 7,000",
          "info", "client",
          f"qa-31: \"{qa['answer']}\" The 2024 return (line F8606.14 = 7,000) and the 2024 Form 5498 (contribution made "
          "02/12/2025 for 2024) support the engine's 7,000 prior basis; conversion taxable amount 26 is right. Confirm "
          "with the client and record it.",
          nodes=[c.L("F8606.2"), "qa:qa-31"], evidence=["ev:ev-0991", "py:/basis_records/ira_nondeductible_basis_ngozi/0"],
          effect=(0, 0), generic=False)
    q14 = c.p.qa["qa-14"]
    c.add("J11-client-answer-contradicts-records", "Client says no investments sold; three brokers report 283 sales",
          "info", "client", f"qa-14: \"{q14['answer']}\" Also qa-15: \"{c.p.qa['qa-15']['answer']}\" (12 crypto sales). "
          "The documents govern; the answers show what the client does not track (e.g. direct indexing).",
          nodes=["qa:qa-14", "qa:qa-15", "doc:D74"], evidence=["doc:D28", "doc:D31", "doc:D74", "doc:D34"], effect=(0, 0), generic=False)


@check("J12-outside-filings")
def outside_filings(c: Ctx):
    """Rule: every filing obligation the facts reveal is identified, in or out of scope."""
    items = [
        ("Form 3520 for 2023 - foreign inheritance from Birgitta Lindqvist (account opened 09/2023)",
         "Prior preparer left it open (D07). D36 shows the inheritance; qa-08 only asked about 2025. Possible late-filing "
         "exposure - raise with the client.", ["page:D36#1", "py:/prior_preparer_workpaper/open_items_left_by_prior_preparer"], "warning"),
        ("FinCEN 114 (FBAR) for 2025 - Sparbanken max SEK 1,452,300", "Outside the engagement (D01). Client filed it "
         "themselves in 2024. Due 10/15/2026.", ["page:D01#1", "ev:ev-0962"], "info"),
        ("Forms 1099-NEC for contractors Quintero 4,800 and Patel 2,600", "Required, not filed (qa-23, D27). Late since "
         "02/02/2026; outside the engagement. Advise the client in writing.", ["qa:qa-23", "page:D27#1"], "warning"),
        ("Ada's own 2025 Form 1040", "She checked 'someone can claim you' - consistent with claiming her as a dependent.",
         ["person:ada"], "info"),
        ("Oregon composite (Woodworks) and Arizona composite (Ridgeline)", "Filed by the entities; Oregon tax 1,580 used "
         "for the Schedule S credit; no Arizona filing needed by the partner (D38).", ["page:D39#2", "page:D38#1"], "info"),
    ]
    for title, detail, ev, sev in items:
        c.add("J12-outside-filings", title, sev, "process", detail, nodes=ev, evidence=ev, generic=False)


@check("J13-resolved-by-client-evidence")
def resolved(c: Ctx):
    """Link client evidence that resolves an extraction doubt to that doubt (verification = confirmed_with_client)."""
    for f in c.findings:
        if "ev:ev-1049" in f.nodes:
            f.evidence.append("msg:msg-08")
            f.detail += " RESOLVED: msg-08 - parish confirmed 1,500 by phone; matches bank statement check #2207."
            f.severity = "info"
