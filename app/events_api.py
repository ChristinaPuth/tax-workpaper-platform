"""Write surface: the event log behind enforced roles, plus live updates.

The acting user comes from the X-Actor header (the role switcher sets it). Every write is
validated against the index (the target must be a real node) and against people.check().
"""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from . import db
from .live import stream
from .people import Forbidden, Invalid, Person, check

router = APIRouter(prefix="/api")

# events whose target is taken from the event they reference
_INHERITS_TARGET = {"undo", "resolve_note", "answer"}


class NewEvent(BaseModel):
    type: str
    target: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class Batch(BaseModel):
    events: list[NewEvent]


class Seen(BaseModel):
    event_id: int


def _actor(request: Request, x_actor: str | None) -> Person:
    people = request.app.state.people
    if not x_actor or x_actor not in people:
        raise HTTPException(401, "set X-Actor to a staff or client id (see /api/people)")
    return people[x_actor]


def _undone_ids(eng) -> set[int]:
    return {e["payload"].get("event_id") for e in db.read_events(eng, types=["undo"])}


def _flag(evts: list[dict], undone: set[int]) -> list[dict]:
    for e in evts:
        e["undone"] = e["id"] in undone
    return evts


def _validate(request: Request, person: Person, ne: NewEvent) -> dict:
    """Return the row to append, or raise HTTPException."""
    s = request.app.state
    eng = s.db
    ref = None
    if ne.type in _INHERITS_TARGET:
        eid = ne.payload.get("event_id")
        ref = db.get_event(eng, eid) if isinstance(eid, int) else None
        if ref is not None:
            ref["undone"] = ref["id"] in _undone_ids(eng)
        target = ref["target"] if ref else ne.target
    else:
        target = ne.target
        if not target:
            raise HTTPException(422, f"{ne.type} needs a target node id")
    if target and target not in s.store.index.nodes:
        raise HTTPException(422, f"unknown node {target!r}")
    prior = _flag(db.read_events(eng, target=target), _undone_ids(eng)) if target else []
    try:
        check(person, ne.type, ne.payload,
              verification_types=s.store.packet.firm["starter_standards"]["verification_types"],
              prior_on_target=prior, target_event=ref)
    except Forbidden as e:
        raise HTTPException(403, str(e))
    except Invalid as e:
        raise HTTPException(422, str(e))
    return {"actor": person.id, "role": person.role, "type": ne.type, "target": target, "payload": ne.payload}


# ------------------------------------------------------------------------- people
@router.get("/people")
def list_people(request: Request) -> list[dict]:
    return [p.to_dict() for p in request.app.state.people.values()]


# ------------------------------------------------------------------------- events
@router.get("/events")
def list_events(request: Request, target: str | None = None, type: str | None = None,
                after: int = 0, limit: int = 500) -> list[dict]:
    eng = request.app.state.db
    return _flag(db.read_events(eng, target=target, types=type.split(",") if type else None,
                                after=after, limit=limit), _undone_ids(eng))


@router.post("/events", status_code=201)
async def post_event(ne: NewEvent, request: Request, x_actor: str | None = Header(None)) -> dict:
    person = _actor(request, x_actor)
    row = _validate(request, person, ne)
    ev = db.append_event(request.app.state.db, **row)
    ev = db.event_dict(ev)
    request.app.state.broker.publish(ev)
    return ev


@router.post("/events/batch", status_code=201)
async def post_batch(b: Batch, request: Request, x_actor: str | None = Header(None)) -> dict:
    """Bulk action: validated all-or-nothing, appended under one batch_id so one undo can reverse it."""
    person = _actor(request, x_actor)
    rows = [_validate(request, person, ne) for ne in b.events]
    batch_id = uuid.uuid4().hex
    out = []
    for row in rows:
        ev = db.event_dict(db.append_event(request.app.state.db, batch_id=batch_id, **row))
        request.app.state.broker.publish(ev)
        out.append(ev)
    return {"batch_id": batch_id, "events": out}


# ------------------------------------------------------------- what changed since I last looked
@router.get("/me/changes")
def my_changes(request: Request, x_actor: str | None = Header(None)) -> dict:
    person = _actor(request, x_actor)
    eng = request.app.state.db
    since = db.last_seen(eng, person.id)
    evts = [e for e in db.read_events(eng, after=since) if e["actor"] != person.id and e["type"] != "view_sensitive"]
    return {"last_seen_event_id": since, "count": len(evts), "events": _flag(evts, _undone_ids(eng))}


@router.post("/me/seen", status_code=204)
def mark_seen(body: Seen, request: Request, x_actor: str | None = Header(None)) -> None:
    person = _actor(request, x_actor)
    db.mark_seen(request.app.state.db, person.id, body.event_id)


# ------------------------------------------------------------------------- live stream
@router.get("/stream")
async def live(request: Request, after: int = 0, last_event_id: str | None = Header(None)) -> StreamingResponse:
    since = int(last_event_id) if last_event_id and last_event_id.isdigit() else after
    eng = request.app.state.db
    gen = stream(request.app.state.broker, lambda: db.read_events(eng, after=since),
                 is_disconnected=request.is_disconnected)
    return StreamingResponse(gen, media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
