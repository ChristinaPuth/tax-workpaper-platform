"""Sensitive data: masked in every API response, shown only on request and logged.

Firm rule (starter_standards): staff without sensitive-data clearance see SSNs, bank and account numbers and IP
PINs masked; every unmasked view is logged. Here every staff response is masked; staff with clearance can reveal
one value, page or person at a time, which writes a view_sensitive event (who, what, when). Staff without
clearance cannot reveal. Clients are the taxpayers: they see their own numbers.

Clients also do not see the firm's internal work: issue lists, internal reports, the event log and live stream,
search, version comparison and what-ifs are refused, and issue fields are emptied from what they can read.

What counts as sensitive is read from the packet's own structure (household SSNs and IP PINs, the refund
account, account-number fields) plus any SSN-shaped string - so a mistyped SSN is masked too.
"""
from __future__ import annotations

import json
import re

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel

from . import db

SSN = re.compile(r"\b\d{3}-\d{2}-(\d{4})\b")
SIGNATURE_PIN = re.compile(r"(PIN\s*)\d{5}\b")
MASK = "•"


class Sensitive:
    def __init__(self, packet):
        hh = packet.household
        self.pins = {str(p["ip_pin"]) for p in hh["people"] if p.get("ip_pin")}
        self.pins |= {str(e["value"]) for e in packet.extracted_values if e["field"].endswith("ip_pin")}
        bank = hh.get("bank_account_for_refund_or_payment") or {}
        self.accounts = {str(bank[k]) for k in ("routing", "account") if bank.get(k)}
        self.accounts |= {str(e["text_as_read"]) for e in packet.extracted_values
                          if e["field"] in ("account_number", "routing_number", "iban") and e.get("text_as_read")}
        self._accounts = [re.compile(re.escape(a).replace(r"\ ", r"\s?")) for a in sorted(self.accounts, key=len, reverse=True)]
        self._pins = [re.compile(rf"\b{re.escape(p)}\b") for p in self.pins]

    def mask_text(self, s: str) -> str:
        s = SSN.sub(lambda m: f"{MASK * 3}-{MASK * 2}-{m.group(1)}", s)
        for rx in self._accounts:
            s = rx.sub(lambda m: _keep_last4(m.group(0)), s)
        for rx in self._pins:
            s = rx.sub(MASK * 6, s)
        return SIGNATURE_PIN.sub(lambda m: m.group(1) + MASK * 5, s)

    def mask(self, obj):
        if isinstance(obj, str):
            return self.mask_text(obj) if any(ch.isdigit() for ch in obj) else obj
        if isinstance(obj, bool) or obj is None:
            return obj
        if isinstance(obj, (int, float)):
            text = str(int(obj)) if float(obj).is_integer() else str(obj)
            if text in self.accounts:
                return _keep_last4(text)
            return MASK * 6 if text in self.pins else obj
        if isinstance(obj, list):
            return [self.mask(x) for x in obj]
        if isinstance(obj, dict):
            return {k: self.mask(v) for k, v in obj.items()}
        return obj


def _keep_last4(text: str) -> str:
    """Same length as the original (pages highlight values by character position): every letter or digit but the
    last four becomes a dot; spaces stay."""
    alnum = [i for i, ch in enumerate(text) if ch.isalnum()]
    hide = set(alnum[:-4])
    return "".join(MASK if i in hide else ch for i, ch in enumerate(text))


# ------------------------------------------------------------------ what clients may read
CLIENT_BLOCKED = ("/api/findings", "/api/finding-states", "/api/reports/areas", "/api/reports/reconciliations",
                  "/api/reports/area/", "/api/search", "/api/compare", "/api/what-if", "/api/events", "/api/stream",
                  "/api/working", "/api/trace", "/api/impact", "/api/me/changes", "/api/replay", "/api/notices",
                  "/api/due-diligence", "/api/coverage", "/api/assignments", "/api/links", "/api/efile")
CLIENT_INTERNAL_KEYS = {"findings": [], "finding_refs": [], "finding_id": None, "finding_state": None,
                        "blockers": [], "findings_total": None, "findings_by_severity": {}}


def strip_internal(obj):
    if isinstance(obj, list):
        return [strip_internal(x) for x in obj]
    if isinstance(obj, dict):
        return {k: (CLIENT_INTERNAL_KEYS[k] if k in CLIENT_INTERNAL_KEYS else strip_internal(v)) for k, v in obj.items()}
    return obj


class SensitiveDataMiddleware:
    """Masks every JSON response under /api for staff (and anonymous callers); for clients, refuses the firm's
    internal endpoints and empties issue fields. The reveal endpoint is the one way to see a value unmasked."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        path = scope.get("path", "")
        if scope["type"] != "http" or not path.startswith("/api/") or path.startswith("/api/sensitive/"):
            return await self.app(scope, receive, send)
        actor = dict(scope.get("headers") or []).get(b"x-actor", b"").decode()
        client = actor.startswith("cu-")
        if client and scope["method"] == "GET" and path.startswith(CLIENT_BLOCKED):
            body = json.dumps({"detail": "not available in the client portal"}).encode()
            await send({"type": "http.response.start", "status": 403,
                        "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())]})
            return await send({"type": "http.response.body", "body": body})
        if path.startswith("/api/stream"):
            return await self.app(scope, receive, send)

        start: dict = {}
        chunks: list[bytes] = []

        async def capture(message):
            if message["type"] == "http.response.start":
                start.update(message)
                return
            chunks.append(message.get("body", b""))
            if message.get("more_body"):
                return
            headers = [(k, v) for k, v in start.get("headers", []) if k.lower() != b"content-length"]
            body = b"".join(chunks)
            if dict(headers).get(b"content-type", b"").startswith(b"application/json") and body:
                data = json.loads(body)
                data = strip_internal(data) if client else scope["app"].state.sensitive.mask(data)
                body = json.dumps(data, ensure_ascii=False).encode()
            headers.append((b"content-length", str(len(body)).encode()))
            await send({**start, "headers": headers})
            await send({"type": "http.response.body", "body": body})

        await self.app(scope, receive, capture)


# ------------------------------------------------------------------ reveal, logged
router = APIRouter(prefix="/api/sensitive")


class Reveal(BaseModel):
    target: str  # ev:..., page:D06#1, person:theo


@router.post("/reveal")
def reveal(body: Reveal, request: Request, x_actor: str | None = Header(None)) -> dict:
    """The unmasked content of one value, page or person - for staff with clearance, and logged."""
    from .events_api import _actor  # here, not at import time: events_api builds on the app modules
    person = _actor(request, x_actor)
    s = request.app.state
    p = s.store.packet
    if not person.is_staff:
        raise HTTPException(403, "clients see their own data without revealing it")
    if not person.clearance:
        raise HTTPException(403, f"{person.name} has no sensitive-data clearance; ask a cleared colleague")
    kind, _, rest = body.target.partition(":")
    if kind == "ev" and rest in p.ev:
        e = p.ev[rest]
        content = {"text_as_read": e["text_as_read"], "value": e["value"]}
    elif kind == "page":
        doc, _, page = rest.partition("#")
        pg = next((x for x in p.doc.get(doc, {}).get("pages", []) if str(x["page"]) == page), None)
        if pg is None:
            raise HTTPException(404, f"no page {rest!r}")
        content = {"printed_content": pg["printed_content"]}
    elif kind == "person":
        who = next((x for x in p.household["people"] if x["id"] == rest), None)
        if who is None:
            raise HTTPException(404, f"no person {rest!r}")
        content = {k: who.get(k) for k in ("ssn", "ip_pin") if who.get(k)}
    else:
        raise HTTPException(404, f"nothing to reveal at {body.target!r}")
    ev = db.event_dict(db.append_event(s.db, actor=person.id, role=person.role, type="view_sensitive",
                                       target=body.target, payload={"fields": sorted(content)}))
    s.broker.publish(ev)
    return {"target": body.target, "content": content, "logged": ev["id"]}


@router.get("/log")
def view_log(request: Request, x_actor: str | None = Header(None)) -> list[dict]:
    """Every unmasked view: who saw what, when. For the firm (not clients)."""
    from .events_api import _actor
    person = _actor(request, x_actor)
    if not person.is_staff:
        raise HTTPException(403, "for the firm only")
    return db.read_events(request.app.state.db, types=["view_sensitive"])
