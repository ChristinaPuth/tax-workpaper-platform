"""The working return and the Inbox: the packet plus everything people have done to it.

Both are derived on each request from the packet, the findings and the event log - nothing here is
stored, so they can never drift from the log.
"""
from __future__ import annotations

from fastapi import APIRouter, Header, Request

from workpaper.working import build

from . import db
from .events_api import _actor
from .gate import build_gate
from .inbox import AREAS, build_inbox, finding_states
from .logview import LogView
from .reports import areas, reconciliations, summary_vs_prior
from .signoff import statuses

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
    events = db.read_events(s.db)
    working = build(s.store.packet, s.store.index, events)
    out = build_inbox(person, packet=s.store.packet, findings=s.store.findings, events=events, working=working,
                      people=s.people, signoffs=signoff_statuses(request, events, working))
    out["areas"] = AREAS
    return out


@router.get("/finding-states")
def finding_state_map(request: Request) -> dict:
    """Each finding's state from the log: open | adjusted (changed, waiting for review) | reviewed.
    The same rule the Inbox uses, so the return view and the Inbox never disagree."""
    s = request.app.state
    return finding_states(s.store.findings, db.read_events(s.db), s.store.packet.latest["version"])


def signoff_statuses(request: Request, events: list[dict] | None = None, working=None) -> list[dict]:
    s = request.app.state
    events = events if events is not None else db.read_events(s.db)
    working = working or build(s.store.packet, s.store.index, events)
    return statuses(s.store.packet, s.store.index, working, events, db.snapshots_for(s.db, "signoff"))


@router.get("/signoffs")
def signoffs(request: Request, target: str | None = None) -> list[dict]:
    """Every live sign-off: valid, or reopened with what changed since it was signed."""
    out = signoff_statuses(request)
    return [s for s in out if target is None or s["target"] == target]


@router.get("/gate")
def gate(request: Request) -> dict:
    """The twelve required steps and everything else that blocks filing, derived from the log."""
    s = request.app.state
    events = db.read_events(s.db)
    working = build(s.store.packet, s.store.index, events)
    return build_gate(packet=s.store.packet, index=s.store.index, findings=s.store.findings, events=events,
                      working=working, signoffs=signoff_statuses(request, events, working), people=s.people)


# ------------------------------------------------------------------------- reports
@router.get("/reports/summary")
def report_summary(request: Request) -> dict:
    """The return against last year's: 2024, 2025 engine, 2025 with adjustments, change, and the variance issue."""
    s = request.app.state
    events = db.read_events(s.db)
    working = build(s.store.packet, s.store.index, events)
    return summary_vs_prior(s.store.packet, working, s.store.findings, LogView(events))


@router.get("/reports/areas")
def report_areas(request: Request) -> list[dict]:
    """One card per area: open issues and their effect, what was handled or reviewed, changes, documents, budget."""
    s = request.app.state
    events = db.read_events(s.db)
    working = build(s.store.packet, s.store.index, events)
    return areas(s.store.packet, working, s.store.findings, LogView(events))


@router.get("/reports/reconciliations")
def report_reconciliations(request: Request) -> list[dict]:
    """Figures that should agree: the independent recomputations that agreed and the issues where they do not."""
    s = request.app.state
    return reconciliations(s.store.packet, s.store.verified, s.store.findings, LogView(db.read_events(s.db)),
                           s.store.packet.latest["version"])
