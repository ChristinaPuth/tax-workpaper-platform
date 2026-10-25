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

from workpaper.working import build

from . import db
from .live import stream
from .logview import LogView
from .people import Forbidden, Invalid, Person, check
from .signoff import scope_of, take

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
    if ne.type == "adjust":
        latest = s.store.packet.latest["version"]
        if not (target.startswith(f"line:{latest}:") or target.startswith("ev:")):
            raise HTTPException(422, f"adjust a line of the current version ({latest}) or an extracted value")
    if ne.type == "question":
        to = ne.payload.get("to")
        if to not in s.people or to == person.id:
            raise HTTPException(422, "a question is addressed to someone else (payload.to, see /api/people)")
    if ne.type == "judgment" and ne.payload.get("finding_id"):
        if not any(f.id == ne.payload["finding_id"] for f in s.store.findings):
            raise HTTPException(422, f"no finding {ne.payload['finding_id']!r}")
    undone = _undone_ids(eng)
    if ne.type == "signoff":
        # no self-review across everything the sign-off covers, not just the node itself
        scope = set(scope_of(s.store.packet, s.store.index, target, s.store.packet.latest["version"]))
        prior = _flag([e for e in db.read_events(eng) if e.get("target") in scope], undone)
    else:
        prior = _flag(db.read_events(eng, target=target), undone) if target else []
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


def _append(request: Request, row: dict, batch_id: str | None = None, cache: dict | None = None) -> dict:
    """Append one validated event; a sign-off also stores the snapshot it will be checked against.
    cache: shared across a batch - sign-offs do not change any number, so one working return serves all."""
    s = request.app.state
    snapshot = None
    if row["type"] == "signoff":
        cache = cache if cache is not None else {}
        if "working" not in cache:
            events = db.read_events(s.db)
            cache["working"] = build(s.store.packet, s.store.index, events)
            cache["log"] = LogView(events)
        scope, content, digest = take(s.store.packet, s.store.index, cache["working"], cache["log"], row["target"])
        row["payload"] = {**row["payload"], "hash": digest, "scope_size": len(scope)}
        snapshot = (scope, content, digest)
    ev = db.event_dict(db.append_event(s.db, batch_id=batch_id, **row))
    if snapshot:
        db.put_snapshot(s.db, kind="signoff", event_id=ev["id"], scope=snapshot[0], hash=snapshot[2],
                        content=snapshot[1])
    s.broker.publish(ev)
    return ev


@router.post("/events", status_code=201)
async def post_event(ne: NewEvent, request: Request, x_actor: str | None = Header(None)) -> dict:
    person = _actor(request, x_actor)
    return _append(request, _validate(request, person, ne))


@router.post("/events/batch", status_code=201)
async def post_batch(b: Batch, request: Request, x_actor: str | None = Header(None)) -> dict:
    """Bulk action: validated all-or-nothing, appended under one batch_id so one undo can reverse it."""
    person = _actor(request, x_actor)
    rows, refused = [], []
    for ne in b.events:
        try:
            rows.append(_validate(request, person, ne))
        except HTTPException as e:
            refused.append((ne.target or "", e))
    if refused:  # nothing is appended; say which items stopped the batch, so they can be done on their own
        names = ["the whole return" if t.startswith("ver:") else t.split(":", 2)[-1] for t, _ in refused]
        status = max(e.status_code for _, e in refused)
        raise HTTPException(status, f"{len(refused)} of {len(b.events)} refused ({', '.join(names[:5])}"
                                    f"{' and more' if len(names) > 5 else ''}): {refused[0][1].detail}")
    batch_id = uuid.uuid4().hex
    numbers_change = any(r["type"] in ("adjust", "undo", "judgment", "attach") for r in rows)
    cache = None if numbers_change else {}
    out = [_append(request, row, batch_id, cache) for row in rows]
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
