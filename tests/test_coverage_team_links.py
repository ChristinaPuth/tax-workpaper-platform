"""Every area considered; assignments, deadlines and notifications; links and related returns; corrected
documents; e-file acknowledgments, where a rejection reopens the return to be filed again."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from workpaper.packet import packet_path

from test_filing import make_ready

PRIYA, DANIEL, HELEN, MARCUS, ADMIN, NGOZI = "st-01", "st-02", "st-03", "st-04", "st-05", "cu-01"
RETURN = "ver:v3"


@pytest.fixture()
def c(tmp_path):
    with TestClient(create_app(str(packet_path()), f"sqlite:///{tmp_path / 'p.db'}")) as client:
        yield client


def post(c, who, type, target=None, **payload):
    return c.post("/api/events", headers={"X-Actor": who}, json={"type": type, "target": target, "payload": payload})


def area(c, key):
    return next(a for a in c.get("/api/coverage", headers={"X-Actor": PRIYA}).json()["areas"] if a["key"] == key)


# ------------------------------------------------------------------ every area considered
def test_the_nine_budget_areas_and_what_is_in_them(c):
    cov = c.get("/api/coverage", headers={"X-Actor": PRIYA}).json()
    assert [a["key"] for a in cov["areas"]][:2] == ["intake_and_engagement", "wages_and_stock_compensation"]
    assert len(cov["areas"]) == 9 and len(cov["left"]) == 8                  # partner review is the partner's sign-off
    assert area(c, "rentals_and_sale")["open_errors"] == ["F-017"]
    assert any(b["kind"] == "areas" for b in c.get("/api/gate").json()["blockers"])


def test_an_area_is_considered_only_once_its_errors_are_settled(c):
    decide = lambda **p: post(c, PRIYA, "judgment", RETURN, kind="area", area="rentals_and_sale",  # noqa: E731
                              decision="Rentals reviewed", authority="Rental workpapers", **p)
    refused = decide(applies=True)
    assert refused.status_code == 422 and "F-017" in refused.json()["detail"]
    assert decide(applies=False).status_code == 422                          # it has amounts: it applies
    f = next(x for x in c.get("/api/findings").json() if x["id"] == "F-017")
    post(c, PRIYA, "judgment", f["nodes"][0], kind="judgment", decision="Repair, not improvement", authority="Reg. 1.263(a)-3",
         finding_id="F-017")
    assert decide(applies=True).status_code == 201
    a = area(c, "rentals_and_sale")
    assert a["status"] == "considered" and a["record"]["by"] == "Priya Raman"
    assert post(c, PRIYA, "judgment", RETURN, kind="area", area="partner_review", applies=True,
                decision="x", authority="y").status_code == 422
    assert post(c, PRIYA, "judgment", "doc:D06", kind="area", area="business", applies=True,
                decision="x", authority="y").status_code == 422             # an area belongs to the whole return


# ------------------------------------------------------------------ assignments, deadlines, notifications
def test_deadlines_count_from_the_firms_today_and_are_met_by_the_work(c):
    d = c.get("/api/assignments", headers={"X-Actor": PRIYA}).json()
    assert d["as_of"] == "2026-06-23" and [t["id"] for t in d["team"]] == [PRIYA, DANIEL, HELEN]
    by = {x["what"]: x for x in d["deadlines"]}
    assert by["Internal: preparer hand-off to review"]["status"] == "overdue"
    assert by["Extended due date (federal and California)"]["days_left"] == 114
    original = by["Federal Form 1040 and California 540NR - original due date"]
    assert (original["status"], original["met"]) == ("extended", "2026-04-14")    # the extension was filed in time
    assert by["FinCEN 114 (FBAR) automatic extended due date (outside engagement)"]["status"] == "outside"
    post(c, PRIYA, "signoff", RETURN, level="preparer")
    by = {x["what"]: x for x in c.get("/api/assignments").json()["deadlines"]}
    assert by["Internal: preparer hand-off to review"]["status"] == "met"


def test_assigning_work_notifies_the_person_until_they_do_it(c):
    assert post(c, PRIYA, "assign", "doc:D31", to=MARCUS).status_code == 403          # preparers do not assign
    assert post(c, DANIEL, "assign", "doc:D31", to=NGOZI).status_code == 422          # only staff
    assert post(c, DANIEL, "assign", "doc:D31", to=MARCUS, due="next week").status_code == 422
    assert post(c, DANIEL, "assign", "doc:D31", to=MARCUS, due="2026-06-25", note="Check the corrected 1099").status_code == 201
    n = c.get("/api/me/notifications", headers={"X-Actor": MARCUS}).json()
    mine = [i for i in n["items"] if i["kind"] == "assignment"]
    assert mine[0]["target"] == "doc:D31" and mine[0]["urgent"] and "Check the corrected 1099" in mine[0]["title"]
    post(c, MARCUS, "verify", "doc:D31", method="agreed_to_source_document")
    a = c.get("/api/assignments").json()["assignments"][0]
    assert a["status"] == "done"
    assert not [i for i in c.get("/api/me/notifications", headers={"X-Actor": MARCUS}).json()["items"] if i["kind"] == "assignment"]


def test_internal_deadlines_notify_the_role_they_belong_to(c):
    titles = lambda who: [i["title"] for i in c.get("/api/me/notifications", headers={"X-Actor": who}).json()["items"]]  # noqa: E731
    assert any("hand-off" in t for t in titles(PRIYA)) and not any("hand-off" in t for t in titles(DANIEL))
    assert any("review complete" in t for t in titles(DANIEL))
    assert not any("hand-off" in t for t in titles(MARCUS))                   # a preparer, but not on this return
    assert titles(ADMIN) == [] and titles(NGOZI) == []
    post(c, PRIYA, "question", "doc:D31", to=NGOZI, text="Did Meridian send anything else?")
    assert titles(NGOZI) == ["Priya Raman asked: Did Meridian send anything else?"]


# ------------------------------------------------------------------ links and related returns
def test_k1_lines_show_the_return_that_issued_them_and_last_year(c):
    r = c.get("/api/links/line:v3:SchE.28B").json()
    assert r["prior_year"]["value"] == 7900
    assert r["related_returns"][0]["who"] == "Ridgeline Real Estate Fund III LP"
    ada = c.get("/api/links/line:v3:F8812.1").json()["related_returns"]
    assert ada and ada[0]["who"] == "Ada Lindqvist-Okafor"


def test_a_link_shows_on_both_items(c):
    assert post(c, PRIYA, "link", "line:v3:SchA.8a", to="doc:nope").status_code == 422
    assert post(c, PRIYA, "link", "line:v3:SchA.8a", to="line:v3:SchA.8a").status_code == 422
    assert post(c, PRIYA, "link", "line:v3:SchA.8a", to="doc:D31", note="same refinance").status_code == 201
    a = c.get("/api/links/line:v3:SchA.8a").json()["links"]
    b = c.get("/api/links/doc:D31").json()["links"]
    assert a[0]["other"] == "doc:D31" and b[0]["other"] == "line:v3:SchA.8a" and b[0]["note"] == "same refinance"
    assert c.get("/api/links/doc:D31", headers={"X-Actor": NGOZI}).status_code == 403


# ------------------------------------------------------------------ corrected documents
def test_the_corrected_1099_lists_what_it_changed_and_where_it_landed(c):
    r = c.get("/api/documents/D31/correction").json()
    assert r["original"]["id"] == "D30" and r["superseded_in"] == ["v2", "v3"]
    ch = {x["field"]: x for x in r["changes"]}
    assert (ch["M9_basis"]["before"], ch["M9_basis"]["after"]) == (6900.0, 4880.0)
    assert ch["M14_acquired"]["used_before"] == {"v1": ["F8949.A.M14"]}         # short-term until corrected
    assert ch["M14_acquired"]["used_after"]["v3"] == ["F8949.D.M14"]            # long-term after
    assert c.get("/api/documents/D30/correction").json()["corrected"]["id"] == "D31"
    assert c.get("/api/documents/D06/correction").status_code == 404


# ------------------------------------------------------------------ e-file acknowledgments
def ack(c, who, jurisdiction, status, errors=None):
    p = {"jurisdiction": jurisdiction, "status": status, "submission_id": "x"}
    if errors is not None:
        p["errors"] = errors
    return post(c, who, "efile", RETURN, **p)


def test_a_rejected_e_file_reopens_the_return_to_fix_and_file_again(c):
    assert ack(c, HELEN, "federal", "accepted").status_code == 409                 # nothing filed yet
    make_ready(c)
    assert post(c, HELEN, "file", RETURN, jurisdictions=["federal", "california"]).status_code == 201
    assert ack(c, PRIYA, "federal", "rejected", [{"code": "R0000-504-02", "message": "x"}]).status_code == 403
    assert ack(c, HELEN, "federal", "rejected").status_code == 422                 # a rejection says why
    assert ack(c, HELEN, "federal", "rejected", [{"code": "R0000-504-02", "message": "Dependent TIN"}]).status_code == 201
    assert ack(c, HELEN, "california", "not_transmitted", [{"code": "STATE-HOLD", "message": "held"}]).status_code == 201
    g = c.get("/api/gate").json()
    assert g["filed"] is None and g["rejected"]["errors"][0]["code"] == "R0000-504-02" and len(g["acks"]) == 2
    # back in preparation: the return takes changes again, and is filed again
    assert post(c, PRIYA, "note", "line:v3:F1040.1a", text="fixed").status_code == 201
    assert post(c, HELEN, "file", RETURN, jurisdictions=["federal", "california"]).status_code == 201
    assert ack(c, HELEN, "federal", "accepted").status_code == 201
    g = c.get("/api/gate").json()
    assert g["filed"] is not None and g["rejected"] is None
    assert post(c, PRIYA, "verify", "doc:D06", method="agreed_to_prior_year").status_code == 409   # frozen again
