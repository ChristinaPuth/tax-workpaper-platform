"""The working return and the Inbox: the packet plus everything people have done to it.

Both are derived on each request from the packet, the findings and the event log - nothing here is
stored, so they can never drift from the log.
"""
from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Request, Response

from workpaper.working import build

from . import db
from .events_api import _actor
from .due_diligence import checklist as dd_checklist
from .gate import build_gate
from .inbox import AREAS, build_inbox, finding_states
from .logview import LogView
from .area_reports import REPORTS, build_area_report
from .notices import build_pack, render_html
from .replay import key_dates, state_at
from .reports import areas, reconciliations, summary_vs_prior
from .signoff import statuses
from .versions import compare, states, what_ifs

router = APIRouter(prefix="/api")


def working_return(request: Request, version: str | None = None):
    s = request.app.state
    return build(s.store.packet, s.store.index, db.read_events(s.db), version)


@router.get("/working")
def working(request: Request, version: str | None = None, amended: bool = False) -> dict:
    """Engine values with people's adjustments applied: what changed, how (adjusted / propagated / stale),
    the estimated tax effect, and warnings where the estimate stops being trustworthy."""
    s = request.app.state
    return build(s.store.packet, s.store.index, db.read_events(s.db), version, amended=amended).to_dict()


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


# ------------------------------------------------------------------------- versions and what-ifs
@router.get("/compare")
def compare_states(request: Request, a: str = "v2", b: str = "v3") -> dict:
    """Line-by-line difference between two states: v1, v2, v3 or 'working' (latest + adjustments)."""
    s = request.app.state
    events = db.read_events(s.db)
    working = build(s.store.packet, s.store.index, events)
    amended = build(s.store.packet, s.store.index, events, amended=True)
    try:
        out = compare(s.store.packet, working, a, b, amended)
    except ValueError as e:
        raise HTTPException(422, str(e))
    out["states"] = states(s.store.packet)
    return out


@router.get("/what-if")
def what_if(request: Request) -> dict:
    """The engine's what-if alternatives and any election recorded against them."""
    s = request.app.state
    return what_ifs(s.store.packet, LogView(db.read_events(s.db)), s.store.findings)


@router.get("/reports/area/{name}")
def area_report(name: str, request: Request) -> dict:
    """An area report: rentals, deductions, k1 or state."""
    s = request.app.state
    events = db.read_events(s.db)
    working = build(s.store.packet, s.store.index, events)
    try:
        return build_area_report(name, s.store.packet, working, s.store.findings, LogView(events), s.store.verified)
    except KeyError:
        raise HTTPException(404, f"no area report {name!r}; use one of {sorted(REPORTS)}")


@router.get("/replay")
def replay(request: Request, at: str | None = None) -> dict:
    """The file as it stood on a date (YYYY-MM-DD), from the packet's record of the season; plus the key dates."""
    s = request.app.state
    p = s.store.packet
    dates = key_dates(p)
    try:
        out = state_at(p, s.store.findings, at or dates[0]["date"])
    except ValueError:
        raise HTTPException(422, "at is a date: YYYY-MM-DD")
    out["key_dates"] = dates
    return out


# ------------------------------------------------------------------------- notices
@router.get("/notices")
def notices(request: Request) -> list[dict]:
    p = request.app.state.store.packet
    return [n for n in p.raw["tax_agency_records"]["notices"] if n["tax_year"] == p.tax_year]


def _pack(request: Request, notice_id: str) -> dict:
    s = request.app.state
    events = db.read_events(s.db)
    working = build(s.store.packet, s.store.index, events)
    try:
        return build_pack(notice_id, s.store.packet, s.store.index, working, s.store.findings, events,
                          signoff_statuses(request, events, working), s.people)
    except KeyError:
        raise HTTPException(404, f"no notice {notice_id!r}")


@router.get("/notices/{notice_id}/pack")
def notice_pack(notice_id: str, request: Request) -> dict:
    """Everything that supports each item the notice asks about, from the record."""
    return _pack(request, notice_id)


@router.get("/notices/{notice_id}/pack.html")
def notice_pack_html(notice_id: str, request: Request, x_actor: str | None = Header(None)) -> Response:
    """The pack as one page to print or attach. Unmasked only for staff with clearance, and that export is logged."""
    s = request.app.state
    person = _actor(request, x_actor)
    if not person.is_staff:
        raise HTTPException(403, "for the firm only")
    page = render_html(_pack(request, notice_id))
    if person.clearance:
        ev = db.event_dict(db.append_event(s.db, actor=person.id, role=person.role, type="view_sensitive",
                                           target=f"notice:{notice_id}", payload={"fields": ["evidence pack export"]}))
        s.broker.publish(ev)
    else:
        page = s.sensitive.mask_text(page)
    return Response(page, media_type="text/html", headers={
        "Content-Disposition": f'attachment; filename="evidence-pack-{notice_id}.html"'})


@router.get("/due-diligence")
def due_diligence(request: Request) -> dict:
    """The Form 8867 checklist worked out from the file: each dependent's credit and knowledge requirements."""
    s = request.app.state
    return dd_checklist(s.store.packet, s.store.findings, db.read_events(s.db), s.store.packet.latest["version"])
