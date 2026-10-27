"""Filing: only a ready return is filed, by the partner; the filed return is frozen and changes go to one
amendment layer."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from workpaper.packet import packet_path

PRIYA, DANIEL, HELEN, NGOZI, ERIK = "st-01", "st-02", "st-03", "cu-01", "cu-02"
RETURN = "ver:v3"


@pytest.fixture()
def c(tmp_path):
    with TestClient(create_app(str(packet_path()), f"sqlite:///{tmp_path / 'f.db'}")) as client:
        yield client


def post(c, who, type, target=None, layer="return", **payload):
    return c.post("/api/events", headers={"X-Actor": who},
                  json={"type": type, "target": target, "payload": payload, "layer": layer})


def make_ready(c):
    """Everything the twelve steps ask for, the quick way: decide every open issue, then sign and approve."""
    states = c.get("/api/finding-states").json()
    events = [{"type": "judgment", "target": f["nodes"][0], "payload": {
        "kind": "explanation", "decision": "Reviewed with the evidence", "authority": "Documents in the file",
        "finding_id": f["id"]}} for f in c.get("/api/findings").json()
        if f["severity"] != "info" and states[f["id"]]["state"] == "open"]
    assert c.post("/api/events/batch", headers={"X-Actor": PRIYA}, json={"events": events}).status_code == 201
    assert post(c, PRIYA, "verify", "doc:D06", method="agreed_to_prior_year").status_code == 201
    items = c.get("/api/due-diligence", headers={"X-Actor": PRIYA}).json()["items"]
    assert post(c, PRIYA, "judgment", "line:v3:F8867.status", kind="due_diligence", decision="Form 8867 completed",
                authority="IRC 6695(g)", checklist={i["id"]: True for i in items}).status_code == 201
    for area in c.get("/api/coverage", headers={"X-Actor": PRIYA}).json()["left"]:
        assert post(c, PRIYA, "judgment", RETURN, kind="area", area=area, applies=True,
                    decision="Considered", authority="Workpapers for the area").status_code == 201
    assert post(c, DANIEL, "signoff", RETURN, level="reviewer").status_code == 201
    assert post(c, HELEN, "signoff", RETURN, level="partner").status_code == 201
    for who, name, pin in ((NGOZI, "Ngozi Okafor", "41207"), (ERIK, "Erik Lindqvist", "88310")):
        assert post(c, who, "signoff", RETURN, level="client", typed_name=name, pin=pin, consent=True).status_code == 201
    gate = c.get("/api/gate").json()
    assert gate["ready"], (gate["summary"], gate["blockers"])


def test_only_a_ready_return_is_filed_and_only_by_the_partner(c):
    assert post(c, HELEN, "file", RETURN).status_code == 409                 # not ready
    make_ready(c)
    assert post(c, PRIYA, "file", RETURN).status_code == 403                 # preparers do not file
    r = post(c, HELEN, "file", RETURN)
    assert r.status_code == 201 and r.json()["payload"]["hash"]               # what was filed is kept
    assert c.get("/api/gate").json()["filed"]["by_name"] == "Helen Strand"
    assert post(c, HELEN, "file", RETURN).status_code == 409                 # once


def test_the_filed_return_is_frozen_and_changes_go_to_the_amendment(c):
    assert post(c, PRIYA, "adjust", "line:v3:SchA.8a", layer="amendment", new_value=1, reason="x").status_code == 409
    make_ready(c)
    filed = post(c, HELEN, "file", RETURN).json()
    assert post(c, PRIYA, "adjust", "line:v3:SchA.8a", new_value=19697, reason="payoff interest").status_code == 409
    assert post(c, PRIYA, "note", "line:v3:SchA.8a", text="still fine to comment").status_code == 201
    assert post(c, HELEN, "undo", event_id=filed["id"]).status_code == 409                # cannot unfile
    amend = post(c, PRIYA, "adjust", "line:v3:SchA.8a", layer="amendment", new_value=19697,
                 reason="Payoff interest counted twice - found after filing")
    assert amend.status_code == 201
    as_filed = c.get("/api/working").json()["lines"]
    amended = c.get("/api/working", params={"amended": "true"}).json()["lines"]
    assert "SchA.8a" not in as_filed and amended["SchA.8a"]["value"] == 19697
    diff = c.get("/api/compare", params={"a": "working", "b": "amended"}).json()
    assert {r["key"] for r in diff["lines"] if r["change"] == "changed"} >= {"SchA.8a", "SchA.17"}
    assert post(c, PRIYA, "undo", event_id=amend.json()["id"], layer="amendment").status_code == 201


def test_amendment_changes_do_not_reopen_what_was_signed_and_filed(c):
    make_ready(c)
    assert post(c, HELEN, "file", RETURN, jurisdictions=["federal", "california"]).status_code == 201
    assert post(c, PRIYA, "adjust", "line:v3:SchB.1.6", layer="amendment", new_value=1870, reason="FTB rounding").status_code == 201
    held = {(s["level"], s["actor"]): s["valid"] for s in c.get("/api/signoffs").json() if s["target"] == RETURN}
    assert held[("partner", HELEN)] and held[("client", NGOZI)] and held[("client", ERIK)]
