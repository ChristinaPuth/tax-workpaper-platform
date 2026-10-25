"""CPA reports: the return against last year, area cards, and reconciliations."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.inbox import area_of
from app.main import create_app
from workpaper.packet import packet_path

PRIYA, DANIEL = "st-01", "st-02"


@pytest.fixture()
def c(tmp_path):
    with TestClient(create_app(str(packet_path()), f"sqlite:///{tmp_path / 'r.db'}")) as client:
        yield client


def rows(c, section):
    body = c.get("/api/reports/summary").json()
    return {r["key"]: r for s in body["sections"] if s["key"] == section for r in s["rows"]}


def test_summary_compares_with_last_year_and_links_the_variance_issue(c):
    fed = rows(c, "federal")
    agi = fed["F1040.11"]
    assert (agi["prior"], agi["working"], agi["change"]) == (228409, 445590, 217181)
    assert agi["over_threshold"] and agi["finding_id"] and agi["finding_state"] == "open"
    assert agi["prior_source"] == "ev-0010"                       # the 2024 return as filed (D06)
    assert not fed["F1040.3b"]["over_threshold"]                  # +820: under the 1,000 floor
    assert fed["F1040.37"]["prior"] == -393 and fed["F1040.37"]["working"] == 4220   # refund vs balance due


def test_summary_shows_adjusted_values(c):
    c.post("/api/events", headers={"X-Actor": PRIYA},
           json={"type": "adjust", "target": "line:v3:Sch1.17", "payload": {"new_value": 0, "reason": "F-016"}})
    agi = rows(c, "federal")["F1040.11"]
    assert agi["engine"] == 445590 and agi["working"] == 459990 and agi["adjusted"]


def test_california_rows_are_flagged_as_not_like_for_like(c):
    body = c.get("/api/reports/summary").json()
    ca = next(s for s in body["sections"] if s["key"] == "california")
    assert "540NR" in ca["note"]
    assert {r["key"]: r for r in ca["rows"]}["F540NR.97"]["working"] == -8256


def test_form_1040_lines_land_in_their_own_area():
    p = __import__("workpaper.packet", fromlist=["Packet"]).Packet.load(packet_path())
    area = lambda k: area_of([f"line:v3:{k}"], p)
    assert area("F1040.3b") == "investments"                       # dividends, not payments
    assert area("F1040.11") == "totals"                            # AGI, not wages
    assert area("F1040.1a") == "wages" and area("F1040.26") == "payments" and area("Sch1.17") == "business"


def test_area_cards_count_open_issues_and_follow_the_work(c):
    cards = {a["key"]: a for a in c.get("/api/reports/areas").json()}
    assert cards["investments"]["open"]["error"] == 6 and cards["investments"]["status"] == "errors"
    assert cards["passthroughs"]["status"] == "clear"
    assert cards["investments"]["budget_hours"] == 4.0
    f = c.get("/api/findings/F-012").json()
    c.post("/api/events", headers={"X-Actor": PRIYA}, json={"type": "adjust", "target": "line:v3:F8949.B.N1",
                                                            "payload": {"new_value": 140, "reason": "F-012"}})
    after = {a["key"]: a for a in c.get("/api/reports/areas").json()}["investments"]
    assert after["open"]["error"] == 5 and after["handled"] == 1 and after["changes"] == 1
    # applying the proposed correction estimates the same effect the issue showed (incl. the California-source rate)
    assert after["change_effect"] == {"federal": f["federal_effect"], "california": f["california_effect"]}


def test_reconciliations_list_what_agrees_and_what_does_not(c):
    groups = {g["title"]: g for g in c.get("/api/reports/reconciliations").json()}
    pay = groups["Payments agree with the agencies"]
    assert {d["finding_id"] for d in pay["differ"]} == {"F-032", "F-033"} and pay["agree"]
    carry = groups["Carryovers agree with last year"]
    assert len(carry["agree"]) == 4 and not carry["differ"]
    assert all(a["engine"] is not None for g in groups.values() for a in g["agree"])
