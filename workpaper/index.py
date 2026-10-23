"""Relationship index over the packet: one graph, traversable in both directions.

Node ids (stable, used by every other layer - findings, reviews, adjustments):
  doc:D08                document
  page:D08#1             page of a document (where simulated or real renderings attach)
  ev:ev-0016             extracted value
  line:v3:F1040.1a       return line in a given engine version
  ver:v3                 engine version
  asset:v3:SAC-BLDG      per-version asset row; asset:py:SAC-BLDG for prior-year records
  qa:qa-25 msg:msg-07 call:call-01  client answers / messages / call notes
  tl:tl-21               timeline event
  diag:v3:SCORP_BASIS_INCOMPLETE    engine diagnostic
  py:/carryovers_into_2025/...      prior-year pointer;  agency:/efile ... agency pointer
  param:mileage_rate     engine parameter;  fx:SEK.2025_average  exchange rate
  person:theo            household member

Edge types (src -> dst):
  has_page        doc -> page
  read_from       ev -> page               (value was read from this page)
  sourced_from    line -> ev | py | param | fx | asset | qa | person | tl ...
  computed_from   line -> line             (same version)
  in_version      line -> ver
  uses_doc        ver -> doc               (documents_used)
  supersedes      ver -> doc               (documents_superseded)
  refers_to       diag | tl | msg -> anything they reference
  same_line       line:vN:K -> line:vM:K   (the same line key across versions)
"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field

from .packet import Packet

_LINE_KEY = re.compile(r"^(F\d{4}[A-Z]?|F\d{4}-[CE]|Sch[A-Z0-9]+|SchCA540NR|F540NR|ScheduleS|FTB\d+[A-Z]?)\.")


@dataclass
class Node:
    id: str
    kind: str
    label: str
    data: dict = field(default_factory=dict)


class Index:
    def __init__(self, packet: Packet):
        self.p = packet
        self.nodes: dict[str, Node] = {}
        self.out: dict[str, list[tuple[str, str]]] = defaultdict(list)  # src -> [(type, dst)]
        self.inn: dict[str, list[tuple[str, str]]] = defaultdict(list)  # dst -> [(type, src)]
        self.unresolved: list[tuple[str, str]] = []
        self._build()

    # ------------------------------------------------------------------ build
    def _add(self, nid: str, kind: str, label: str, **data) -> str:
        if nid not in self.nodes:
            self.nodes[nid] = Node(nid, kind, label, data)
        return nid

    def _edge(self, src: str, etype: str, dst: str) -> None:
        if dst not in self.nodes:
            self.unresolved.append((src, dst))
            return
        self.out[src].append((etype, dst))
        self.inn[dst].append((etype, src))

    def resolve(self, ref: str, version: str | None = None) -> str:
        """Map a packet reference string (README reference_formats) to a node id."""
        if ref.startswith("ev-"):
            return f"ev:{ref}"
        if re.fullmatch(r"D\d{2}", ref):
            return f"doc:{ref}"
        m = re.fullmatch(r"doc:(D\d{2})#page(\d+)", ref)
        if m:
            return f"page:{m[1]}#{m[2]}"
        for pre in ("qa", "msg", "call"):
            if ref.startswith(pre + "-"):
                return f"{pre}:{ref}"
        if ref.startswith("py:/") or ref.startswith("agency:/"):
            return ref
        if ref.startswith("asset:"):
            aid = ref.split(":", 1)[1]
            if version and f"asset:{version}:{aid}" in self.nodes:
                return f"asset:{version}:{aid}"
            return f"asset:py:{aid}"
        if ref.startswith("household:"):
            return f"person:{ref.split(':', 1)[1]}"
        if ref.startswith("ref:param."):
            return f"param:{ref[len('ref:param.'):]}"
        if ref.startswith("ref:fx."):
            return f"fx:{ref[len('ref:fx.'):]}"
        if ref.startswith("timeline:"):
            return f"tl:{ref.split(':', 1)[1]}"
        if re.fullmatch(r"tl-\d+", ref):
            return f"tl:{ref}"
        if re.fullmatch(r"v\d+", ref):
            return f"ver:{ref}"
        if version and _LINE_KEY.match(ref):
            return f"line:{version}:{ref}"
        return f"?:{ref}"

    def _ensure_pointer(self, ref: str) -> None:
        """Pointers into prior_years / tax_agency_records become nodes on demand (only if they resolve)."""
        if not (ref.startswith("py:/") or ref.startswith("agency:/")) or ref in self.nodes:
            return
        root, ptr = ref.split(":", 1)
        try:
            val = self.p.resolve_pointer(root, ptr)
        except (KeyError, IndexError, ValueError):
            return
        label = ("prior year " if root == "py" else "agency ") + ptr
        self._add(ref, "prior" if root == "py" else "agency", label, value=val if not isinstance(val, (dict, list)) else None)

    def _build(self) -> None:
        p = self.p
        for d in p.documents:
            did = self._add(f"doc:{d['id']}", "document", d["title"], doc_id=d["id"])
            for pg in d["pages"]:
                self._add(f"page:{d['id']}#{pg['page']}", "page", f"{d['id']} p{pg['page']}")
                self._edge(did, "has_page", f"page:{d['id']}#{pg['page']}")
        for e in p.extracted_values:
            nid = self._add(f"ev:{e['id']}", "extracted_value", f"{e['document_id']} {e['label']}", ev_id=e["id"])
            self._edge(nid, "read_from", f"page:{e['document_id']}#{e['page']}")
        for q in p.client["questionnaire"]:
            self._add(f"qa:{q['id']}", "client_answer", q["question"])
        for m in p.client["messages"]:
            self._add(f"msg:{m['id']}", "client_message", m["text"][:80])
        for c in p.client["call_notes"]:
            self._add(f"call:{c['id']}", "call_note", f"Call {c['date'][:10]}")
        for person in p.household["people"]:
            self._add(f"person:{person['id']}", "person", person["name"])
        for name in p.params:
            self._add(f"param:{name}", "parameter", name)
        for cur, rates in p.params.get("fx", {}).items():
            for rname in rates:
                self._add(f"fx:{cur}.{rname}", "fx_rate", f"{cur} {rname}")
        for a in p.prior["asset_records"]:
            self._add(f"asset:py:{a['asset_id']}", "asset", a["description"], version="prior")
        for t in p.raw["timeline"]:
            self._add(f"tl:{t['id']}", "timeline", t["event"])

        for v in p.versions:
            ver = v["version"]
            self._add(f"ver:{ver}", "version", f"{ver} {v['trigger']}")
            for a in v["assets"]:
                self._add(f"asset:{ver}:{a['asset_id']}", "asset", a["description"], version=ver)
            for l in v["lines"]:
                self._add(f"line:{ver}:{l['key']}", "line", f"{l['key']} {l['label']}", version=ver, key=l["key"])
            for i, g in enumerate(v["diagnostics"]):
                self._add(f"diag:{ver}:{g['code']}", "diagnostic", g["message"], version=ver, severity=g["severity"])

        # second pass: edges (all nodes exist now)
        for v in p.versions:
            ver = v["version"]
            for did in v["documents_used"]:
                self._edge(f"ver:{ver}", "uses_doc", f"doc:{did}")
            for did in v["documents_superseded"]:
                self._edge(f"ver:{ver}", "supersedes", f"doc:{did}")
            for a in v["assets"]:
                for s in a.get("sources", []):
                    nid = self.resolve(s, ver)
                    self._ensure_pointer(nid)
                    if nid.startswith("asset:"):
                        continue
                    self._edge(f"asset:{ver}:{a['asset_id']}", "sourced_from", nid)
                if f"asset:py:{a['asset_id']}" in self.nodes:
                    self._edge(f"asset:{ver}:{a['asset_id']}", "sourced_from", f"asset:py:{a['asset_id']}")
            for l in v["lines"]:
                lid = f"line:{ver}:{l['key']}"
                self._edge(lid, "in_version", f"ver:{ver}")
                for inp in l["inputs"]:
                    self._edge(lid, "computed_from", f"line:{ver}:{inp}")
                for s in l["sources"]:
                    nid = self.resolve(s, ver)
                    self._ensure_pointer(nid)
                    self._edge(lid, "sourced_from", nid)
            for g in v["diagnostics"]:
                for r in g["refs"]:
                    nid = self.resolve(r, ver)
                    self._ensure_pointer(nid)
                    self._edge(f"diag:{ver}:{g['code']}", "refers_to", nid)
        latest = p.latest["version"]
        for t in p.raw["timeline"]:
            for r in t["refs"]:
                nid = self.resolve(r, latest)
                self._ensure_pointer(nid)
                self._edge(f"tl:{t['id']}", "refers_to", nid)
        # same line key across versions
        vers = [v["version"] for v in p.versions]
        for a, b in zip(vers, vers[1:]):
            for key in p.lines[b]:
                if key in p.lines[a]:
                    self._edge(f"line:{b}:{key}", "same_line", f"line:{a}:{key}")
        # message/answer references that are explicit in the text (e.g. "photo attached (D40)")
        for m in p.client["messages"]:
            for did in re.findall(r"\b(D\d{2})\b", m["text"]):
                self._edge(f"msg:{m['id']}", "refers_to", f"doc:{did}")

    # --------------------------------------------------------------- queries
    def targets(self, nid: str, etype: str | None = None) -> list[str]:
        return [d for t, d in self.out.get(nid, []) if etype is None or t == etype]

    def sources(self, nid: str, etype: str | None = None) -> list[str]:
        return [s for t, s in self.inn.get(nid, []) if etype is None or t == etype]

    def doc_of(self, nid: str) -> str | None:
        n = self.nodes.get(nid)
        if not n:
            return None
        if n.kind == "document":
            return nid
        if n.kind == "page":
            return "doc:" + nid.split(":")[1].split("#")[0]
        if n.kind == "extracted_value":
            return f"doc:{self.p.ev[n.data['ev_id']]['document_id']}"
        return None

    def trace_line(self, version: str, key: str, depth: int = 50) -> dict:
        """Downward trace: how a line was built, all the way to document pages."""
        seen: set[str] = set()

        def walk(lid: str, d: int) -> dict:
            line = self.p.line(lid.split(":", 2)[2], version)
            node = {"id": lid, "value": line["value"] if line else None, "rule": line["rule"] if line else None,
                    "inputs": [], "sources": []}
            if lid in seen or d > depth:
                return node
            seen.add(lid)
            for s in self.targets(lid, "sourced_from"):
                entry = {"id": s, "kind": self.nodes[s].kind}
                if s.startswith("ev:"):
                    e = self.p.ev[s[3:]]
                    entry.update(document=e["document_id"], page=e["page"], field=e["field"], value=e["value"],
                                 text_as_read=e["text_as_read"], confidence=e["confidence"], position=e["position"])
                node["sources"].append(entry)
            for i in self.targets(lid, "computed_from"):
                node["inputs"].append(walk(i, d + 1))
            return node

        return walk(f"line:{version}:{key}", 0)

    def lines_fed_by(self, nid: str, version: str) -> dict[str, int]:
        """Upward trace: every line in a version that depends (directly or transitively) on a node,
        with its distance (1 = directly). Breadth-first, so each line keeps its shortest distance.

        A value or parameter reaches lines that cite it as a source; a line reaches the lines computed
        from it. A line does not count as depending on itself."""
        direct = [s for s in self.sources(nid, "sourced_from") if s.startswith(f"line:{version}:")]
        if nid.startswith(f"line:{version}:"):
            direct += self.sources(nid, "computed_from")
        out: dict[str, int] = {}
        frontier, depth = list(dict.fromkeys(direct)), 1
        while frontier:
            nxt = []
            for lid in frontier:
                if lid in out or lid == nid:
                    continue
                out[lid] = depth
                nxt.extend(self.sources(lid, "computed_from"))
            frontier, depth = nxt, depth + 1
        return out

    def document_landing(self, doc_id: str, version: str | None = None) -> dict:
        """Where a document's values landed in a version - or why they did not."""
        version = version or self.p.latest["version"]
        d = self.p.doc[doc_id]
        evs = self.p.ev_by_doc.get(doc_id, [])
        landed: dict[str, list[str]] = {}
        for e in evs:
            for lid in self.sources(f"ev:{e['id']}", "sourced_from"):
                if lid.startswith(f"line:{version}:"):
                    landed.setdefault(e["id"], []).append(lid.split(":", 2)[2])
        v = self.p.version[version]
        if doc_id in v["documents_superseded"]:
            status, why = "superseded", "Replaced by a corrected document."
        elif d["extraction"]["status"] == "not_extracted":
            status, why = "not_extracted", d["extraction"]["reason"]
        elif landed:
            status, why = "used", None
        elif any(doc_id in (l.get("note") or "") for l in v["lines"]):
            l = next(l for l in v["lines"] if doc_id in (l.get("note") or ""))
            status, why = "explained_in_note", f"{l['key']}: {l['note']}"
        elif doc_id in v["documents_used"]:
            status, why = "used_without_line_link", "Engine lists it as used but no line cites its values."
        else:
            status, why = "unused", "No line in this version cites this document."
        return {"document": doc_id, "version": version, "status": status, "reason": why,
                "extraction": d["extraction"], "values": len(evs), "values_landed": len(landed),
                "landed": landed,
                "values_not_landed": [e["id"] for e in evs if e["id"] not in landed]}

    def stats(self) -> dict:
        kinds: dict[str, int] = defaultdict(int)
        for n in self.nodes.values():
            kinds[n.kind] += 1
        return {"nodes": len(self.nodes), "edges": sum(len(v) for v in self.out.values()),
                "by_kind": dict(kinds), "unresolved_refs": len(self.unresolved)}

    def to_json(self) -> dict:
        return {
            "nodes": [{"id": n.id, "kind": n.kind, "label": n.label, **n.data} for n in self.nodes.values()],
            "edges": [{"src": s, "type": t, "dst": d} for s, lst in self.out.items() for t, d in lst],
            "unresolved": [{"src": s, "ref": r} for s, r in self.unresolved],
        }
