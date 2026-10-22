"""Read-only API over the loaded packet/index/findings. No endpoint here writes anything;
writes go through app/events_api.py.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from .documents import render_page

router = APIRouter(prefix="/api")


def _store(request: Request):
    return request.app.state.store


def _finding_dict(f) -> dict:
    return dict(f.to_dict(), related=getattr(f, "related", []))


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
    return [{"key": l["key"], "form": l["form"], "line": l["line"], "label": l["label"], "value": l["value"],
             "jurisdiction": l["jurisdiction"]} for l in out]


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
    lines = sorted(ix.lines_fed_by(node_id, version))
    detail = [{"key": lid.split(":", 2)[2], "label": p.line(lid.split(":", 2)[2], version)["label"],
               "value": p.line(lid.split(":", 2)[2], version)["value"]} for lid in lines]
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
@router.get("/search")
def search(q: str, request: Request, limit: int = 25) -> dict:
    s = _store(request)
    p = s.packet
    needle = q.strip().lower()
    if not needle:
        return {"lines": [], "documents": [], "extracted_values": [], "findings": []}
    lines = [{"version": v["version"], "key": l["key"], "label": l["label"], "value": l["value"]}
             for v in p.versions for l in v["lines"]
             if needle in l["key"].lower() or needle in l["label"].lower()][:limit]
    documents = [{"id": d["id"], "title": d["title"]} for d in p.documents if needle in d["title"].lower()][:limit]
    evs = [{"id": e["id"], "document_id": e["document_id"], "page": e["page"], "label": e["label"],
            "text_as_read": e["text_as_read"]} for e in p.extracted_values
           if needle in (e["text_as_read"] or "").lower() or needle in e["label"].lower()][:limit]
    findings = [_finding_dict(f) for f in s.findings if needle in f.title.lower() or needle in f.detail.lower()][:limit]
    return {"lines": lines, "documents": documents, "extracted_values": evs, "findings": findings}
