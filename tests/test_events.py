"""Event log, enforced roles and live updates (the write side).

Each test gets a fresh database; the packet is loaded once per module.
"""
from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

from app.live import Broker, stream
from app.main import create_app
from workpaper.packet import packet_path

PRIYA, DANIEL, HELEN, MARCUS, JO, SAM, NGOZI = "st-01", "st-02", "st-03", "st-04", "st-05", "st-06", "cu-01"
SCHC1 = "line:v3:SchC.1"


@pytest.fixture()
def db_url(tmp_path):
    return f"sqlite:///{tmp_path / 'events.db'}"


@pytest.fixture()
def client(db_url):
    with TestClient(create_app(str(packet_path()), db_url)) as c:
        yield c


def post(c, actor, type, target=None, **payload):
    return c.post("/api/events", headers={"X-Actor": actor} if actor else {},
                  json={"type": type, "target": target, "payload": payload})


def adjust(c, actor=PRIYA, target=SCHC1):
    return post(c, actor, "adjust", target, new_value=151300,
                reason="1099-K 12,400 already deposited gross in books revenue (D15 p3)")


# ------------------------------------------------------------------ identities
def test_people_come_from_the_packet(client):
    people = {p["id"]: p for p in client.get("/api/people").json()}
    assert len(people) == 8  # six staff, two client users
    assert people[MARCUS]["sensitive_data_clearance"] is False
    assert "adjust" not in people[NGOZI]["can"] and "answer" in people[NGOZI]["can"]


def test_writes_need_an_actor(client):
    assert post(client, None, "note", SCHC1, text="x").status_code == 401
    assert post(client, "st-99", "note", SCHC1, text="x").status_code == 401


# ------------------------------------------------------------------ validation
def test_target_must_be_a_real_node(client):
    r = post(client, PRIYA, "note", "line:v3:NOPE", text="x")
    assert r.status_code == 422 and "unknown node" in r.json()["detail"]


def test_adjustment_needs_a_reason_and_keeps_the_original(client):
    assert post(client, PRIYA, "adjust", SCHC1, new_value=151300).status_code == 422
    r = adjust(client)
    assert r.status_code == 201
    ev = r.json()
    assert ev["actor"] == PRIYA and ev["role"] == "preparer" and ev["target"] == SCHC1
    assert client.get("/api/lines/SchC.1").json()  # packet still serves the engine's 163,700 untouched


def test_verification_method_comes_from_firm_standards(client):
    assert post(client, PRIYA, "verify", "ev:ev-0016", method="eyeballed").status_code == 422
    assert post(client, PRIYA, "verify", "ev:ev-0016", method="agreed_to_source_document").status_code == 201


def test_judgment_records_authority(client):
    assert post(client, DANIEL, "judgment", "line:v3:SchE.14A", kind="judgment",
                decision="capitalize HVAC").status_code == 422
    assert post(client, DANIEL, "judgment", "line:v3:SchE.14A", kind="judgment", decision="capitalize HVAC",
                authority="Treas. Reg. 1.263(a)-3(k): replacement of a major component").status_code == 201


# ------------------------------------------------------------------ roles
def test_client_cannot_adjust(client):
    r = adjust(client, actor=NGOZI)
    assert r.status_code == 403


def test_only_reviewers_write_review_notes(client):
    assert post(client, PRIYA, "review_note", SCHC1, text="tie to 1099s", blocking=True).status_code == 403
    assert post(client, SAM, "review_note", SCHC1, text="tie to 1099s", blocking=True).status_code == 201
    assert post(client, JO, "adjust", SCHC1, new_value=1, reason="x").status_code == 403


def test_signoff_level_is_capped_by_role(client):
    assert post(client, PRIYA, "signoff", SCHC1, level="reviewer").status_code == 403
    assert post(client, PRIYA, "signoff", SCHC1, level="preparer").status_code == 201
    assert post(client, DANIEL, "signoff", SCHC1, level="reviewer").status_code == 201
    assert post(client, HELEN, "signoff", SCHC1, level="partner").status_code == 201


def test_no_self_review(client):
    assert adjust(client, actor=DANIEL).status_code == 201
    r = post(client, DANIEL, "signoff", SCHC1, level="reviewer")
    assert r.status_code == 403 and "prepared" in r.json()["detail"]
    assert post(client, HELEN, "signoff", SCHC1, level="reviewer").status_code == 201


# ------------------------------------------------------------------ undo, notes, questions
def test_undo_appends_and_flags(client):
    ev = adjust(client).json()
    assert post(client, MARCUS, "undo", None, event_id=ev["id"]).status_code == 403  # not the author
    u = post(client, PRIYA, "undo", None, event_id=ev["id"])
    assert u.status_code == 201 and u.json()["target"] == SCHC1  # inherits the target
    log = client.get("/api/events", params={"target": SCHC1}).json()
    assert [e["type"] for e in log] == ["adjust", "undo"] and log[0]["undone"] is True
    assert post(client, PRIYA, "undo", None, event_id=ev["id"]).status_code == 422  # already undone


def test_undoing_your_adjustment_lifts_the_self_review_block(client):
    ev = adjust(client, actor=DANIEL).json()
    post(client, DANIEL, "undo", None, event_id=ev["id"])
    assert post(client, DANIEL, "signoff", SCHC1, level="reviewer").status_code == 201


def test_review_note_resolution(client):
    note = post(client, DANIEL, "review_note", SCHC1, text="Tie gross receipts to 1099s", blocking=True).json()
    assert post(client, PRIYA, "resolve_note", None, event_id=note["id"]).status_code == 403
    r = post(client, DANIEL, "resolve_note", None, event_id=note["id"], text="Tied: 142,000 + 9,300")
    assert r.status_code == 201 and r.json()["target"] == SCHC1


def test_client_answer_lands_on_the_question_target(client):
    q = post(client, PRIYA, "question", "line:v3:Sch1.17", to=NGOZI,
             text="Was Erik eligible for coverage through your employer?").json()
    a = post(client, NGOZI, "answer", None, event_id=q["id"], text="Yes, both employers offered family coverage.")
    assert a.status_code == 201 and a.json()["target"] == "line:v3:Sch1.17"
    assert post(client, NGOZI, "answer", None, event_id=999).status_code == 422


# ------------------------------------------------------------------ bulk, changes, persistence
def test_batch_is_all_or_nothing(client):
    ok = {"type": "verify", "target": "ev:ev-0016", "payload": {"method": "agreed_to_source_document"}}
    bad = {"type": "verify", "target": "ev:ev-0035", "payload": {"method": "nope"}}
    r = client.post("/api/events/batch", headers={"X-Actor": PRIYA}, json={"events": [ok, bad]})
    assert r.status_code == 422 and client.get("/api/events").json() == []
    r = client.post("/api/events/batch", headers={"X-Actor": PRIYA}, json={"events": [ok, dict(ok, target="ev:ev-0035")]})
    body = r.json()
    assert r.status_code == 201 and len({e["batch_id"] for e in body["events"]}) == 1


def test_what_changed_since_i_last_looked(client):
    adjust(client)
    post(client, PRIYA, "note", SCHC1, text="see D15 p3")
    mine = client.get("/api/me/changes", headers={"X-Actor": DANIEL}).json()
    assert mine["count"] == 2
    assert client.get("/api/me/changes", headers={"X-Actor": PRIYA}).json()["count"] == 0  # own work excluded
    client.post("/api/me/seen", headers={"X-Actor": DANIEL}, json={"event_id": mine["events"][-1]["id"]})
    assert client.get("/api/me/changes", headers={"X-Actor": DANIEL}).json()["count"] == 0


def test_events_survive_a_restart(db_url):
    with TestClient(create_app(str(packet_path()), db_url)) as c:
        adjust(c)
    with TestClient(create_app(str(packet_path()), db_url)) as c:
        assert [e["type"] for e in c.get("/api/events").json()] == ["adjust"]


# ------------------------------------------------------------------ live
def test_stream_replays_missed_then_delivers_live():
    async def run():
        broker = Broker()
        missed = [{"id": 1, "type": "note"}]
        gen = stream(broker, lambda: missed, heartbeat=5)
        first = await gen.__anext__()
        assert first.startswith("id: 1\nevent: note\n")
        nxt = asyncio.ensure_future(gen.__anext__())
        await asyncio.sleep(0)
        broker.publish({"id": 1, "type": "note"})          # already replayed: skipped
        broker.publish({"id": 2, "type": "adjust"})
        second = await asyncio.wait_for(nxt, 2)
        assert second.startswith("id: 2\nevent: adjust\n")
        await gen.aclose()
        assert broker.subscribers == 0

    asyncio.run(run())


def test_stream_ends_when_the_server_stops():
    """An open SSE stream must not hold the server open on shutdown or --reload."""
    import threading

    async def run():
        stopping = threading.Event()
        broker = Broker()
        gen = stream(broker, lambda: [], heartbeat=60, stopping=stopping)
        nxt = asyncio.ensure_future(gen.__anext__())
        await asyncio.sleep(0.1)
        stopping.set()
        with pytest.raises(StopAsyncIteration):
            await asyncio.wait_for(nxt, 2)
        assert broker.subscribers == 0

    asyncio.run(run())


def test_exit_signal_sets_the_stop_flag_and_still_reaches_the_server():
    import signal
    from app import live

    seen = []
    prev_term = signal.signal(signal.SIGTERM, lambda s, f: seen.append(s))  # stands in for uvicorn's handler
    prev_int = signal.getsignal(signal.SIGINT)
    try:
        live.install_exit_signal_hook()
        signal.getsignal(signal.SIGTERM)(signal.SIGTERM, None)
        assert live.SHUTTING_DOWN.is_set() and seen == [signal.SIGTERM]
    finally:
        signal.signal(signal.SIGTERM, prev_term)
        signal.signal(signal.SIGINT, prev_int)
        live.SHUTTING_DOWN.clear()
