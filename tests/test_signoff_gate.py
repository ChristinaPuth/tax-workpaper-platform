"""Sign-offs that reopen, decisions that settle findings, questions between people, and the filing gate."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from workpaper.packet import packet_path

PRIYA, DANIEL, HELEN, MARCUS, NGOZI = "st-01", "st-02", "st-03", "st-04", "cu-01"
RETURN = "ver:v3"


@pytest.fixture()
def c(tmp_path):
    with TestClient(create_app(str(packet_path()), f"sqlite:///{tmp_path / 's.db'}")) as client:
        yield client


def post(c, actor, type, target=None, **payload):
    return c.post("/api/events", headers={"X-Actor": actor}, json={"type": type, "target": target, "payload": payload})


def signoffs(c, target=None):
    return c.get("/api/signoffs", params={"target": target} if target else {}).json()


def inbox(c, actor):
    body = c.get("/api/inbox", headers={"X-Actor": actor}).json()
    return {s["key"]: s for s in body["sections"]}


def steps(c):
    g = c.get("/api/gate").json()
    return g, {s["n"]: s for s in g["steps"]}


def decide(c, actor, finding_id, target, kind="explanation", decision="Explained", authority="Client records"):
    return post(c, actor, "judgment", target, kind=kind, decision=decision, authority=authority, finding_id=finding_id)


# ------------------------------------------------------------------ sign-off content hash
def test_signoff_records_a_hash_and_starts_valid(c):
    ev = post(c, DANIEL, "signoff", "line:v3:F1040.11", level="reviewer").json()
    assert len(ev["payload"]["hash"]) == 64 and ev["payload"]["scope_size"] > 10   # AGI and everything under it
    [s] = signoffs(c)
    assert s["valid"] and s["changed"] == []


def test_an_upstream_change_reopens_and_says_what_changed(c):
    post(c, DANIEL, "signoff", "line:v3:F1040.11", level="reviewer")
    adj = post(c, PRIYA, "adjust", "line:v3:SchC.1", new_value=151300, reason="1099-K already in books").json()
    [s] = signoffs(c)
    assert not s["valid"]
    changed = {x["node"]: x["what"] for x in s["changed"]}
    assert "adjusted" in changed["line:v3:SchC.1"] and "163,700 -> 151,300" in changed["line:v3:SchC.1"]
    assert "line:v3:F1040.11" in changed                                  # the signed number itself moved
    post(c, PRIYA, "undo", None, event_id=adj["id"])
    assert signoffs(c)[0]["valid"]                                       # back to exactly what was signed


def test_notes_and_verifications_do_not_reopen(c):
    post(c, DANIEL, "signoff", "line:v3:SchC.1", level="reviewer")
    post(c, PRIYA, "note", "line:v3:SchC.1", text="Tied to the 1099s")
    post(c, PRIYA, "verify", "ev:ev-0103", method="agreed_to_source_document")
    [s] = signoffs(c)
    assert s["valid"] and s["verified_since"] == 1                       # reported, not a reopen


def test_an_unrelated_change_does_not_reopen(c):
    post(c, DANIEL, "signoff", "line:v3:SchC.1", level="reviewer")
    post(c, PRIYA, "adjust", "line:v3:SchA.8a", new_value=19697, reason="payoff interest counted twice")
    assert signoffs(c)[0]["valid"]


def test_no_self_review_across_the_signed_scope(c):
    post(c, DANIEL, "adjust", "line:v3:SchC.1", new_value=151300, reason="1099-K already in books")
    r = post(c, DANIEL, "signoff", "line:v3:F1040.11", level="reviewer")  # AGI depends on what Daniel changed
    assert r.status_code == 403
    assert post(c, HELEN, "signoff", "line:v3:F1040.11", level="reviewer").status_code == 201


def test_reopened_signoff_lands_in_the_signers_inbox(c):
    post(c, DANIEL, "signoff", "line:v3:SchC.31", level="reviewer")
    post(c, PRIYA, "adjust", "line:v3:SchC.1", new_value=151300, reason="1099-K already in books")
    item = inbox(c, DANIEL)["reopened"]["items"][0]
    assert item["target"] == "line:v3:SchC.31" and "SchC.1" in item["what"]


# ------------------------------------------------------------------ decisions
def test_a_decision_settles_a_finding_and_goes_to_review(c):
    assert c.get("/api/finding-states").json()["F-112"]["state"] == "open"
    r = decide(c, PRIYA, "F-112", "qa:qa-14", kind="judgment",
               decision="Client misunderstood the question; the 1099-Bs show the sales.", authority="D28, D31, D74")
    assert r.status_code == 201
    st = c.get("/api/finding-states").json()["F-112"]
    assert st["state"] == "decided" and st["authority"] == "D28, D31, D74"
    review = inbox(c, DANIEL)["review"]["items"]
    assert any(i["kind"] == "decision" and i["finding_id"] == "F-112" for i in review)
    post(c, DANIEL, "signoff", "qa:qa-14", level="reviewer")
    assert c.get("/api/finding-states").json()["F-112"]["state"] == "reviewed"


def test_decisions_are_validated(c):
    assert post(c, PRIYA, "judgment", "qa:qa-14", kind="whim", decision="x", authority="y").status_code == 422
    assert post(c, PRIYA, "judgment", "qa:qa-14", kind="judgment", authority="y").status_code == 422
    assert decide(c, PRIYA, "F-999", "qa:qa-14").status_code == 422


def test_bulk_explanations_settle_the_variance_step(c):
    findings = c.get("/api/findings", params={"check": "P5-prior-year-variance"}).json()
    events = [{"type": "judgment", "target": f["nodes"][0],
               "payload": {"kind": "explanation", "decision": "New employer, business growth and the condo sale",
                           "authority": "Client questionnaire, W-2s, closing statement", "finding_id": f["id"]}}
              for f in findings]
    r = c.post("/api/events/batch", headers={"X-Actor": PRIYA}, json={"events": events})
    assert r.status_code == 201 and len(r.json()["events"]) == 59
    _, s = steps(c)
    assert s[5]["status"] == "done" and s[5]["progress"] == {"done": 59, "total": 59}
    # the reviewer sees one item for the batch, and can sign off all of it at once
    [group] = [i for i in inbox(c, DANIEL)["review"]["items"] if i["kind"] == "decision_batch"]
    assert group["count"] == 59 and group["check"] == "P5" and len(group["targets"]) == 59
    signs = [{"type": "signoff", "target": t, "payload": {"level": "reviewer"}} for t in group["targets"]]
    assert c.post("/api/events/batch", headers={"X-Actor": DANIEL}, json={"events": signs}).status_code == 201
    assert "review" not in inbox(c, DANIEL)
    states = c.get("/api/finding-states").json()
    assert all(states[f["id"]]["state"] == "reviewed" for f in findings)


# ------------------------------------------------------------------ questions
def test_questions_reach_colleagues_and_answers_close_them(c):
    q = post(c, PRIYA, "question", "line:v3:SchE.14A", to=DANIEL, text="Repair or improvement for the HVAC?").json()
    assert inbox(c, DANIEL)["questions"]["items"][0]["event_id"] == q["id"]
    post(c, DANIEL, "answer", None, event_id=q["id"], text="Improvement: whole system replaced.")
    assert "questions" not in inbox(c, DANIEL)
    assert inbox(c, PRIYA)["replies"]["items"][0]["target"] == "line:v3:SchE.14A"


def test_a_question_needs_someone_else_to_answer_it(c):
    assert post(c, PRIYA, "question", "line:v3:SchC.1", to=PRIYA, text="?").status_code == 422
    assert post(c, PRIYA, "question", "line:v3:SchC.1", to="st-99", text="?").status_code == 422


# ------------------------------------------------------------------ the gate and the twelve steps
def test_the_gate_starts_closed_with_derived_steps(c):
    g, s = steps(c)
    assert not g["ready"] and len(g["steps"]) == 12
    assert s[1]["status"] == "done"                                       # D01 and D02 signed
    assert s[6]["status"] == "done"                                       # carryovers agree (no P4 findings)
    assert s[2]["status"] == "open" and s[5]["progress"]["total"] == 59
    assert s[12]["status"] == "later"
    assert any(b["kind"] == "errors" for b in g["blockers"])


def test_steps_follow_the_work(c):
    post(c, PRIYA, "verify", "doc:D06", method="agreed_to_prior_year")
    decide(c, PRIYA, "F-034", "person:theo", kind="judgment",
           decision="SSN corrected to 666-74-3390", authority="Social Security card (D71), 2024 return (D06)")
    post(c, PRIYA, "judgment", "line:v3:F8867.status", kind="due_diligence",
         decision="Form 8867 completed: Theo qualifies for the CTC", authority="Form 8867 questions, D71, household")
    _, s = steps(c)
    assert s[2]["status"] == s[3]["status"] == s[8]["status"] == "done"


def test_blocking_review_note_blocks_until_resolved(c):
    note = post(c, DANIEL, "review_note", "line:v3:SchC.1", text="Tie receipts to the 1099s", blocking=True).json()
    g, _ = steps(c)
    assert any(b["kind"] == "review_note" for b in g["blockers"])
    post(c, DANIEL, "resolve_note", None, event_id=note["id"], text="Tied.")
    g, _ = steps(c)
    assert not any(b["kind"] == "review_note" for b in g["blockers"])


def test_unreviewed_and_over_threshold_changes_block(c):
    post(c, PRIYA, "adjust", "line:v3:SchC.1", new_value=151300, reason="1099-K already in books")
    kinds = {b["kind"] for b in steps(c)[0]["blockers"]}
    assert {"unreviewed", "partner"} <= kinds
    post(c, DANIEL, "signoff", "line:v3:SchC.1", level="reviewer")
    post(c, HELEN, "signoff", "line:v3:SchC.1", level="partner")
    kinds = {b["kind"] for b in steps(c)[0]["blockers"]}
    assert not kinds & {"unreviewed", "partner"}


def test_return_signoffs_drive_steps_10_and_11_and_reopen(c):
    post(c, DANIEL, "signoff", RETURN, level="reviewer")
    _, s = steps(c)
    assert s[10]["status"] == "done" and "Daniel Ortiz" in s[10]["detail"]
    assert inbox(c, HELEN)["return"]["items"][0]["target"] == RETURN       # partner is told it is her turn
    post(c, HELEN, "signoff", RETURN, level="partner")
    _, s = steps(c)
    assert s[11]["status"] == "done"
    post(c, PRIYA, "adjust", "line:v3:SchA.8a", new_value=19697, reason="payoff interest counted twice")
    _, s = steps(c)
    assert s[10]["status"] == s[11]["status"] == "open" and "Reopened" in s[10]["detail"]


def test_a_preparer_cannot_sign_off_the_return_as_reviewer(c):
    assert post(c, PRIYA, "signoff", RETURN, level="reviewer").status_code == 403


def test_signing_a_batch_does_not_approve_another_change_on_the_same_line(c):
    post(c, PRIYA, "adjust", "line:v3:SchC.1", new_value=151300, reason="1099-K already in books")
    findings = c.get("/api/findings", params={"check": "P5-prior-year-variance"}).json()
    events = [{"type": "judgment", "target": f["nodes"][0],
               "payload": {"kind": "explanation", "decision": "Explained", "authority": "Client", "finding_id": f["id"]}}
              for f in findings]
    c.post("/api/events/batch", headers={"X-Actor": PRIYA}, json={"events": events})
    [group] = [i for i in inbox(c, DANIEL)["review"]["items"] if i["kind"] == "decision_batch"]
    assert group["held_back"] == ["line:v3:SchC.1"] and "line:v3:SchC.1" not in group["targets"]
    signs = [{"type": "signoff", "target": t, "payload": {"level": "reviewer"}} for t in group["targets"]]
    c.post("/api/events/batch", headers={"X-Actor": DANIEL}, json={"events": signs})
    review = inbox(c, DANIEL)["review"]["items"]
    assert any(i["kind"] == "adjustment" and i["target"] == "line:v3:SchC.1" for i in review)  # still waiting


def test_signoffs_given_together_reopen_together(c):
    targets = ["line:v3:SchC.29", "line:v3:SchC.31", "line:v3:Sch1.3"]
    signs = [{"type": "signoff", "target": t, "payload": {"level": "reviewer"}} for t in targets]
    c.post("/api/events/batch", headers={"X-Actor": DANIEL}, json={"events": signs})
    post(c, PRIYA, "adjust", "line:v3:SchC.25", new_value=2172, reason="business-use share")
    [item] = inbox(c, DANIEL)["reopened"]["items"]
    assert item["count"] == 3 and sorted(item["targets"]) == sorted(targets) and "SchC.25" in item["what"]
    reopened = [b for b in steps(c)[0]["blockers"] if b["kind"] == "reopened"]
    assert len(reopened) == 1 and reopened[0]["count"] == 3
    # signing again replaces the reopened sign-offs
    c.post("/api/events/batch", headers={"X-Actor": DANIEL}, json={"events": signs})
    assert "reopened" not in inbox(c, DANIEL)
    assert all(s["valid"] for s in signoffs(c)) and len(signoffs(c)) == 3
