"""Who does what by when: the team on the engagement, work assigned to a person, the firm's deadlines,
and each person's notifications.

The team comes from firm.assignment_at_start; anything more specific is an assign event on a node (to whom,
optionally by when). An assignment is done once that person does work on the node after it was assigned.
Deadlines come from firm.deadlines, counted from the firm's 'today' in the packet; the internal ones are met
by the sign-off they stand for, the filing ones by filing. Nothing here is stored apart from the event log.
"""
from __future__ import annotations

from datetime import date

from .logview import LogView, filing_status

WORK = {"adjust", "verify", "judgment", "signoff", "answer", "note", "attach", "resolve_note", "link"}
SOON = 14  # days


def team(packet, people: dict) -> list[dict]:
    return [{"role": role, "id": pid, "name": people[pid].name if pid in people else pid}
            for role, pid in packet.firm["assignment_at_start"].items()]


def assignments(events: list[dict], people: dict, today: date) -> list[dict]:
    log = LogView(events)
    name = lambda pid: people[pid].name if pid in people else pid  # noqa: E731
    out = []
    for a in log.of_type("assign"):
        to = a["payload"].get("to")
        done = next((e for e in log.by_target.get(a["target"], []) if e["actor"] == to and e["id"] > a["id"]
                     and e["type"] in WORK), None)
        due = a["payload"].get("due")
        out.append({"event_id": a["id"], "target": a["target"], "to": to, "to_name": name(to), "by": a["actor"],
                    "by_name": name(a["actor"]), "at": a["at"], "due": due, "note": a["payload"].get("note"),
                    "status": "done" if done else "open", "done_at": done["at"] if done else None,
                    "days_left": (date.fromisoformat(due) - today).days if due and not done else None})
    # a newer assignment of the same node replaces the older one while both are open
    latest = {}
    for a in out:
        if a["status"] == "open":
            latest[a["target"]] = a["event_id"]
    return [a for a in out if a["status"] == "done" or latest.get(a["target"]) == a["event_id"]]


def deadlines(packet, events: list[dict], signoffs: list[dict], today: date) -> list[dict]:
    ret = f"ver:{packet.latest['version']}"
    held = lambda level: next((s["at"][:10] for s in signoffs if s["target"] == ret and s["level"] == level  # noqa: E731
                               and s["valid"]), None)
    filed = filing_status(events)["filed"]
    extended = next((t["at"][:10] for t in packet.raw.get("timeline", []) if t.get("event") == "extension_filed_with_payment"
                     and t["at"][:10] <= today.isoformat()), None)
    out = []
    for d in packet.firm["deadlines"]:
        what, when = d["what"], date.fromisoformat(d["date"])
        low = what.lower()
        if "outside engagement" in low:
            kind, met, role = "outside", None, None
        elif "hand-off" in low:
            kind, met, role = "internal", held("preparer"), "preparer"
        elif "review complete" in low:
            kind, met, role = "internal", held("reviewer"), "reviewer"
        else:
            kind, met, role = "filing", filed["at"][:10] if filed else None, None
        days = (when - today).days
        if kind == "filing" and "original due date" in low and extended and not met:
            kind, met = "extended", extended
        status = ("extended" if kind == "extended" else "met" if met else "outside" if kind == "outside" else "overdue" if days < 0
                  else "soon" if days <= SOON else "upcoming")
        out.append({"what": what, "date": d["date"], "kind": kind, "days_left": days, "met": met, "status": status,
                    "for": role})
    return sorted(out, key=lambda d: d["date"])


def notifications(person, events: list[dict], packet, people: dict, signoffs: list[dict], today: date) -> list[dict]:
    """What is waiting for this person: assignments, questions, deadlines close or past."""
    log = LogView(events)
    name = lambda pid: people[pid].name if pid in people else pid  # noqa: E731
    items = []
    for a in assignments(events, people, today):
        if a["to"] == person.id and a["status"] == "open":
            items.append({"kind": "assignment", "target": a["target"], "at": a["at"], "due": a["due"],
                          "title": f"{a['by_name']} assigned you this" + (f": {a['note']}" if a["note"] else ""),
                          "urgent": a["days_left"] is not None and a["days_left"] <= 3})
    for q in log.of_type("question"):
        if q["payload"].get("to") == person.id and q["id"] not in log.answered:
            items.append({"kind": "question", "target": q["target"], "at": q["at"], "due": None,
                          "title": f"{name(q['actor'])} asked: {q['payload'].get('text', '')}", "urgent": False})
    if person.is_staff and person.role != "firm_administrator":
        for d in deadlines(packet, events, signoffs, today):
            owner = packet.firm["assignment_at_start"].get(d["for"]) if d["for"] else None
            if d["status"] in ("overdue", "soon") and owner in (None, person.id):
                items.append({"kind": "deadline", "target": None, "at": d["date"], "due": d["date"],
                              "title": f"{d['what']} - " + (f"{-d['days_left']} days overdue" if d["days_left"] < 0
                                                            else "today" if d["days_left"] == 0 else f"in {d['days_left']} days"),
                              "urgent": d["status"] == "overdue"})
    return sorted(items, key=lambda i: (not i["urgent"], i["due"] or "9999", i["at"]))
