"""What an item is connected to beyond how it was computed: the same line last year, the related returns
it depends on (a K-1's partnership or S corporation return, a dependent's own return), and links people made.

Related returns come from household.related_returns: a return is related to a line when the line's sources
are documents that return produced (its K-1s), or when it is a dependent's return and the line is about
dependents. A person links two items with a link event (payload.to); the link shows on both.
"""
from __future__ import annotations

import re

from .logview import LogView

DEPENDENT_FORMS = ("F8812", "F8867", "F8863", "F2441")


def _docs_of(packet, version: str, key: str) -> set[str]:
    line = packet.line(key, version) or {}
    return {packet.ev[s]["document_id"] for s in line.get("sources", []) if s in packet.ev}


def related(packet, events: list[dict], node: str, people: dict) -> dict:
    name = lambda pid: people[pid].name if pid in people else pid  # noqa: E731
    log = LogView(events)
    manual = []
    for e in log.of_type("link"):
        other = e["payload"].get("to") if e["target"] == node else e["target"] if e["payload"].get("to") == node else None
        if other:
            manual.append({"event_id": e["id"], "other": other, "note": e["payload"].get("note"), "by": e["actor"],
                           "by_name": name(e["actor"]), "at": e["at"]})
    docs: set[str] = set()
    form = key = None
    if node.startswith("line:"):
        _, version, key = node.split(":", 2)
        docs, form = _docs_of(packet, version, key), key.split(".")[0]
    elif node.startswith(("doc:", "page:")):
        docs = {node.split(":", 1)[1].split("#")[0]}
    person = node.split(":", 1)[1] if node.startswith("person:") else None
    names = {p["name"]: p["id"] for p in packet.household["people"]}
    returns = []
    for r in packet.household.get("related_returns", []):
        made = set(re.findall(r"\bD\d{2}\b", str(r.get("in_this_packet") or "")))
        pid = names.get(r["who"])
        why = (f"its K-1s ({', '.join(sorted(made & docs))}) are sources here" if made & docs
               else "this is about the dependent who files it" if pid and (pid == person or form in DEPENDENT_FORMS)
               else None)
        if why:
            returns.append({"who": r["who"], "return": r["return"], "prepared_by": r["prepared_by"],
                            "in_this_packet": r["in_this_packet"], "documents": sorted(made), "why": why})
    prior = None
    if key:
        py = packet.raw["prior_years"]["return_2024"]
        if key in py["lines"]:
            prior = {"year": 2024, "value": py["lines"][key], "label": py.get("line_labels", {}).get(key)}
    return {"node": node, "prior_year": prior, "related_returns": returns, "links": manual}
