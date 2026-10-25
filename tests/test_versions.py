"""Version comparison and what-if alternatives."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from workpaper.packet import Packet, packet_path

PRIYA, NGOZI = "st-01", "cu-01"


@pytest.fixture()
def c(tmp_path):
    with TestClient(create_app(str(packet_path()), f"sqlite:///{tmp_path / 'v.db'}")) as client:
        yield client


@pytest.mark.parametrize("a,b,i", [("v1", "v2", 1), ("v2", "v3", 2)])
def test_diff_agrees_with_the_packets_own_change_list(c, a, b, i):
    p = Packet.load(packet_path())
    mine = {(r["key"], r["change"]) for r in c.get("/api/compare", params={"a": a, "b": b}).json()["lines"]}
    theirs = {(x["key"], x["change"]) for x in p.versions[i]["changes_from_previous"]}
    assert mine == theirs


def test_v2_to_v3_says_why_and_which_documents(c):
    d = c.get("/api/compare", params={"a": "v2", "b": "v3"}).json()
    assert "Ridgeline K-1" in d["trigger"]
    assert "D73" in d["documents"]["added"]
    agi = next(s for s in d["summary"] if s["key"] == "agi")
    assert (agi["old"], agi["new"], agi["delta"]) == (429820, 445590, 15770)
    assert c.get("/api/compare", params={"a": "v2", "b": "v9"}).status_code == 422


def test_working_shows_adjustments_and_what_needs_a_recompute(c):
    assert c.get("/api/compare", params={"a": "v3", "b": "working"}).json()["lines"] == []
    c.post("/api/events", headers={"X-Actor": PRIYA},
           json={"type": "adjust", "target": "line:v3:Sch1.17", "payload": {"new_value": 0, "reason": "F-016"}})
    d = c.get("/api/compare", params={"a": "v3", "b": "working"}).json()
    rows = {r["key"]: r for r in d["lines"]}
    assert rows["Sch1.17"]["change"] == "changed" and rows["Sch1.17"]["delta"] == -14400
    assert rows["F1040.11"]["new"] == 459990
    assert rows["F1040.16"]["change"] == "needs recompute"          # tax is a formula: only a rerun updates it
    assert d["adjustments"][0]["key"] == "Sch1.17"


def test_what_ifs_are_the_engines_numbers(c):
    alts = {a["id"]: a for a in c.get("/api/what-if").json()["alternatives"]}
    assert (alts["equipment_section179"]["federal"], alts["equipment_section179"]["california"]) == (0, -1050)
    assert alts["hvac_improvement"]["findings"] == ["F-017"]
    assert alts["penalty_annualized"]["lines"] == []


def test_an_election_needs_authority_and_can_be_withdrawn(c):
    post = lambda who, payload: c.post("/api/events", headers={"X-Actor": who},
                                      json={"type": "judgment", "target": "ver:v3", "payload": payload})
    base = {"kind": "election", "decision": "Elect section 179", "what_if": "equipment_section179"}
    assert post(PRIYA, {**base, "authority": ""}).status_code == 422
    assert post(NGOZI, {**base, "authority": "IRC 179"}).status_code == 403
    ev = post(PRIYA, {**base, "authority": "IRC 179; client agreed 2026-06-24"}).json()
    alt = next(a for a in c.get("/api/what-if").json()["alternatives"] if a["id"] == "equipment_section179")
    assert alt["election"]["authority"].startswith("IRC 179")
    c.post("/api/events", headers={"X-Actor": PRIYA}, json={"type": "undo", "payload": {"event_id": ev["id"]}})
    alt = next(a for a in c.get("/api/what-if").json()["alternatives"] if a["id"] == "equipment_section179")
    assert alt["election"] is None
