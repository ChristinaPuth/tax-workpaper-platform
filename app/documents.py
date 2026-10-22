"""Simulated source-document rendering.

The packet has no page images (README `no_page_images`): `position` on each extracted
value is synthetic, not a real layout box. This module locates each value inside its
page's `printed_content` text instead, so the UI can highlight the exact span. A real
pipeline would replace `locate_value` with real OCR/layout boxes; callers only ever see
`{"start": int, "end": int}` or `None` either way, so the swap is contained here.
"""
from __future__ import annotations

import re

from workpaper.index import Index
from workpaper.packet import Packet

_WORD = re.compile(r"[A-Za-z0-9]+")


def _tokens(s: str) -> set[str]:
    return {w.lower() for w in _WORD.findall(s)}


def _needle_pattern(needle: str) -> re.Pattern:
    # a bare word/number (e.g. a checkbox "X" or an SSN) must match as a whole token,
    # or it would hit every occurrence of that character inside unrelated words
    if _WORD.fullmatch(needle):
        return re.compile(r"(?<![A-Za-z0-9])" + re.escape(needle) + r"(?![A-Za-z0-9])")
    return re.compile(re.escape(needle))


def _candidates(ev: dict) -> list[str]:
    """text_as_read is the pipeline's normalized reading; printed_content can state the same
    value in a different format (ISO date vs MM/DD/YYYY, "$4,800" vs "4,800.00"). Try the
    normalized reading first, then formats derived from the parsed value, most specific first."""
    out = [ev["text_as_read"]] if ev.get("text_as_read") else []
    value, vtype = ev.get("value"), ev.get("value_type")
    if vtype == "date" and isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        y, m, d = value.split("-")
        out += [value, f"{int(m)}/{int(d)}/{y}", f"{m}/{d}/{y}"]
    elif vtype == "money" and isinstance(value, (int, float)):
        if value == int(value):
            out += [f"${int(value):,}", f"{int(value):,}"]
        out += [f"${value:,.2f}", f"{value:,.2f}"]
    elif vtype == "percent" and isinstance(value, (int, float)):
        out += [f"{value:g}%", f"{value * 100:g}%"]
    elif vtype == "integer" and isinstance(value, (int, float)):
        out += [f"{int(value):,}", str(int(value))]
    seen: set[str] = set()
    return [c for c in out if c and not (c in seen or seen.add(c))]


def locate_value(page_text: str, ev: dict) -> dict | None:
    """Best-effort character span of ev's value within page_text, or None if not printed there.

    When the matched text appears more than once on a page (e.g. a W-2 with Box 3 and
    Box 5 both "118,000.00"), the occurrence whose preceding ~60 characters share the
    most words with the field's label/field name wins (e.g. "Box 3" beats "Box 5").
    """
    for needle in _candidates(ev):
        positions = [m.start() for m in _needle_pattern(needle).finditer(page_text)]
        if not positions:
            continue
        if len(positions) == 1:
            start = positions[0]
        else:
            label_tokens = _tokens(f"{ev.get('field', '')} {ev.get('label', '')}")
            start = max(positions, key=lambda pos: len(_tokens(page_text[max(0, pos - 60):pos]) & label_tokens))
        return {"start": start, "end": start + len(needle)}
    return None


def field_view(packet: Packet, index: Index, ev: dict, span: dict | None) -> dict:
    flows_to = [{"version": lid.split(":", 2)[1], "key": lid.split(":", 2)[2]}
                for lid in index.sources(f"ev:{ev['id']}", "sourced_from") if lid.startswith("line:")]
    return {"ev_id": ev["id"], "field": ev["field"], "label": ev["label"], "value": ev["value"],
            "value_type": ev["value_type"], "text_as_read": ev["text_as_read"], "confidence": ev["confidence"],
            "position": ev["position"], "span": span, "flows_to": flows_to}


def render_page(packet: Packet, index: Index, doc_id: str, page: int) -> dict:
    d = packet.doc[doc_id]
    pg = next((p for p in d["pages"] if p["page"] == page), None)
    if pg is None:
        raise KeyError(f"{doc_id} has no page {page}")
    text = pg["printed_content"]
    evs = [e for e in packet.ev_by_doc.get(doc_id, []) if e["page"] == page]
    fields = [field_view(packet, index, e, locate_value(text, e)) for e in evs]
    return {"document": doc_id, "page": page, "printed_content": text, "fields": fields}


def page_coverage(packet: Packet, doc_id: str) -> dict:
    """How many of this document's values could be located on their printed page - a located=False
    value is itself informative (blank field, checkbox, or a misread that is not on the page at all)."""
    located = not_located = 0
    for e in packet.ev_by_doc.get(doc_id, []):
        d = packet.doc[doc_id]
        pg = next((p for p in d["pages"] if p["page"] == e["page"]), None)
        text = pg["printed_content"] if pg else ""
        if locate_value(text, e) is not None:
            located += 1
        else:
            not_located += 1
    return {"located": located, "not_located": not_located}
