"""Area reports: rentals, deductions and limits, K-1s, state split."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from workpaper.packet import packet_path

PRIYA = "st-01"


@pytest.fixture()
def c(tmp_path):
    with TestClient(create_app(str(packet_path()), f"sqlite:///{tmp_path / 'a.db'}")) as client:
        yield client


def report(c, name):
    r = c.get(f"/api/reports/area/{name}")
    assert r.status_code == 200
    return r.json()


def block(rep, title_start):
    return next(b for b in rep["blocks"] if b["title"].startswith(title_start))


def checks(rep):
    return {x["label"]: x for b in rep["blocks"] if b["type"] == "checks" for x in b["rows"]}


def test_every_recomputed_limit_agrees_with_the_engine(c):
    for name in ("rentals", "deductions", "state"):
        assert all(x["agrees"] for x in checks(report(c, name)).values()), name


def test_rentals_show_each_property_the_passive_release_and_the_hvac_issue(c):
    rep = report(c, "rentals")
    a = block(rep, "Property A")
    assert "California-source" in a["note"]
    repairs = next(r for r in a["rows"] if r["key"] == "SchE.14A")
    assert repairs["engine"] == 13300 and "F-017" in {i["id"] for i in repairs["issues"]}
    assert "16,150" in block(rep, "Passive activity losses")["note"]
    assert "Form 4797" in block(rep, "Property B")["note"]


def test_deduction_limits_are_spelled_out(c):
    rep = report(c, "deductions")
    salt = checks(rep)["SALT deduction after the cap"]
    assert (salt["engine"], salt["limit"]) == (40000, "40,000") and "1,290" in salt["note"]
    assert checks(rep)["Child tax credit phase-out"]["engine"] == 2300
    assert "54,206" in block(rep, "Itemized or standard")["note"]


def test_k1_values_are_traced_to_the_lines_they_land_on(c):
    rep = report(c, "k1")
    ridgeline = next(b for b in rep["blocks"] if b["type"] == "k1" and b["document"] == "D37")
    lands = {r["field"]: [x["key"] for x in r["lines"]] for r in ridgeline["rows"]}
    assert lands["box2"] == ["SchE.28B"] and lands["box5"] == ["SchB.1.8"]
    assert "first used in v3" in ridgeline["note"]
    supplement = next(b for b in rep["blocks"] if b["type"] == "k1" and b["document"] == "D38")
    assert "1,848" in supplement["note"]


def test_state_split_table_and_the_wage_issue(c):
    rep = report(c, "state")
    table = next(b for b in rep["blocks"] if b["type"] == "table")
    rows = {r["line"]: r for r in table["rows"]}
    assert "A" not in rows                                            # not a column of Schedule CA
    assert rows["1"]["ca_share"] == 1.0 and rows["1"]["cols"]["E"]["issues"] == ["F-022"]
    assert rows["17"]["ca_share"] is None                             # losses: a share means nothing
    assert "F-022" in rep["issues"]


def test_reports_follow_adjustments(c):
    c.post("/api/events", headers={"X-Actor": PRIYA}, json={"type": "adjust", "target": "line:v3:SchA.8a",
                                                            "payload": {"new_value": 19697, "reason": "F-020"}})
    interest = block(report(c, "deductions"), "Interest")
    row = next(r for r in interest["rows"] if r["key"] == "SchA.8a")
    assert (row["engine"], row["working"], row["kind"]) == (21847, 19697, "adjusted")
    assert c.get("/api/reports/area/nope").status_code == 404


def test_tax_computation_recomputations_agree(c):
    rep = report(c, "tax")
    ch = checks(rep)
    assert len(ch) >= 5 and all(x["agrees"] for x in ch.values())
    assert any("Schedule D tax worksheet" in k for k in ch)


def test_depreciation_assets_add_up_to_the_return(c):
    rep = report(c, "depreciation")
    assets = next(b for b in rep["blocks"] if b["type"] == "grid")
    assert len(assets["rows"]) == 9
    assert all(x["agrees"] for x in checks(rep).values())          # rental A, rental B, studio


def test_carryovers_in_and_out(c):
    rep = report(c, "carryovers")
    rows = {r["item"]: r for r in next(b for b in rep["blocks"] if b["type"] == "grid")["rows"]}
    assert rows["Suspended passive loss - 1450 Fremont Way"]["in"] == 6300
    assert rows["Minimum tax credit"]["out"] == 3871 and rows["Minimum tax credit"]["what"] == "new in 2025"
    assert all(x["agrees"] for x in checks(rep).values())


def test_books_to_tax_shows_the_1099k_gap(c):
    rep = report(c, "books")
    rows = next(b for b in rep["blocks"] if b["type"] == "grid")["rows"]
    receipts = next(r for r in rows if r["tax"] == 163700)
    assert receipts["difference"] == 12400                         # the 1099-K added on top of the books (F-015)
    meals = next(r for r in rows if r["item"] == "Meals")
    assert meals["difference"] == -1980


def test_retirement_and_prior_preparer(c):
    outside = next(b for b in report(c, "retirement")["blocks"] if b["type"] == "issues")
    assert outside["rows"] and all(r["id"].startswith("F-") for r in outside["rows"])
    open_items = report(c, "prior")["blocks"][1]["rows"]
    assert len(open_items) == 4
    form3520 = next(r for r in open_items if "3520" in r["text"])
    assert any("3520" in i["title"] for i in form3520["issues"])


def test_payments_line_up_with_the_agencies(c):
    rep = report(c, "payments")
    fed, ca = (b for b in rep["blocks"] if b["type"] == "grid")
    jan = next(r for r in fed["rows"] if r["date"] == "2026-01-15")
    assert jan["return"] is None and jan["irs"] == 3000 and "13,000" in fed["note"]
    sept = next(r for r in ca["rows"] if r["date"] == "2025-09-15")
    assert sept["year"] == "2024" and sept["ftb"] is None and "2024" in sept["status"]
    assert {"F-032", "F-033"} <= set(rep["issues"])


def test_roll_forward_lists_what_next_year_needs(c):
    rep = report(c, "rollforward")
    carry = {r["item"]: r for r in next(b for b in rep["blocks"] if b["title"] == "Carried into 2026")["rows"]}
    assert carry["Minimum tax credit"]["federal"] == 3871
    assets = next(b for b in rep["blocks"] if b["title"] == "Assets still in service")["rows"]
    assert not any(a["asset"].startswith("AUS-") for a in assets)     # property B was sold
    c.post("/api/events", headers={"X-Actor": PRIYA}, json={"type": "judgment", "target": "ver:v3", "payload": {
        "kind": "election", "decision": "Elect section 179 for the studio equipment", "authority": "IRC 179"}})
    choices = next(b for b in report(c, "rollforward")["blocks"] if b["title"] == "Choices made this year")["rows"]
    assert choices[0]["decision"].startswith("Elect section 179")
