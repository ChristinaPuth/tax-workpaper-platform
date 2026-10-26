"""Attachments are stored and recorded on a node; a bulk action is undone in one go."""
from __future__ import annotations

import base64

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from workpaper.packet import packet_path

PRIYA, DANIEL, MARCUS, NGOZI, ERIK = "st-01", "st-02", "st-04", "cu-01", "cu-02"


@pytest.fixture()
def c(tmp_path):
    with TestClient(create_app(str(packet_path()), f"sqlite:///{tmp_path / 'u.db'}")) as client:
        yield client


def upload(c, who, target="doc:D06", body=b"%PDF-1.4 receipt", **extra):
    return c.post("/api/attachments", headers={"X-Actor": who}, json={
        "target": target, "filename": "C:\\scans\\receipt.pdf", "mime": "application/pdf",
        "data": base64.b64encode(body).decode(), **extra})


def test_a_file_is_stored_recorded_on_the_node_and_downloaded_as_uploaded(c):
    r = upload(c, PRIYA, note="  HVAC invoice  ")
    assert r.status_code == 201
    ev = r.json()
    assert ev["type"] == "attach" and ev["target"] == "doc:D06"
    assert ev["payload"]["filename"] == "receipt.pdf" and ev["payload"]["size"] == 16 and ev["payload"]["note"] == "HVAC invoice"
    got = c.get(f"/api/attachments/{ev['payload']['attachment_id']}", headers={"X-Actor": DANIEL})
    assert got.content == b"%PDF-1.4 receipt" and got.headers["content-type"] == "application/pdf"
    assert 'filename="receipt.pdf"' in got.headers["content-disposition"]


def test_uploads_are_checked_before_anything_is_stored(c):
    assert upload(c, PRIYA, target="doc:nope").status_code == 422
    assert upload(c, PRIYA, body=b"").status_code == 422
    assert c.post("/api/attachments", headers={"X-Actor": PRIYA},
                  json={"target": "doc:D06", "filename": "x", "data": "not base64!"}).status_code == 422
    assert upload(c, PRIYA, body=b"x" * (5 * 1024 * 1024 + 1)).status_code == 413
    assert upload(c, "st-05").status_code == 403                                  # the administrator does not attach
    assert c.get("/api/attachments/1", headers={"X-Actor": PRIYA}).status_code == 404   # nothing was stored


def test_an_attach_event_must_name_a_stored_file(c):
    post = lambda payload: c.post("/api/events", headers={"X-Actor": PRIYA},  # noqa: E731
                                  json={"type": "attach", "target": "doc:D06", "payload": payload})
    assert post({}).status_code == 422
    assert post({"attachment_id": 99}).status_code == 422
    assert post({"ref": "msg-07"}).status_code == 201


def test_clients_open_only_their_own_files(c):
    mine = upload(c, NGOZI).json()["payload"]["attachment_id"]
    staff = upload(c, PRIYA).json()["payload"]["attachment_id"]
    assert c.get(f"/api/attachments/{mine}", headers={"X-Actor": NGOZI}).status_code == 200
    assert c.get(f"/api/attachments/{mine}", headers={"X-Actor": ERIK}).status_code == 403
    assert c.get(f"/api/attachments/{staff}", headers={"X-Actor": NGOZI}).status_code == 403
    assert c.get(f"/api/attachments/{mine}", headers={"X-Actor": PRIYA}).status_code == 200


def batch(c, who, events):
    return c.post("/api/events/batch", headers={"X-Actor": who}, json={"events": events})


def notes(n):
    return [{"type": "note", "target": "doc:D06", "payload": {"text": f"note {i}"}} for i in range(n)]


def test_a_batch_is_undone_in_one_go_and_only_once(c):
    b = batch(c, PRIYA, notes(3)).json()
    one = b["events"][0]["id"]
    assert c.post("/api/events", headers={"X-Actor": PRIYA}, json={"type": "undo", "payload": {"event_id": one}}).status_code == 201
    r = c.post(f"/api/events/batch/{b['batch_id']}/undo", headers={"X-Actor": PRIYA})
    assert r.status_code == 201 and len(r.json()["events"]) == 2                   # the one already undone is skipped
    live = [e for e in c.get("/api/events?target=doc:D06").json() if e["type"] == "note"]
    assert all(e["undone"] for e in live)
    assert c.post(f"/api/events/batch/{b['batch_id']}/undo", headers={"X-Actor": PRIYA}).status_code == 409
    assert c.post("/api/events/batch/nope/undo", headers={"X-Actor": PRIYA}).status_code == 404


def test_batch_undo_follows_the_undo_rules(c):
    b = batch(c, PRIYA, notes(2)).json()
    refused = c.post(f"/api/events/batch/{b['batch_id']}/undo", headers={"X-Actor": MARCUS})
    assert refused.status_code == 403 and "2 of 2 refused" in refused.json()["detail"]
    assert c.post(f"/api/events/batch/{b['batch_id']}/undo", headers={"X-Actor": DANIEL}).status_code == 201   # a reviewer may


def test_undoing_a_batch_of_decisions_reopens_the_issues(c):
    states = c.get("/api/finding-states").json()
    open_ = [f for f in c.get("/api/findings").json() if f["severity"] != "info" and states[f["id"]]["state"] == "open"][:3]
    b = batch(c, PRIYA, [{"type": "judgment", "target": f["nodes"][0], "payload": {
        "kind": "explanation", "decision": "Reviewed", "authority": "File", "finding_id": f["id"]}} for f in open_]).json()
    assert all(c.get("/api/finding-states").json()[f["id"]]["state"] != "open" for f in open_)
    c.post(f"/api/events/batch/{b['batch_id']}/undo", headers={"X-Actor": PRIYA})
    assert all(c.get("/api/finding-states").json()[f["id"]]["state"] == "open" for f in open_)


def test_clients_do_not_see_the_8867_working(c):
    assert c.get("/api/due-diligence", headers={"X-Actor": NGOZI}).status_code == 403
