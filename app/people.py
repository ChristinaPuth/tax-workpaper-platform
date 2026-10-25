"""Who can do what. Identities come from the packet (firm staff, client users); the role switcher
picks one, and every write is checked here on the server - hiding a button is not enforcement.

Firm rules from firm.starter_standards.rules enforced at write time:
  - A person may not review or sign off on work they prepared.
  - Staff without sensitive-data clearance see SSNs, bank and account numbers and IP PINs masked;
    every unmasked view is logged (as a view_sensitive event).
Rules enforced at filing time (the gate, later): open blocking review notes, partner sign-off for
adjustments over 1,000 of tax effect, due diligence.
"""
from __future__ import annotations

from dataclasses import dataclass

from workpaper.packet import Packet

LEVELS = ["preparer", "reviewer", "partner"]  # starter_standards.review_levels, lowest first

EVENT_TYPES = {
    "note",            # free comment on any node
    "review_note",     # reviewer's note; payload.blocking=True blocks filing until resolved
    "resolve_note",    # closes a review_note (payload.event_id)
    "question",        # to the client or a colleague (payload.to, payload.text)
    "answer",          # answers a question (payload.event_id); becomes evidence on the question's target
    "verify",          # payload.method in starter_standards.verification_types, payload.evidence[]
    "adjust",          # payload.new_value, payload.reason; original stays in the packet
    "judgment",        # payload.kind (judgment|election|due_diligence|penalty), decision, authority
    "signoff",         # payload.level in LEVELS
    "attach",          # payload.attachment_id or payload.ref (msg-07, call-01 ...)
    "assign",          # payload.to, payload.due
    "undo",            # payload.event_id - appends the reversal, never deletes
    "view_sensitive",  # written by the server when a cleared user unmasks a field
}

# judgment: a judgment call; election: a tax election; due_diligence: e.g. Form 8867;
# penalty: a penalty decision; explanation: why a number moved or why an issue needs no change
JUDGMENT_KINDS = {"judgment", "election", "due_diligence", "penalty", "explanation"}

_STAFF_WORK = {"note", "question", "answer", "verify", "adjust", "judgment", "signoff", "attach", "undo"}
ALLOWED: dict[str, set[str]] = {
    "preparer": _STAFF_WORK,
    "reviewer": _STAFF_WORK | {"review_note", "resolve_note", "assign"},
    "partner": _STAFF_WORK | {"review_note", "resolve_note", "assign"},
    "quality_reviewer": {"note", "review_note", "resolve_note", "attach"},
    "firm_administrator": {"note", "assign"},
    "client": {"answer", "attach"},
}


@dataclass(frozen=True)
class Person:
    id: str
    name: str
    role: str
    credential: str | None = None
    clearance: bool = False
    active_from: str | None = None
    note: str | None = None

    @property
    def is_staff(self) -> bool:
        return self.id.startswith("st-")

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "role": self.role, "credential": self.credential,
                "sensitive_data_clearance": self.clearance, "active_from": self.active_from, "note": self.note,
                "can": sorted(ALLOWED.get(self.role, ()))}


def directory(p: Packet) -> dict[str, Person]:
    out = {s["id"]: Person(s["id"], s["name"], s["role"], s.get("credential"), bool(s.get("sensitive_data_clearance")),
                           s.get("active_from"), s.get("note"))
           for s in p.firm["staff"]}
    for c in p.firm.get("client_users", []):
        out[c["id"]] = Person(c["id"], c["name"], c["role"], clearance=False)
    return out


class Forbidden(Exception):
    """The actor's role does not allow this event."""


class Invalid(Exception):
    """The event is malformed or contradicts the log."""


def check(person: Person, etype: str, payload: dict, *, verification_types: list[str],
          prior_on_target: list[dict], target_event: dict | None) -> None:
    """Raise Forbidden / Invalid; return None when the event may be appended.

    prior_on_target: earlier events on the same target (for the no-self-review rule).
    target_event: the event referenced by payload.event_id (undo, resolve_note, answer), if any.
    """
    if etype not in EVENT_TYPES or etype == "view_sensitive":
        raise Invalid(f"unknown or server-only event type {etype!r}")
    if etype not in ALLOWED.get(person.role, set()):
        raise Forbidden(f"{person.name} ({person.role}) may not {etype}")

    if etype == "verify" and payload.get("method") not in verification_types:
        raise Invalid(f"method must be one of {verification_types}")
    if etype == "adjust":
        if "new_value" not in payload or not str(payload.get("reason", "")).strip():
            raise Invalid("an adjustment needs new_value and a reason")
    if etype == "judgment":
        if payload.get("kind") not in JUDGMENT_KINDS:
            raise Invalid(f"kind must be one of {sorted(JUDGMENT_KINDS)}")
        if not str(payload.get("decision", "")).strip():
            raise Invalid("a judgment records the decision")
        if not str(payload.get("authority", "")).strip():
            raise Invalid("every judgment call records the authority relied on")  # firm rule
    if etype in ("note", "review_note", "question") and not str(payload.get("text", "")).strip():
        raise Invalid(f"{etype} needs text")

    if etype == "signoff":
        level = payload.get("level")
        if level not in LEVELS:
            raise Invalid(f"level must be one of {LEVELS}")
        if person.role in LEVELS and LEVELS.index(level) > LEVELS.index(person.role):
            raise Forbidden(f"{person.role} cannot sign off at {level} level")
        if level != "preparer":
            prepared = [e for e in prior_on_target if e["actor"] == person.id and e["type"] in ("adjust", "verify")
                        and not e.get("undone")]
            if prepared:
                where = sorted({e["target"].split(":", 2)[-1] for e in prepared if e.get("target")})
                raise Forbidden("a person may not review or sign off on work they prepared"
                                + (f" (you worked on {', '.join(where[:3])}{' and more' if len(where) > 3 else ''})"
                                   if where else ""))

    if etype in ("undo", "resolve_note", "answer"):
        if target_event is None:
            raise Invalid("payload.event_id must name an existing event")
        if etype == "undo":
            if target_event["type"] in ("undo", "view_sensitive"):
                raise Invalid(f"cannot undo a {target_event['type']} event")
            if target_event.get("undone"):
                raise Invalid("already undone")
            if target_event["actor"] != person.id and person.role not in ("reviewer", "partner"):
                raise Forbidden("only the author, a reviewer or a partner can undo an event")
        if etype == "resolve_note" and target_event["type"] != "review_note":
            raise Invalid("resolve_note must reference a review_note")
        if etype == "answer" and target_event["type"] != "question":
            raise Invalid("answer must reference a question")
