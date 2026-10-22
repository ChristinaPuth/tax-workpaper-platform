"""Cross-record reconciliations: return vs agency records, prior year, household, and the document set."""
from __future__ import annotations

from datetime import date

from ..findings import Correction
from .base import Ctx, check, fmt


@check("P1-federal-payments-vs-transcript")
def federal_payments(c: Ctx):
    tx = c.p.agency["irs_account_transcript_2025"][-1]["transactions"]
    est = [t for t in tx if t["code"] == "670" and "extension" not in t["description"].lower()]
    ext = [t for t in tx if t["code"] == "670" and "extension" in t["description"].lower()]
    on_record = sum(t["amount"] for t in est)
    line = c.p.line("F1040.26")
    if abs(on_record - line["value"]) < 1:
        c.ok("P1-federal-payments-vs-transcript", "2025 estimated payments agree to IRS transcript", line["value"], on_record, [c.L("F1040.26")])
    else:
        conf = {c.p.ev[s]["value"] for s in line["sources"] if s.startswith("ev-") and "amount" in c.p.ev[s]["field"]}
        missing = [t for t in est if t["amount"] not in conf or t["date"] > "2025-12-31"]
        qa = [s for s in line["sources"] if s.startswith("qa-")]
        c.add("P1-federal-payments-vs-transcript",
              f"Federal estimated payments {fmt(line['value'])} vs IRS transcript {fmt(on_record)}",
              "error", "client",
              f"The engine took the fourth payment from the client's questionnaire answer ("
              + "; ".join(f"{q}: \"{c.p.qa[q]['answer']}\"" for q in qa)
              + f") because no confirmation was uploaded. The IRS transcript shows "
              + ", ".join(f"{t['date']} {fmt(t['amount'])}" for t in est) + ".",
              nodes=[c.L("F1040.26"), *[f"qa:{q}" for q in qa]],
              evidence=["agency:/irs_account_transcript_2025"],
              corrections=[Correction("F1040.26", line["value"], on_record, "payment")],
              deltas=[("payment", on_record - line["value"])],
              effect_note="Payments change the balance due 1:1; the 2210 penalty also moves slightly.")
    ext_line = c.p.line("Sch3.10")
    if ext_line and ext and abs(sum(t["amount"] for t in ext) - ext_line["value"]) < 1:
        c.ok("P1-federal-payments-vs-transcript", "Extension payment agrees to IRS transcript", ext_line["value"],
             sum(t["amount"] for t in ext), [c.L("Sch3.10")])


@check("P2-california-payments-vs-ftb")
def california_payments(c: Ctx):
    ftb = c.p.agency["ftb_account"]
    on_record = sum(t["amount"] for t in ftb["tax_year_2025_payments"])
    line = c.p.line("F540NR.72")
    if abs(on_record - line["value"]) < 1:
        c.ok("P2-california-payments-vs-ftb", "CA estimated payments agree to FTB", line["value"], on_record, [c.L("F540NR.72")])
        return
    # find the payment(s) the engine counted that were designated to a different tax year
    wrong = []
    for s in line["sources"]:
        e = c.p.ev.get(s)
        if e and e["field"].endswith("_year") and str(e["value"]) != str(c.p.tax_year):
            grp = e["field"].rsplit("_", 1)[0]
            amt = next(x for x in c.p.ev_by_doc[e["document_id"]] if x["field"] == f"{grp}_amount")
            dt = next(x for x in c.p.ev_by_doc[e["document_id"]] if x["field"] == f"{grp}_date")
            wrong.append((e, amt, dt))
    held = "; ".join(f"{t['date']} {fmt(t['amount'])}: {t.get('note', '')}" for t in ftb.get("tax_year_2024_payments_after_filing", []))
    c.add("P2-california-payments-vs-ftb",
          f"California estimated payments {fmt(line['value'])} vs FTB account {fmt(on_record)}",
          "error", "engine",
          "Rule R-CA-ESTIMATED-PAYMENTS counts every FTB payment in the date window regardless of the tax year it "
          "was designated to. " + " ".join(
              f"{dt['value']} {fmt(amt['value'])} was designated tax year {e['value']} ({e['id']}, printed on "
              f"{e['document_id']})." for e, amt, dt in wrong) + f" FTB: {held}",
          nodes=[c.L("F540NR.72"), *[f"ev:{e['id']}" for e, _, _ in wrong]],
          evidence=["agency:/ftb_account", *[f"page:{e['document_id']}#{e['page']}" for e, _, _ in wrong]],
          corrections=[Correction("F540NR.72", line["value"], on_record, "ca_payment")],
          deltas=[("ca_payment", on_record - line["value"])],
          effect_note="Balance changes 1:1. Option: ask FTB to move the 2024 credit to 2025 (judgment, record it).")


@check("P3-identity-vs-documents")
def identity(c: Ctx):
    """Each household SSN must match every independent document that prints it."""
    for person in c.p.household["people"]:
        name, ssn = person["name"], person["ssn"]
        hits = []
        for (did, pg), text in c.p.page_text.items():
            if name in text or name.split()[0] in text:
                for e in c.p.ev_by_doc.get(did, []):
                    if e["value_type"] == "ssn" and e["page"] == pg:
                        idx = text.find(name.split()[0])
                        # attribute the SSN to this person only when it is printed right after the name
                        if idx >= 0 and str(e["value"]) in text[idx: idx + len(name) + 30]:
                            hits.append(e)
        bad = [e for e in hits if e["value"] != ssn]
        if bad:
            docs = sorted({e["document_id"] for e in bad})
            c.add("P3-identity-vs-documents", f"{name}: SSN on the return {ssn} disagrees with {', '.join(docs)}",
                  "error", "client",
                  f"Household record (entered by the client) has {ssn}; "
                  + "; ".join(f"{e['document_id']} prints {e['value']}" for e in bad)
                  + ". The return would be rejected (dependent TIN/name mismatch).",
                  nodes=[f"person:{person['id']}", *[f"ev:{e['id']}" for e in bad]],
                  evidence=[f"page:{e['document_id']}#{e['page']}" for e in bad],
                  corrections=[Correction(f"household.{person['id']}.ssn", ssn, bad[0]["value"], "none")],
                  effect=(0, 0), effect_note="No tax effect; blocks e-file.")
        elif hits:
            c.ok("P3-identity-vs-documents", f"{name} SSN agrees to {len(hits)} document(s)", 0, 0, [f"person:{person['id']}"])


@check("P4-carryovers-agree-to-prior-year")
def carryovers(c: Ctx):
    py = c.p.prior["return_2024"]["lines"]
    co = c.p.prior["carryovers_into_2025"]
    st, lt, allowed = -py["SchD.7"], -py["SchD.15"], -py["SchD.21"]
    st_left = max(0, st - allowed)
    lt_left = lt - max(0, allowed - st)
    for k, expected in (("capital_loss_short", st_left), ("capital_loss_long", lt_left),
                        ("passive_1450_fremont", -py["F8582.unallowed.A"]),
                        ("passive_1200_barton_hills", -py["F8582.unallowed.B"])):
        node = f"py:/carryovers_into_2025/{k}"
        if abs(co[k] - expected) < 1:
            c.ok("P4-carryovers-agree-to-prior-year", f"{k} carryover agrees to 2024 return", co[k], expected, [node])
        else:
            c.add("P4-carryovers-agree-to-prior-year", f"{k} carryover {co[k]} vs 2024 return {expected}", "error",
                  "document", "Carryover does not agree to the filed 2024 return.", nodes=[node])
    if co["capital_loss_short"] != abs(c.p.line_value("SchD.6")) or co["capital_loss_long"] != abs(c.p.line_value("SchD.14")):
        c.add("P4-carryovers-agree-to-prior-year", "Schedule D carryover lines differ from the carryover record", "error",
              "engine", "", nodes=[c.L("SchD.6"), c.L("SchD.14")])


@check("P5-prior-year-variance")
def variance(c: Ctx):
    std = c.p.firm["starter_standards"]["variance_review"]
    pct, amt = std["flag_if_change_over_percent"] / 100, std["and_over_amount"]
    py = c.p.prior["return_2024"]["lines"]
    keymap = {"CA540.13": "F540NR.13", "CA540.17": "F540NR.17", "CA540.19": "F540NR.19", "CA540.31": "F540NR.31",
              "CA540.64": "F540NR.64", "CA540.71": "F540NR.71", "CA540.72": "F540NR.72"}
    # Schedule B lines are numbered by payer order, which changes every year: match by payer name instead.
    import re as _re
    labels = c.p.prior["return_2024"]["line_labels"]
    payer = lambda s: " ".join(_re.split(r"[-(]", s.split(" - ", 1)[-1])[0].split()[:2]).lower()
    cur_payer = {}
    for key, l in c.p.lines[c.ver].items():
        if _re.match(r"SchB\.[15]\.\d+$", key):
            cur_payer[(key.split(".")[1], payer(l["label"]))] = key
    for k in list(py):
        m = _re.match(r"SchB\.([15])\.\d+$", k)
        if m:
            keymap[k] = cur_payer.pop((m[1], payer(labels[k])), None) or "?"
    for (part, name), key in cur_payer.items():  # payers with no 2024 counterpart
        new = c.p.line_value(key)
        if abs(new) > amt:
            c.add("P5-prior-year-variance", f"{key}: new payer in 2025 ({c.p.line(key)['label']}) {fmt(new)}",
                  "warning", "process", "No 2024 counterpart. Confirm it is new income, not a second report of an existing account.",
                  nodes=[c.L(key)])
    rows = []
    for k, old in py.items():
        if not isinstance(old, (int, float)):
            continue
        key = keymap.get(k, k)
        new = c.p.line_value(key, default=None)
        if new is None or isinstance(new, str):
            continue
        diff = float(new) - float(old)
        if abs(diff) > amt and (old == 0 or abs(diff) / abs(old) > pct):
            rows.append((key, old, new, diff))
    for key, old, new, diff in rows:
        c.add("P5-prior-year-variance", f"{key}: {fmt(old)} (2024) -> {fmt(new)} (2025), {'+' if diff > 0 else ''}{fmt(diff)}",
              "warning", "process", f"Over the firm threshold ({int(pct * 100)}% and {fmt(amt)}). Needs an explanation.",
              nodes=[c.L(key)], evidence=[f"py:/return_2024/lines/{key}"])


@check("P6-document-completeness")
def completeness(c: Ctx):
    v = c.p.latest
    computed = v["computed_at"]
    support = {  # documents that prove a required step rather than feed a line
        "engagement_letter": "Engagement letter and consents signed", "consent_7216": "Engagement letter and consents signed",
        "identity_document": "Identity verified", "irs_ip_pin_notice": "Identity verified",
        "prior_year_return": "Prior-year return reviewed",
    }
    for d in c.p.documents:
        land = c.ix.document_landing(d["id"])
        if land["status"] in ("used", "superseded", "explained_in_note"):
            continue
        if d["document_type"] in support and d["received_at"] <= computed:
            c.ok("P6-document-completeness", f"{d['id']} supports required step: {support[d['document_type']]}", 0, 0,
                 [f"doc:{d['id']}"])
            continue
        late = d["received_at"] > computed
        if land["status"] == "not_extracted":
            c.add("P6-document-completeness", f"{d['id']} not extracted: {d['title']}", "info", "process",
                  land["reason"], nodes=[f"doc:{d['id']}"])
        else:
            c.add("P6-document-completeness",
                  f"{d['id']} not reflected in {v['version']}: {d['title']}" + (" (received after the last computation)" if late else ""),
                  "warning", "process",
                  f"Received {d['received_at'][:10]}; {v['version']} computed {computed[:10]}. {land['reason']} "
                  "Every document must be used or carry a reason.",
                  nodes=[f"doc:{d['id']}"])


@check("P7-engine-diagnostics")
def engine_diagnostics(c: Ctx):
    """The engine's own warnings are findings too - they need a disposition before filing."""
    for g in c.p.latest["diagnostics"]:
        nodes = [f"diag:{c.ver}:{g['code']}", *[c.ix.resolve(r, c.ver) for r in g["refs"]]]
        c.add("P7-engine-diagnostics", f"Engine: {g['code']}", "warning" if g["severity"] == "warning" else "info",
              "engine", g["message"], nodes=[n for n in nodes if n in c.ix.nodes or n.startswith(("py:/", "agency:/"))])
