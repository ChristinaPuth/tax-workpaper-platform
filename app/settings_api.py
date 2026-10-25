"""A person's own settings - simple or expert view, glossary hints, the quick start - and the quick start itself.

Defaults come from the firm's staff records: someone without a credential who joined in the last six months
(as of the latest return version) starts in the simple view with the quick start open; everyone else starts
in the expert view. Each person can change this; what they choose is stored per person, outside the event log
(it is not work on the return).

Quick start steps are ticked from what the person actually did - their own events, and the pages they opened -
never by hand.
"""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel

from . import db
from .events_api import _actor
from .people import ALLOWED, Person

router = APIRouter(prefix="/api")

NEW_STAFF_DAYS = 183
VISITS = {"inbox", "trace", "search", "filing", "reports"}


class SettingsPatch(BaseModel):
    mode: str | None = None              # simple | expert
    glossary: bool | None = None         # underline terms that have a plain explanation
    quick_start: bool | None = None      # open the quick start when this person starts
    visited: list[str] | None = None     # quick start pages this person has opened


def as_of(packet) -> date:
    """The firm's 'today' in the packet: when the latest return version was computed."""
    return date.fromisoformat(packet.latest["computed_at"][:10])


def defaults(person: Person, packet) -> tuple[dict, str]:
    if not person.is_staff:
        return {"mode": "simple", "glossary": True, "quick_start": False}, "Client view: plain language."
    if person.active_from and not person.credential:
        days = (as_of(packet) - date.fromisoformat(person.active_from)).days
        if days <= NEW_STAFF_DAYS:
            return ({"mode": "simple", "glossary": True, "quick_start": True},
                    f"New to the firm (started {person.active_from}): simple view and the quick start are on.")
    return ({"mode": "expert", "glossary": False, "quick_start": False},
            "Experienced staff: expert view (technical ids shown, explanations on hover).")


def quick_start(person: Person, events: list[dict], visited: set[str]) -> list[dict]:
    can = ALLOWED.get(person.role, set())
    mine = {e["type"] for e in events if e["actor"] == person.id}
    steps = [
        ("inbox", "Start in your Inbox",
         "Everything that needs you, worst first. Each card says what happened, why it matters and what to do.",
         "/inbox", "inbox" in visited),
        ("trace", "Follow a number to the page it came from",
         "Open Schedule C line 1 and click a source under 'How it was built' - the document opens with the value "
         "highlighted.", "/return?v=v3&form=SchC&line=SchC.1", "trace" in visited),
        ("search", "Find anything by amount",
         "Press ⌘K and type 12,400: the 1099-K, the books and the issue come up together.", None, "search" in visited),
    ]
    if "adjust" in can:
        steps.append(("fix", "Correct a number - always with a reason",
                      "Open an issue that proposes a correction (e.g. 'SchC.1 counts the 1099-K twice'), use the "
                      "proposed value and say why. A reviewer then signs it off.",
                      "/findings?id=F-015", bool(mine & {"adjust", "judgment"})))
    if person.role in ("reviewer", "partner"):
        steps.append(("review", "Review a change and sign off",
                      "Changes by others wait in your Inbox. Check the evidence, then sign off - you cannot sign "
                      "your own work.", "/inbox", "signoff" in mine))
    if "question" in can:
        steps.append(("ask", "Ask the client or a colleague",
                      "Use 'Ask someone' on any line or document. The answer lands on that line as evidence.",
                      None, "question" in mine))
    steps.append(("filing", "See what still blocks filing",
                  "The Filing page works out the firm's twelve steps from the file - nothing is ticked by hand.",
                  "/filing", "filing" in visited))
    return [{"id": i, "title": t, "body": b, "href": h, "done": d} for i, t, b, h, d in steps]


def _view(request: Request, person: Person) -> dict:
    s = request.app.state
    base, reason = defaults(person, s.store.packet)
    mine = db.get_settings(s.db, person.id)
    settings = {**base, **{k: v for k, v in mine.items() if k in base}}
    steps = quick_start(person, db.read_events(s.db, types=["adjust", "judgment", "signoff", "question"]),
                        set(mine.get("visited", [])))
    return {"settings": settings, "defaults": base, "reason": reason, "changed": sorted(k for k in mine if k in base),
            "quick_start": steps if person.is_staff else [], "as_of": as_of(s.store.packet).isoformat()}


@router.get("/me/settings")
def my_settings(request: Request, x_actor: str | None = Header(None)) -> dict:
    return _view(request, _actor(request, x_actor))


@router.patch("/me/settings")
def update_settings(body: SettingsPatch, request: Request, x_actor: str | None = Header(None)) -> dict:
    person = _actor(request, x_actor)
    eng = request.app.state.db
    mine = db.get_settings(eng, person.id)
    if body.mode is not None:
        if body.mode not in ("simple", "expert"):
            raise HTTPException(422, "mode is simple or expert")
        mine["mode"] = body.mode
    if body.glossary is not None:
        mine["glossary"] = body.glossary
    if body.quick_start is not None:
        mine["quick_start"] = body.quick_start
    if body.visited:
        unknown = set(body.visited) - VISITS
        if unknown:
            raise HTTPException(422, f"unknown quick start page(s): {sorted(unknown)}")
        mine["visited"] = sorted(set(mine.get("visited", [])) | set(body.visited))
    db.put_settings(eng, person.id, mine)
    return _view(request, person)


@router.delete("/me/settings", status_code=200)
def reset_settings(request: Request, x_actor: str | None = Header(None)) -> dict:
    """Back to the defaults for this person (the quick start progress is kept)."""
    person = _actor(request, x_actor)
    eng = request.app.state.db
    mine = db.get_settings(eng, person.id)
    db.put_settings(eng, person.id, {k: v for k, v in mine.items() if k == "visited"})
    return _view(request, person)
