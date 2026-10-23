"""The working return and the Inbox: the packet plus everything people have done to it.

Both are derived on each request from the packet, the findings and the event log - nothing here is
stored, so they can never drift from the log.
"""
from __future__ import annotations

from fastapi import APIRouter, Header, Request

from workpaper.working import build

from . import db
from .events_api import _actor
from .inbox import AREAS, build_inbox, finding_states

router = APIRouter(prefix="/api")


def working_return(request: Request, version: str | None = None):
    s = request.app.state
    return build(s.store.packet, s.store.index, db.read_events(s.db), version)


@router.get("/working")
def working(request: Request, version: str | None = None) -> dict:
    """Engine values with people's adjustments applied: what changed, how (adjusted / propagated / stale),
    the estimated tax effect, and warnings where the estimate stops being trustworthy."""
    return working_return(request, version).to_dict()


@router.get("/inbox")
def inbox(request: Request, x_actor: str | None = Header(None)) -> dict:
    s = request.app.state
    person = _actor(request, x_actor)
    out = build_inbox(person, packet=s.store.packet, findings=s.store.findings, events=db.read_events(s.db),
                      working=working_return(request), people=s.people)
    out["areas"] = AREAS
    return out


@router.get("/finding-states")
def finding_state_map(request: Request) -> dict:
    """Each finding's state from the log: open | adjusted (changed, waiting for review) | reviewed.
    The same rule the Inbox uses, so the return view and the Inbox never disagree."""
    s = request.app.state
    return finding_states(s.store.findings, db.read_events(s.db), s.store.packet.latest["version"])
