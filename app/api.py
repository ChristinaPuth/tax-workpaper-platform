"""Read-only API over the loaded packet/index/findings. No endpoint here writes anything;
writes go through app/events_api.py.
"""
from __future__ import annotations

import re

from fastapi import APIRouter, HTTPException, Request

from .documents import locate_value, render_page

router = APIRouter(prefix="/api")


def _store(request: Request):
    return request.app.state.store


def _finding_dict(f) -> dict:
    return dict(f.to_dict(), related=getattr(f, "related", []))


def _findings_by_node(findings) -> dict[str, dict[str, int]]:
    """node id -> {severity: count}, for flagging rows without fetching every finding."""
    out: dict[str, dict[str, int]] = {}
    for f in findings:
        for n in f.nodes:
            c = out.setdefault(n, {})
            c[f.severity] = c.get(f.severity, 0) + 1
    return out


def _line_not_found(version: str, key: str) -> HTTPException:
    return HTTPException(404, f"no line {key!r} in version {version!r}")


# ---------------------------------------------------------------------- overview
@router.get("/overview")
def overview(request: Request) -> dict:
    s = _store(request)
    p = s.packet
    sev: dict[str, int] = {}
    for f in s.findings:
        sev[f.severity] = sev.get(f.severity, 0) + 1
    return {
        "household": {"filing_status": p.household["filing_status"], "tax_year": p.tax_year,
                      "people": [{"id": pid, "name": person["name"]} for pid, person in p.person.items()]},
        "versions": [{"version": v["version"], "trigger": v["trigger"], "computed_at": v["computed_at"],
                      "summary": v["summary"]} for v in p.versions],
        "latest_version": p.latest["version"],
        "index_stats": s.index.stats(),
        "findings_total": len(s.findings),
        "findings_by_severity": sev,
        "documents_total": len(p.documents),
    }


# ----------------------------------------------------------------------- versions / lines
@router.get("/versions")
def list_versions(request: Request) -> list[dict]:
    p = _store(request).packet
    return [{"version": v["version"], "trigger": v["trigger"], "computed_at": v["computed_at"],
             "documents_used": len(v["documents_used"]), "documents_superseded": v["documents_superseded"],
             "summary": v["summary"], "lines": len(v["lines"])} for v in p.versions]


@router.get("/versions/{version}/lines")
def version_lines(version: str, request: Request, area: str | None = None) -> list[dict]:
    p = _store(request).packet
    lines = p.lines.get(version)
    if lines is None:
        raise HTTPException(404, f"no version {version!r}")
    out = lines.values()
    if area:
        out = [l for l in out if l["form"] == area]
    findings = _store(request).findings
    flags = _findings_by_node(findings)
    refs: dict[str, list[dict]] = {}
    for f in findings:
        for n in f.nodes:
            refs.setdefault(n, []).append({"id": f.id, "severity": f.severity})
    return [{"key": l["key"], "form": l["form"], "line": l["line"], "label": l["label"], "value": l["value"],
             "jurisdiction": l["jurisdiction"], "rule": l["rule"],
             "findings": flags.get(f"line:{version}:{l['key']}", {}),
             "finding_refs": refs.get(f"line:{version}:{l['key']}", [])} for l in out]


@router.get("/lines/{key}")
def line_detail(key: str, request: Request) -> dict:
    s = _store(request)
    p, ix = s.packet, s.index
    across = {v["version"]: p.line(key, v["version"]) for v in p.versions}
    across = {ver: l for ver, l in across.items() if l is not None}
    if not across:
        raise HTTPException(404, f"no line {key!r} in any version")
    latest_ver = max(across, key=lambda v: [vv["version"] for vv in p.versions].index(v))
    latest = across[latest_ver]
    rule_text = p.rules.get(latest["rule"]) if latest.get("rule") else None
    findings = [_finding_dict(f) for f in s.findings if f"line:{latest_ver}:{key}" in f.nodes]
    return {
        "key": key, "label": latest["label"], "form": latest["form"], "line": latest["line"],
        "jurisdiction": latest["jurisdiction"], "latest_version": latest_ver,
        "by_version": {ver: {"value": l["value"], "rule": l["rule"], "note": l.get("note")}
                       for ver, l in across.items()},
        "rule": latest.get("rule"), "rule_text": rule_text, "inputs": latest["inputs"], "sources": latest["sources"],
        "note": latest.get("note"), "findings": findings,
    }


@router.get("/trace/{version}/{key}")
def trace(version: str, key: str, request: Request) -> dict:
    s = _store(request)
    if s.packet.line(key, version) is None:
        raise _line_not_found(version, key)
    return s.index.trace_line(version, key)


# ------------------------------------------------------------------------ impact (upward trace)
@router.get("/impact/{node_id:path}")
def impact(node_id: str, request: Request, version: str | None = None) -> dict:
    s = _store(request)
    p, ix = s.packet, s.index
    if node_id not in ix.nodes:
        raise HTTPException(404, f"no node {node_id!r}")
    version = version or p.latest["version"]
    fed = ix.lines_fed_by(node_id, version)
    detail = []
    for lid in sorted(fed, key=lambda l: (fed[l], l)):  # nearest first
        line = p.line(lid.split(":", 2)[2], version)
        detail.append({"key": line["key"], "label": line["label"], "value": line["value"], "distance": fed[lid]})
    return {"node": node_id, "version": version, "label": ix.nodes[node_id].label, "lines_fed": detail}


# ------------------------------------------------------------------------- documents
@router.get("/documents")
def list_documents(request: Request) -> list[dict]:
    s = _store(request)
    p, ix = s.packet, s.index
    out = []
    for d in p.documents:
        landing = ix.document_landing(d["id"])
        out.append({"id": d["id"], "title": d["title"], "document_type": d["document_type"],
                     "received_at": d["received_at"], "page_count": d["page_count"],
                     "extraction_status": d["extraction"]["status"], "landing_status": landing["status"],
                     "values": landing["values"], "values_landed": landing["values_landed"],
                     "coverage": s.coverage.get(d["id"])})
    return out


@router.get("/documents/{doc_id}")
def document_detail(doc_id: str, request: Request) -> dict:
    s = _store(request)
    p, ix = s.packet, s.index
    d = p.doc.get(doc_id)
    if d is None:
        raise HTTPException(404, f"no document {doc_id!r}")
    findings = [_finding_dict(f) for f in s.findings if any(ix.doc_of(n) == f"doc:{doc_id}" for n in f.nodes + f.evidence)]
    return {**{k: v for k, v in d.items() if k != "pages"}, "pages": [p_["page"] for p_ in d["pages"]],
            "landing": ix.document_landing(doc_id), "coverage": s.coverage.get(doc_id), "findings": findings}


@router.get("/documents/{doc_id}/pages/{page}")
def document_page(doc_id: str, page: int, request: Request) -> dict:
    s = _store(request)
    if doc_id not in s.packet.doc:
        raise HTTPException(404, f"no document {doc_id!r}")
    try:
        return render_page(s.packet, s.index, doc_id, page)
    except KeyError as e:
        raise HTTPException(404, str(e)) from e


@router.get("/values/{ev_id}")
def value_layers(ev_id: str, request: Request, version: str | None = None) -> dict:
    """The three layers of one extracted value: what is printed on the page, what the pipeline
    read, and what the return uses. Disagreement between layers is where confident mistakes hide."""
    s = _store(request)
    p, ix = s.packet, s.index
    e = p.ev.get(ev_id)
    if e is None:
        raise HTTPException(404, f"no extracted value {ev_id!r}")
    version = version or p.latest["version"]
    text = p.page_text.get((e["document_id"], e["page"]), "")
    span = locate_value(text, e)
    used = []
    for lid in ix.sources(f"ev:{ev_id}", "sourced_from"):
        if lid.startswith(f"line:{version}:"):
            line = p.line(lid.split(":", 2)[2], version)
            used.append({"key": line["key"], "label": line["label"], "value": line["value"], "rule": line["rule"],
                         "sources": len(line["sources"])})
    nid = f"ev:{ev_id}"
    return {
        "id": ev_id, "document": e["document_id"], "page": e["page"], "field": e["field"], "label": e["label"],
        "printed": {"found": span is not None, "text": text[span["start"]:span["end"]] if span else None,
                    "span": span, "context": text[max(0, span["start"] - 80):span["end"] + 80] if span else None},
        "extracted": {"value": e["value"], "value_type": e["value_type"], "text_as_read": e["text_as_read"],
                      "confidence": e["confidence"]},
        "used": used, "version": version,
        "findings": [_finding_dict(f) for f in s.findings if nid in f.nodes],
    }


@router.get("/nodes/{node_id:path}")
def node_preview(node_id: str, request: Request) -> dict:
    """A one-line preview of any node id, for hover cards on references."""
    ix = _store(request).index
    n = ix.nodes.get(node_id)
    if n is None:
        raise HTTPException(404, f"no node {node_id!r}")
    doc = ix.doc_of(node_id)
    return {"id": n.id, "kind": n.kind, "label": n.label, "document": doc.split(":", 1)[1] if doc else None,
            "data": {k: v for k, v in n.data.items() if isinstance(v, (str, int, float, bool)) or v is None}}


# -------------------------------------------------------------------------- findings
@router.get("/findings")
def list_findings(request: Request, severity: str | None = None, origin: str | None = None,
                   check: str | None = None, node: str | None = None) -> list[dict]:
    findings = _store(request).findings
    if severity:
        findings = [f for f in findings if f.severity == severity]
    if origin:
        findings = [f for f in findings if f.origin == origin]
    if check:
        findings = [f for f in findings if f.check == check]
    if node:
        findings = [f for f in findings if node in f.nodes]
    return [_finding_dict(f) for f in findings]


@router.get("/findings/{finding_id}")
def finding_detail(finding_id: str, request: Request) -> dict:
    findings = _store(request).findings
    f = next((f for f in findings if f.id == finding_id), None)
    if f is None:
        raise HTTPException(404, f"no finding {finding_id!r}")
    return _finding_dict(f)


# --------------------------------------------------------------------------- search
def _as_amount(q: str) -> float | None:
    """'163,700', '$12,400.00', '-8256' -> a number; anything with letters -> None."""
    t = q.strip().replace(",", "").replace("$", "").replace(" ", "")
    if not t or not any(ch.isdigit() for ch in t):
        return None
    try:
        return float(t)
    except ValueError:
        return None


def _rank(needle: str, *fields: str) -> int | None:
    """0 exact, 1 prefix, 2 contains (on any field); None if no match."""
    best = None
    for f in fields:
        f = (f or "").lower()
        r = 0 if f == needle else 1 if f.startswith(needle) else 2 if needle in f else None
        if r is not None and (best is None or r < best):
            best = r
    return best


@router.get("/search")
def search(q: str, request: Request, limit: int = 25) -> dict:
    """One box for the whole return: amounts (163,700), lines (gross receipts, SchC.1), documents (W-2, D23),
    people (household, staff, client users), values as read, and issues. A query that reads as a number is
    searched both as an amount (exact matches first) and as text ("3520" also finds "Form 3520"). Lines
    come from the current version only, best match first."""
    s = _store(request)
    p = s.packet
    needle = q.strip().lower()
    out = {"query": q, "amount": None, "lines": [], "documents": [], "people": [], "extracted_values": [],
           "findings": []}
    if not needle:
        return out
    version = p.latest["version"]
    amount = _as_amount(needle)
    out["amount"] = amount

    def line_row(l: dict) -> dict:
        return {"version": version, "key": l["key"], "label": l["label"], "value": l["value"], "form": l["form"]}

    def merge(first: list[dict], then: list[dict], key: str = "id") -> list[dict]:
        seen, out_ = set(), []
        for x in first + then:
            if x[key] not in seen:
                seen.add(x[key])
                out_.append(x)
        return out_[:limit]

    def ev_row(e: dict) -> dict:
        return {"id": e["id"], "document_id": e["document_id"], "page": e["page"], "label": e["label"],
                "text_as_read": e["text_as_read"]}

    # text matches - always, so "3520" still finds "Form 3520" and "D23" finds the document
    ranked = [(r, l) for l in p.lines[version].values() if (r := _rank(needle, l["key"], l["label"])) is not None]
    text_lines = [line_row(l) for _, l in sorted(ranked, key=lambda x: x[0])]
    docs = [(r, d) for d in p.documents
            if (r := _rank(needle, d["id"], d["title"], d["document_type"], d.get("issuer", ""))) is not None]
    out["documents"] = [{"id": d["id"], "title": d["title"], "document_type": d["document_type"]}
                        for _, d in sorted(docs, key=lambda x: x[0])][:limit]
    people = [{"id": f"person:{pid}", "name": x["name"], "role": x.get("role", "household")}
              for pid, x in p.person.items() if needle in x["name"].lower()]
    people += [{"id": s_["id"], "name": s_["name"], "role": s_["role"]}
               for s_ in p.firm["staff"] + p.firm.get("client_users", []) if needle in s_["name"].lower()]
    out["people"] = people[:limit]
    text_evs = [ev_row(e) for e in p.extracted_values
                if needle in (e["text_as_read"] or "").lower() or needle in e["label"].lower()]
    text_findings = [_finding_dict(f) for f in s.findings
                     if needle in f.title.lower() or needle in f.detail.lower()]

    # amount matches - when the query reads as a number, exact amounts come first
    amount_lines, amount_evs, amount_findings = [], [], []
    if amount is not None:
        amount_lines = [line_row(l) for l in p.lines[version].values()
                        if isinstance(l["value"], (int, float)) and abs(abs(float(l["value"])) - abs(amount)) <= 0.5]
        amount_evs = [ev_row(e) for e in p.extracted_values
                      if isinstance(e["value"], (int, float)) and not isinstance(e["value"], bool)
                      and abs(abs(float(e["value"])) - abs(amount)) <= 0.5]
        # whole numbers only: 12,400 must not match 212,400
        shown = re.compile(r"(?<![\d,.])" + re.escape(f"{abs(amount):,.0f}") + r"(?![\d,]|\.\d)")
        amount_findings = [_finding_dict(f) for f in s.findings if shown.search(f.title) or shown.search(f.detail)]

    out["lines"] = merge(amount_lines, text_lines, "key")
    out["extracted_values"] = merge(amount_evs, text_evs)
    out["findings"] = merge(amount_findings, text_findings)
    return out

    ranked = [(r, l) for l in p.lines[version].values() if (r := _rank(needle, l["key"], l["label"])) is not None]
    out["lines"] = [line_row(l) for _, l in sorted(ranked, key=lambda x: x[0])][:limit]
    docs = [(r, d) for d in p.documents
            if (r := _rank(needle, d["id"], d["title"], d["document_type"], d.get("issuer", ""))) is not None]
    out["documents"] = [{"id": d["id"], "title": d["title"], "document_type": d["document_type"]}
                        for _, d in sorted(docs, key=lambda x: x[0])][:limit]
    people = [{"id": f"person:{pid}", "name": x["name"], "role": x.get("role", "household")}
              for pid, x in p.person.items() if needle in x["name"].lower()]
    people += [{"id": s_["id"], "name": s_["name"], "role": s_["role"]}
               for s_ in p.firm["staff"] + p.firm.get("client_users", []) if needle in s_["name"].lower()]
    out["people"] = people[:limit]
    out["extracted_values"] = [
        {"id": e["id"], "document_id": e["document_id"], "page": e["page"], "label": e["label"],
         "text_as_read": e["text_as_read"]} for e in p.extracted_values
        if needle in (e["text_as_read"] or "").lower() or needle in e["label"].lower()][:limit]
    out["findings"] = [_finding_dict(f) for f in s.findings
                       if needle in f.title.lower() or needle in f.detail.lower()][:limit]
    return out
