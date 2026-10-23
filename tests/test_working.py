"""The working return (Plan C propagation), the role-based Inbox and search."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from workpaper.index import Index
from workpaper.packet import Packet, packet_path
from workpaper.working import build, infer_category, infer_operator

PRIYA, DANIEL, HELEN, MARCUS, JO, SAM, NGOZI = "st-01", "st-02", "st-03", "st-04", "st-05", "st-06", "cu-01"


@pytest.fixture(scope="module")
def p():
    return Packet.load(packet_path())


@pytest.fixture(scope="module")
def ix(p):
    return Index(p)


def adj(i, key, value, reason="test", actor=PRIYA, **extra):
    return {"id": i, "type": "adjust", "target": f"line:v3:{key}", "actor": actor, "at": "2026-07-01T00:00:00Z",
            "payload": {"new_value": value, "reason": reason, **extra}}


def undo(i, of, actor=PRIYA):
    return {"id": i, "type": "undo", "target": None, "actor": actor, "at": "2026-07-01T00:00:00Z",
            "payload": {"event_id": of}}


# ------------------------------------------------------------------ operators
def test_operators_are_inferred_from_the_engine(p):
    assert infer_operator(p, "v3", "SchC.29") == ("diff", ["SchC.7", "SchC.28"])        # receipts - expenses
    assert infer_operator(p, "v3", "F1040.33")[0] == "sum"
    assert infer_operator(p, "v3", "F540NR.97")[0] == "rdiff"                           # payments - tax
    assert infer_operator(p, "v3", "SchCA540NR.12.D")[0] == "ca_col"                    # A - B + C
    assert infer_operator(p, "v3", "SchC.9") is None                                     # mileage formula: not arithmetic


def test_categories():
    assert infer_category("SchC.1") == ("schc_profit", 1)
    assert infer_category("SchC.25") == ("schc_profit", -1)        # an expense going up lowers profit
    assert infer_category("F8949.B.N1") == ("stcg", 1)
    assert infer_category("F8949.E.N4") == ("ltcg", 1)
    assert infer_category("SchA.5b") == ("salt", 1)
    assert infer_category("F1040.26") == ("payment", 1)
    assert infer_category("F1040.16") is None


# ------------------------------------------------------------------ propagation
def test_no_adjustments_means_the_engine_return(p, ix):
    w = build(p, ix, [])
    assert w.lines == {} and w.estimate["federal"] == 0
    assert w.summary["agi"]["value"] == w.summary["agi"]["engine"] == 445590


def test_adjustment_propagates_arithmetic_and_marks_formulas_stale(p, ix):
    w = build(p, ix, [adj(1, "SchC.1", 151300)])
    assert w.lines["SchC.1"]["kind"] == "adjusted"
    assert w.lines["SchC.31"] == {"engine": 81854, "value": 69454.0, "kind": "propagated", "partial": False}
    assert w.lines["F1040.11"]["value"] == 433190.0 and w.lines["F1040.11"]["partial"]   # SEP/SEHI limits await recompute
    assert w.lines["SchSE.12"]["kind"] == "stale"                                        # SE tax is the engine's formula
    assert w.lines["F1040.16"]["kind"] == "stale"                                        # tax from brackets
    assert "F1040.1a" not in w.lines                                                    # unrelated lines untouched


def test_estimate_matches_the_finding_method(p, ix):
    w = build(p, ix, [adj(1, "SchC.1", 151300)])
    assert w.estimate["federal"] == -4402 and w.estimate["california"] == -384           # same as finding F-015
    assert w.summary["balance_due"]["value"] == 4220 - 4402
    assert any("5%" in x for x in w.warnings)


def test_payments_flow_arithmetically_not_by_estimate(p, ix):
    w = build(p, ix, [adj(1, "F1040.26", 12000, "IRS transcript shows 3,000 on 1/15")])
    assert w.estimate["federal"] == 0
    assert w.lines["F1040.37"]["value"] == 5220.0 and w.summary["balance_due"]["value"] == 5220


def test_undo_restores_the_engine_value(p, ix):
    w = build(p, ix, [adj(1, "SchC.1", 151300), undo(2, 1)])
    assert w.lines == {} and w.adjustments == []


def test_latest_adjustment_on_a_line_wins(p, ix):
    w = build(p, ix, [adj(1, "SchC.1", 150000), adj(2, "SchC.1", 151300)])
    assert w.lines["SchC.1"]["value"] == 151300 and len(w.adjustments) == 1


def test_crossing_a_threshold_warns(p, ix):
    w = build(p, ix, [adj(1, "SchC.1", 100000)])                       # AGI falls below the 400,000 CTC phase-out
    assert any("child tax credit" in x for x in w.warnings)


def test_adjusting_a_source_value_makes_its_lines_stale(p, ix):
    ev = {"id": 1, "type": "adjust", "target": "ev:ev-0127", "actor": PRIYA, "at": "t",
          "payload": {"new_value": 0, "reason": "already in books"}}
    w = build(p, ix, [ev])
    assert w.lines["SchC.1"]["kind"] == "stale"


# ------------------------------------------------------------------ API: working, inbox, search
@pytest.fixture()
def client(tmp_path):
    with TestClient(create_app(str(packet_path()), f"sqlite:///{tmp_path / 'w.db'}")) as c:
        yield c


def post(c, actor, type, target=None, **payload):
    return c.post("/api/events", headers={"X-Actor": actor}, json={"type": type, "target": target, "payload": payload})


def inbox(c, actor):
    body = c.get("/api/inbox", headers={"X-Actor": actor}).json()
    return body, {s["key"]: s for s in body["sections"]}


def test_working_endpoint_follows_the_log(client):
    assert client.get("/api/working").json()["lines"] == {}
    post(client, PRIYA, "adjust", "line:v3:SchC.1", new_value=151300, reason="1099-K already in books")
    w = client.get("/api/working").json()
    assert w["lines"]["SchC.31"]["kind"] == "propagated" and w["estimate"]["federal"] == -4402


def test_adjust_only_the_current_version(client):
    r = post(client, PRIYA, "adjust", "line:v1:SchC.1", new_value=1, reason="x")
    assert r.status_code == 422 and "current version" in r.json()["detail"]
    assert post(client, PRIYA, "adjust", "doc:D21", new_value=1, reason="x").status_code == 422


def test_preparer_inbox_lists_issues_worst_first_in_plain_language(client):
    body, s = inbox(client, PRIYA)
    fix = s["fix"]["items"]
    assert fix[0]["severity"] == "error"
    errors = [i for i in fix if i["severity"] == "error"]
    assert len(errors) == 18
    effects = [abs(i["effect"]["federal"] or 0) + abs(i["effect"]["california"] or 0) for i in errors]
    assert effects == sorted(effects, reverse=True)                     # biggest tax effect first
    card = next(i for i in fix if i["id"] == "F-015")
    assert card["why"] and card["todo"] and "151,300" in card["proposal"]
    assert card["area_label"] == "Business (Schedule C)"
    assert not [i for i in fix if i["kind"] == "group"]                  # batches live in their own section
    batch = {i["id"]: i for i in s["batch"]["items"]}
    assert batch["group:P5"]["count"] == 59 and batch["group:P5"]["title"] == "59 prior-year changes to explain"
    assert batch["group:P6"]["title"] == "1 document not used"           # singular when there is one
    assert body["total"] == len(fix) + len(batch)


def test_a_fix_moves_from_the_preparer_to_the_reviewer_to_the_partner(client):
    post(client, PRIYA, "adjust", "line:v3:SchC.1", new_value=151300, reason="1099-K already in books")
    _, s = inbox(client, PRIYA)
    assert "F-015" not in [i["id"] for i in s["fix"]["items"]]
    assert "F-015" in [i["id"] for i in s["done"]["items"]]               # changed, waiting for review
    _, r = inbox(client, DANIEL)
    review = r["review"]["items"]
    assert review and review[0]["kind"] == "adjustment" and review[0]["effect"]["federal"] == -4402
    _, h = inbox(client, HELEN)
    assert [i["target"] for i in h["partner"]["items"]] == ["line:v3:SchC.1"]  # over the 1,000 threshold
    post(client, DANIEL, "signoff", "line:v3:SchC.1", level="reviewer")
    _, r = inbox(client, DANIEL)
    assert "review" not in r
    post(client, HELEN, "signoff", "line:v3:SchC.1", level="partner")
    _, h = inbox(client, HELEN)
    assert "partner" not in h


def test_reviewer_does_not_see_own_changes_for_review(client):
    post(client, DANIEL, "adjust", "line:v3:SchC.25", new_value=2172, reason="business-use share")
    _, r = inbox(client, DANIEL)
    assert "review" not in r


def test_client_sees_only_questions_addressed_to_them(client):
    body, _ = inbox(client, NGOZI)
    assert body["total"] == 0 and body["empty_message"]
    q = post(client, PRIYA, "question", "line:v3:Sch1.17", to=NGOZI, text="Could Erik join your employer's plan?").json()
    _, s = inbox(client, NGOZI)
    assert [i["event_id"] for i in s["questions"]["items"]] == [q["id"]]
    post(client, NGOZI, "answer", None, event_id=q["id"], text="Yes, family coverage was offered.")
    body, _ = inbox(client, NGOZI)
    assert body["total"] == 0
    _, s = inbox(client, PRIYA)
    assert s["replies"]["items"][0]["target"] == "line:v3:Sch1.17"


def test_administrator_has_an_explained_empty_inbox(client):
    body, _ = inbox(client, JO)
    assert body["total"] == 0 and "administrators" in body["empty_message"]


def test_blocking_review_note_shows_first_for_the_preparer(client):
    post(client, DANIEL, "review_note", "line:v3:SchC.1", text="Tie gross receipts to the 1099s", blocking=True)
    _, s = inbox(client, PRIYA)
    assert s["notes"]["items"][0]["severity"] == "error"


def test_search_by_amount_finds_lines_and_values(client):
    r = client.get("/api/search", params={"q": "163,700"}).json()
    assert r["amount"] == 163700 and "SchC.1" in [l["key"] for l in r["lines"]]
    r = client.get("/api/search", params={"q": "$12400"}).json()
    assert any(e["document_id"] == "D21" for e in r["extracted_values"])
    titles = [f["title"] for f in r["findings"]]
    assert any("12,400" in t for t in titles) and not any("212,400" in t for t in titles)  # whole numbers only


def test_search_by_name_ranks_and_dedupes(client):
    r = client.get("/api/search", params={"q": "gross receipts"}).json()
    keys = [l["key"] for l in r["lines"]]
    assert keys[0] == "SchC.1" and len(keys) == len(set(keys))         # current version only, no v1/v2 copies
    assert client.get("/api/search", params={"q": "d23"}).json()["documents"][0]["id"] == "D23"
    people = client.get("/api/search", params={"q": "ngozi"}).json()["people"]
    assert {x["id"] for x in people} >= {"person:ngozi", "cu-01"}


# ------------------------------------------------------------------ fixes found while testing the Inbox
def test_waiting_for_review_does_not_count_as_needing_you(client):
    before, _ = inbox(client, PRIYA)
    post(client, PRIYA, "adjust", "line:v3:SchC.1", new_value=151300, reason="1099-K already in books")
    after, s = inbox(client, PRIYA)
    assert after["total"] == before["total"] - 1                        # the fixed issue no longer needs Priya
    assert s["done"]["needs_you"] is False


def test_a_changed_issue_says_who_changed_it_and_that_nothing_is_left_to_do(client):
    post(client, PRIYA, "adjust", "line:v3:SchC.1", new_value=151300, reason="1099-K already in books")
    _, s = inbox(client, PRIYA)
    card = s["done"]["items"][0]
    assert card["state"] == "adjusted" and card["handled_by"] == PRIYA
    assert card["why"].startswith("Priya Raman changed SchC.1")
    assert card["todo"] == "Nothing to do until a reviewer signs off."


def test_every_issue_opens_something_it_cites(client):
    _, s = inbox(client, PRIYA)
    items = {i["id"]: i for i in s["fix"]["items"]}
    low_conf = next(i for i in items.values() if "LOW_CONFIDENCE_READ" in i["title"])
    assert low_conf["target"] == "ev:ev-1049"                             # the handwritten receipt, not the diagnostic
    conflict = next(i for i in items.values() if "QUESTIONNAIRE_SALES_CONFLICT" in i["title"])
    assert conflict["target"] is None and conflict["finding_id"]         # nothing with a page: the UI opens the finding


def test_outside_filings_ask_for_a_decision_not_a_correction(client):
    _, s = inbox(client, PRIYA)
    f3520 = next(i for i in s["fix"]["items"] if "Form 3520" in i["title"])
    assert f3520["proposal"] is None and "Raise it with the client" in f3520["todo"]
    assert all("apply the proposed correction" not in i["todo"] for i in s["fix"]["items"] if not i["proposal"])


def test_finding_states_follow_the_log(client):
    assert client.get("/api/finding-states").json()["F-015"] == {"state": "open"}
    post(client, PRIYA, "adjust", "line:v3:SchC.1", new_value=151300, reason="1099-K already in books")
    st = client.get("/api/finding-states").json()["F-015"]
    assert st["state"] == "adjusted" and st["by"] == PRIYA and st["line"] == "SchC.1"
    post(client, DANIEL, "signoff", "line:v3:SchC.1", level="reviewer")
    assert client.get("/api/finding-states").json()["F-015"]["state"] == "reviewed"


def test_lines_name_their_findings(client):
    rows = {r["key"]: r for r in client.get("/api/versions/v3/lines").json()}
    assert {"id": "F-015", "severity": "error"} in rows["SchC.1"]["finding_refs"]


def test_changing_a_number_does_not_settle_an_issue_that_asks_for_an_explanation(client):
    post(client, PRIYA, "adjust", "line:v3:SchC.1", new_value=151300, reason="1099-K already in books")
    st = client.get("/api/finding-states").json()
    assert st["F-015"]["state"] == "adjusted"     # proposed SchC.1 -> 151,300: settled by the change
    assert st["F-056"]["state"] == "open"         # variance vs 2024 still needs an explanation


def test_a_number_is_also_searched_as_text(client):
    r = client.get("/api/search", params={"q": "3520"}).json()
    assert r["amount"] == 3520
    assert any("Form 3520" in f["title"] for f in r["findings"])          # text match
    assert any(e["text_as_read"] == "3,520.00" for e in r["extracted_values"])  # amount match (crypto lot C5)
