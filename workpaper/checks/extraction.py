"""Checks that compare what the pipeline read against what is printed. They never trust confidence scores."""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from difflib import SequenceMatcher

from ..findings import Correction
from .base import Ctx, check, date_forms, fmt, numbers_in

ID_PATTERNS = {
    "ein": re.compile(r"\b\d{2}-\d{7}\b"),
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
}


@check("X1-identifier-not-printed")
def identifier_not_printed(c: Ctx):
    """An EIN/SSN that is not on the page, while a same-shaped identifier with the same digits is: a transposition."""
    for e in c.p.extracted_values:
        pat = ID_PATTERNS.get(e["value_type"])
        if not pat or not e["value"]:
            continue
        text = c.p.page_text[(e["document_id"], e["page"])]
        if e["value"] in text:
            continue
        candidates = [t for t in pat.findall(text) if sorted(t) == sorted(e["value"])]
        lines = c.ev_lines(e["id"])
        printed = candidates[0] if candidates else "(no matching identifier on the page)"
        c.add("X1-identifier-not-printed",
              f"{e['label']} misread on {e['document_id']}: {e['value']} vs printed {printed}",
              "error" if lines else "warning", "extraction",
              f"Pipeline read {e['value']} (confidence {e['confidence']}); the page prints {printed}"
              + (" - same digits, transposed." if candidates else ".")
              + (f" Flows to {', '.join(l.split(':', 2)[2] for l in lines)}." if lines else ""),
              nodes=[f"ev:{e['id']}", *lines], evidence=[f"page:{e['document_id']}#{e['page']}"],
              corrections=[Correction(l.split(":", 2)[2], e["value"], printed, "none") for l in lines],
              effect=(0, 0), effect_note="No tax effect; the identifier is wrong on the filed form.")


@check("X2-value-not-printed")
def value_not_printed(c: Ctx):
    """Numbers and dates that do not appear anywhere on the page they were read from."""
    for e in c.p.extracted_values:
        v, vt = e["value"], e["value_type"]
        text = c.p.page_text[(e["document_id"], e["page"])]
        if vt in ("money", "integer", "quantity") and v not in (None, ""):
            fv = round(float(v), 2)
            if fv == 0 and e["text_as_read"] in ("", "0.00", "0"):
                continue  # handled by X3 (blank read as zero) or genuinely printed zero
            if fv in numbers_in(text) or -fv in numbers_in(text):
                continue
        elif vt == "date" and v:
            if any(f in text for f in date_forms(v)):
                continue
        else:
            continue
        lines = c.ev_lines(e["id"])
        c.add("X2-value-not-printed", f"{e['document_id']} {e['label']}: {fmt(v)} is not printed on the page",
              "warning", "extraction",
              f"Pipeline read {fmt(v)} from text '{e['text_as_read']}' (confidence {e['confidence']}), but no such "
              f"amount appears on {e['document_id']} page {e['page']}. Page text: \"{text[:220]}\"",
              nodes=[f"ev:{e['id']}", *lines], evidence=[f"page:{e['document_id']}#{e['page']}"])


@check("X3-blank-read-as-zero")
def blank_read_as_zero(c: Ctx):
    """Nothing printed, yet the pipeline produced 0 with high confidence - and a line used it as an amount."""
    for e in c.p.extracted_values:
        if e["value_type"] != "money" or e["text_as_read"] != "" or e["value"] not in (0, 0.0):
            continue
        lines = c.ev_lines(e["id"])
        if not lines:
            continue
        c.add("X3-blank-read-as-zero",
              f"{e['document_id']} {e['label']}: blank field read as 0.00 (confidence {e['confidence']})",
              "warning", "extraction",
              "The printed field is blank (" + _snippet(c, e) + "). A blank basis is unknown, not zero; "
              f"used by {', '.join(l.split(':', 2)[2] for l in lines)}.",
              nodes=[f"ev:{e['id']}", *lines], evidence=[f"page:{e['document_id']}#{e['page']}"])


def _snippet(c: Ctx, e: dict) -> str:
    text = c.p.page_text[(e["document_id"], e["page"])]
    lot = e["field"].split("_")[0]
    i = text.find(lot + " ")
    return f'printed: "{text[i:i + 170]}..."' if i >= 0 else "field not printed"


@check("X4-low-confidence-in-use")
def low_confidence_in_use(c: Ctx, threshold: float = 0.9):
    for e in c.p.extracted_values:
        if e["confidence"] >= threshold:
            continue
        lines = c.ev_lines(e["id"])
        if not lines:
            continue
        c.add("X4-low-confidence-in-use", f"{e['document_id']} {e['label']} read at confidence {e['confidence']}",
              "warning", "extraction",
              f"Value {fmt(e['value'])} (read as '{e['text_as_read']}') feeds "
              f"{', '.join(l.split(':', 2)[2] for l in lines)}. Printed: \"{c.p.page_text[(e['document_id'], e['page'])][:200]}\"",
              nodes=[f"ev:{e['id']}", *lines], evidence=[f"page:{e['document_id']}#{e['page']}"])


def _norm_page(t: str) -> str:
    t = re.sub(r"^\([^)]*\)\s*", "", t.strip())   # drop scanner/annotation prefix
    return re.sub(r"\s+", " ", t)


@check("X5-duplicate-page-counted-twice")
def duplicate_page(c: Ctx):
    """Two pages of one document with the same content, whose values both reach the same line."""
    for d in c.p.documents:
        pages = d["pages"]
        for i in range(len(pages)):
            for j in range(i + 1, len(pages)):
                a, b = _norm_page(pages[i]["printed_content"]), _norm_page(pages[j]["printed_content"])
                if len(a) < 80 or SequenceMatcher(None, a, b).ratio() < 0.97:
                    continue
                pi, pj = pages[i]["page"], pages[j]["page"]
                evs_j = [e for e in c.p.ev_by_doc.get(d["id"], []) if e["page"] == pj]
                double = defaultdict(list)
                for e in evs_j:
                    for lid in c.ev_lines(e["id"]):
                        twin = next((x for x in c.p.ev_by_doc[d["id"]] if x["page"] == pi and x["field"] == e["field"]), None)
                        if twin and lid in c.ev_lines(twin["id"]):
                            double[lid].append((e, twin))
                for lid, pairs in double.items():
                    key = lid.split(":", 2)[2]
                    line = c.p.line(key)
                    dup = sum(float(e["value"]) for e, _ in pairs)
                    corr = [Correction(key, line["value"], line["value"] - dup, "none")]
                    deltas = []
                    # follow the standard-mileage dependency generically: any line computed from this one at a parameter rate
                    for dep in c.ix.sources(lid, "computed_from"):
                        dl = c.p.line(dep.split(":", 2)[2])
                        rate_params = [s for s in c.ix.targets(dep, "sourced_from") if s.startswith("param:")]
                        if rate_params and dl["rule"] == "R-STANDARD-MILEAGE":
                            rate = c.p.params[rate_params[0][6:]]
                            new = round((line["value"] - dup) * rate)
                            corr.append(Correction(dl["key"], dl["value"], new, "schc_profit"))
                            deltas.append(("schc_profit", dl["value"] - new))  # lower expense -> more profit
                    c.add("X5-duplicate-page-counted-twice",
                          f"{d['id']} page {pj} is a second scan of page {pi}; {key} counts it twice",
                          "error", "engine",
                          f"Pages {pi} and {pj} of '{d['title']}' carry the same content "
                          f"(page {pj} begins: \"{pages[j]['printed_content'][:90]}\"). {key} = {fmt(line['value'])} "
                          f"includes {fmt(dup)} from page {pj} on top of the same {fmt(dup)} from page {pi}.",
                          nodes=[lid, *[f"ev:{e['id']}" for e, _ in pairs], f"page:{d['id']}#{pj}"],
                          evidence=[f"page:{d['id']}#{pi}", f"page:{d['id']}#{pj}"],
                          corrections=corr, deltas=deltas)


@check("X6-partial-extraction")
def partial_extraction(c: Ctx):
    """Pages the pipeline did not read that still print transactions."""
    lot_re = re.compile(r"\b([A-Z]{1,2}\d+) ([^;]*?) [\d.,]+ (?:sh|units) acquired (\S+) sold (\S+) proceeds ([\d,]+\.\d\d) "
                        r"basis ([\d,]+\.\d\d) (short|long)-term (covered|noncovered)")
    for d in c.p.documents:
        if d["extraction"]["status"] != "partial":
            continue
        read = {(e["page"]) for e in c.p.ev_by_doc.get(d["id"], [])}
        fields = {e["field"].split("_")[0] for e in c.p.ev_by_doc.get(d["id"], [])}
        superseded = d["id"] in c.p.latest["documents_superseded"]
        for pg in d["pages"]:
            for m in lot_re.finditer(pg["printed_content"]):
                lot, name, acq, sold, proceeds, basis, term, cov = m.groups()
                if lot in fields:
                    continue
                pr, bs = float(proceeds.replace(",", "")), float(basis.replace(",", ""))
                gain = pr - bs
                box = {("short", "covered"): "A", ("short", "noncovered"): "B",
                       ("long", "covered"): "D", ("long", "noncovered"): "E"}[(term, cov)]
                if superseded:
                    continue  # the corrected document carries the same omission; reported there
                c.add("X6-partial-extraction",
                      f"{d['id']} page {pg['page']} not read: lot {lot} ({name}) missing from Form 8949",
                      "error", "extraction",
                      f"{d['extraction']['reason']} The page prints lot {lot}: acquired {acq}, sold {sold}, proceeds "
                      f"{proceeds}, basis {basis}, {term}-term {cov}. It belongs in Form 8949 box {box}; gain {fmt(gain)}.",
                      nodes=[f"doc:{d['id']}", f"page:{d['id']}#{pg['page']}", c.L(f"F8949.{box}.total")],
                      evidence=[f"page:{d['id']}#{pg['page']}"],
                      corrections=[Correction(f"F8949.{box}.{lot}", None, round(gain, 2), "stcg" if term == "short" else "ltcg")],
                      deltas=[("stcg" if term == "short" else "ltcg", gain, c.ca_category_for_sale(sold))])


@check("X7-summary-vs-detail")
def summary_vs_detail(c: Ctx):
    """Broker summary totals must equal the sum of the lots (the engine only checks proceeds)."""
    for d in c.p.documents:
        evs = c.p.ev_by_doc.get(d["id"], [])
        lots = defaultdict(dict)
        for e in evs:
            m = re.match(r"^([A-Z]{1,2}\d+)_(proceeds|basis|wash|term)$", e["field"])
            if m:
                lots[m[1]][m[2]] = e["value"]
        if not lots:
            continue
        summ = {e["field"]: e for e in evs if re.match(r"^(st|lt)_(proceeds|basis|wash)$", e["field"])}
        for term in ("st", "lt"):
            for fld in ("proceeds", "basis", "wash"):
                s = summ.get(f"{term}_{fld}")
                if not s:
                    continue
                detail = round(sum(float(l.get(fld) or 0) for l in lots.values()
                                   if l.get("term") == ("short" if term == "st" else "long")), 2)
                if abs(detail - float(s["value"])) < 0.01:
                    c.ok("X7-summary-vs-detail", f"{d['id']} {term} {fld}: summary = sum of {len(lots)} lots",
                         float(s["value"]), detail, [f"ev:{s['id']}"])
                else:
                    c.add("X7-summary-vs-detail", f"{d['id']} {term} {fld}: summary {fmt(s['value'])} vs lots {fmt(detail)}",
                          "warning", "document", "Broker summary does not equal its own detail.",
                          nodes=[f"ev:{s['id']}", f"doc:{d['id']}"])


@check("X8-same-income-two-documents")
def same_income_two_documents(c: Ctx):
    """One payment reported on two documents (e.g. a composite 1099 and a stand-alone 1099 for the same account),
    both summed into the same total."""
    ver = c.ver
    by_parent = defaultdict(list)   # parent line -> [(child line, ev)]
    for key, line in c.p.lines[ver].items():
        for s in line["sources"]:
            if s.startswith("ev-"):
                for parent in c.ix.sources(c.L(key), "computed_from"):
                    by_parent[parent].append((key, c.p.ev[s]))
    for parent, items in by_parent.items():
        groups = defaultdict(list)
        for key, e in items:
            if e["value_type"] == "money" and e["value"]:
                groups[round(float(e["value"]), 2)].append((key, e))
        for amt, grp in groups.items():
            docs = {e["document_id"] for _, e in grp}
            if len(docs) < 2:
                continue
            texts = {d: c.p.page_text[(d, next(e["page"] for _, e in grp if e["document_id"] == d))] for d in docs}
            shared = set.intersection(*[set(re.findall(r"ending (\d{4})", t)) for t in texts.values()])
            if not shared:
                continue
            (k1, e1), (k2, e2) = sorted(grp, key=lambda x: x[0])[:2]
            parent_key = parent.split(":", 2)[2]
            cat = "interest" if parent_key.startswith("SchB.2") or parent_key.startswith("SchB.") else "ordinary_income"
            c.add("X8-same-income-two-documents",
                  f"{fmt(amt)} reported on {e1['document_id']} and {e2['document_id']} for account ending "
                  f"{', '.join(shared)} - counted twice in {parent_key}",
                  "error", "engine",
                  f"{k1} ({e1['document_id']}: {texts[e1['document_id']][:120]}...) and {k2} "
                  f"({e2['document_id']}: {texts[e2['document_id']][:140]}...) are the same income for the same "
                  f"account. {parent_key} adds both.",
                  nodes=[c.L(k1), c.L(k2), parent, f"ev:{e1['id']}", f"ev:{e2['id']}"],
                  evidence=[f"page:{e1['document_id']}#{e1['page']}", f"page:{e2['document_id']}#{e2['page']}"],
                  corrections=[Correction(k2, amt, 0, cat)], deltas=[(cat, -amt, c.p.california_category(k2))])


@check("X9-duplicate-document")
def duplicate_document(c: Ctx):
    """Same document uploaded twice (re-upload, phone photo). Report how the engine treated it."""
    docs = [d for d in c.p.documents if c.p.ev_by_doc.get(d["id"])]
    for i, a in enumerate(docs):
        for b in docs[i + 1:]:
            if a["document_type"] != b["document_type"] or a.get("marked_corrected") or b.get("marked_corrected"):
                continue
            va = Counter((e["field"], str(e["value"])) for e in c.p.ev_by_doc[a["id"]])
            vb = Counter((e["field"], str(e["value"])) for e in c.p.ev_by_doc[b["id"]])
            overlap = sum((va & vb).values()) / max(1, min(sum(va.values()), sum(vb.values())))
            if overlap < 0.9:
                continue
            la, lb = c.ix.document_landing(a["id"]), c.ix.document_landing(b["id"])
            both_used = la["status"] == "used" and lb["status"] == "used"
            c.add("X9-duplicate-document", f"{b['id']} duplicates {a['id']} ({a['title']})",
                  "error" if both_used else "info", "document",
                  f"{int(overlap * 100)}% of extracted fields identical. {a['id']}: {la['status']}; {b['id']}: "
                  f"{lb['status']}" + (f" ({lb['reason']})" if lb["reason"] else "") + ".",
                  nodes=[f"doc:{a['id']}", f"doc:{b['id']}"], evidence=[f"doc:{a['id']}", f"doc:{b['id']}"])
