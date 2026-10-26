"""Every area considered: the firm's nine budget areas, each considered or marked not applicable.

An area is one of the firm's budget areas (firm.budget_hours). For each one the file says how much of the
return is in it (lines with an amount, documents) and which issues are still open there. The preparer records
that the area was considered - or that it does not apply, with the basis - as an "area" decision on the whole
return. Partner review is the partner's sign-off on the whole return, so it is never marked by hand.
A decision is refused while the area still has an open error, and "not applicable" is refused for an area
that has amounts on the return.
"""
from __future__ import annotations

from .inbox import _DOC_AREA, area_of, finding_state
from .logview import LogView

AREAS = {  # budget area -> the areas the rest of the app files lines, documents and issues under
    "intake_and_engagement": (["intake"], ["prior", "outside"]),
    "wages_and_stock_compensation": (["wages"], ["tax"]),
    "investments_and_digital_assets": (["investments"], ["carryovers"]),
    "business": (["business"], ["books", "depreciation"]),
    "rentals_and_sale": (["rentals"], ["rentals", "depreciation"]),
    "pass_throughs_and_basis": (["passthroughs"], ["k1"]),
    "deductions_and_credits": (["deductions", "payments"], ["deductions", "payments"]),
    "california": (["california"], ["state"]),
    "partner_review": (["totals"], ["tax", "rollforward"]),
}
BY_HAND = [a for a in AREAS if a != "partner_review"]


def _title(key: str) -> str:
    return key.replace("_and_", " & ").replace("_", " ").capitalize().replace("Pass throughs", "Pass-throughs")


def coverage(packet, findings, events: list[dict], version: str, signoffs: list[dict], people: dict) -> dict:
    log = LogView(events)
    name = lambda pid: people[pid].name if pid in people else pid  # noqa: E731
    lines: dict[str, int] = {}
    for key, line in packet.lines[version].items():
        if isinstance(line["value"], (int, float)) and line["value"]:
            a = area_of([f"line:{version}:{key}"], packet)
            lines[a] = lines.get(a, 0) + 1
    docs: dict[str, int] = {}
    for d in packet.documents:
        a = _DOC_AREA.get(d["document_type"], "intake")
        docs[a] = docs.get(a, 0) + 1
    open_: dict[str, list] = {}
    for f in findings:
        if f.severity != "info" and finding_state(f, log, version)["state"] == "open":
            open_.setdefault(area_of(f.nodes, packet), []).append(f)
    decided = {}
    for e in log.of_type("judgment"):
        if e["payload"].get("kind") == "area":
            decided[e["payload"].get("area")] = e
    ret = f"ver:{version}"
    partner = next((s for s in reversed(signoffs) if s["target"] == ret and s["level"] == "partner" and s["valid"]), None)
    out = []
    for key, hours in packet.firm["budget_hours"].items():
        covers, reports = AREAS.get(key, ([], []))
        fs = [f for a in covers for f in open_.get(a, [])]
        d = decided.get(key)
        if key == "partner_review":
            status = "considered" if partner else "open"
            record = {"by": name(partner["actor"]), "at": partner["at"], "decision": "Partner signed off the whole return",
                      "authority": None, "event_id": partner["event_id"]} if partner else None
        else:
            status = ("considered" if d["payload"].get("applies") else "not_applicable") if d else "open"
            record = {"by": name(d["actor"]), "at": d["at"], "decision": d["payload"].get("decision"),
                      "authority": d["payload"].get("authority"), "event_id": d["id"]} if d else None
        out.append({"key": key, "title": _title(key), "budget_hours": hours, "status": status, "by_hand": key != "partner_review",
                    "lines": sum(lines.get(a, 0) for a in covers), "documents": sum(docs.get(a, 0) for a in covers),
                    "open_errors": [f.id for f in fs if f.severity == "error"],
                    "open_warnings": [f.id for f in fs if f.severity == "warning"],
                    "reports": reports, "record": record})
    left = [a for a in out if a["by_hand"] and a["status"] == "open"]
    return {"areas": out, "left": [a["key"] for a in left],
            "summary": {"considered": sum(1 for a in out if a["status"] != "open"), "total": len(out)}}


def validate_area(packet, findings, events: list[dict], version: str, payload: dict) -> str | None:
    """Why an area decision cannot be recorded, or None."""
    key = payload.get("area")
    if key == "partner_review":
        return "partner review is the partner's sign-off on the whole return"
    if key not in BY_HAND:
        return f"area must be one of {BY_HAND}"
    if not isinstance(payload.get("applies"), bool):
        return "say whether the area applies (payload.applies true or false)"
    c = next(a for a in coverage(packet, findings, events, version, [], {})["areas"] if a["key"] == key)
    if payload["applies"] and c["open_errors"]:
        return f"settle the {len(c['open_errors'])} open error(s) in this area first ({', '.join(c['open_errors'][:4])})"
    if not payload["applies"] and (c["lines"] or c["open_errors"] or c["open_warnings"]):
        return (f"this area has {c['lines']} line(s) with amounts on the return, so it applies" if c["lines"]
                else "this area still has open issues, so it applies")
    return None
