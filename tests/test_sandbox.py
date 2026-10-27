"""Public demo mode: each visitor works on their own copy, kept across reloads, invisible to others."""
from __future__ import annotations

import os
import time

import pytest
from fastapi.testclient import TestClient

from app import sandbox
from app.live import Broker
from app.main import create_app
from workpaper.packet import packet_path

A, B = "aaaaaaaa1111", "bbbbbbbb2222"


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("SANDBOX_PER_VISITOR", "1")
    monkeypatch.setenv("SANDBOX_DIR", str(tmp_path / "boxes"))
    return tmp_path


def client(tmp_path):
    return TestClient(create_app(str(packet_path()), f"sqlite:///{tmp_path / 'shared.db'}"))


def note(c, box, text="hello"):
    return c.post("/api/events", headers={"X-Actor": "st-01", "X-Sandbox": box},
                  json={"type": "note", "target": "doc:D06", "payload": {"text": text}})


def notes(c, box=None):
    h = {"X-Actor": "st-01", **({"X-Sandbox": box} if box else {})}
    return [e["payload"]["text"] for e in c.get("/api/events?type=note", headers=h).json()]


def test_visitors_do_not_see_each_others_work(env):
    with client(env) as c:
        assert c.get("/api/overview").json()["sandboxed"] is True
        assert note(c, A, "from A").status_code == 201
        assert notes(c, A) == ["from A"]
        assert notes(c, B) == []                       # a new visitor starts from the packet as delivered
        assert notes(c) == []                          # nor does it touch the shared database


def test_a_visitors_copy_survives_a_restart(env):
    with client(env) as c:
        note(c, A, "kept")
    with client(env) as c:
        assert notes(c, A) == ["kept"]


def test_a_bad_sandbox_id_is_refused(env):
    with client(env) as c:
        r = c.get("/api/events", headers={"X-Actor": "st-01", "X-Sandbox": "../../etc"})
        assert r.status_code == 400


def test_old_and_surplus_sandboxes_are_removed(env, monkeypatch):
    monkeypatch.setenv("SANDBOX_MAX", "2")
    with client(env) as c:
        for box in ("box00000001", "box00000002"):
            note(c, box)
        folder = env / "boxes"
        old = time.time() - 3600
        os.utime(folder / "box00000001.db", (old, old))
        note(c, "box00000003")                         # creating a third drops the oldest
        assert sorted(f.stem for f in folder.glob("*.db")) == ["box00000002", "box00000003"]


def test_live_updates_stay_inside_a_sandbox(tmp_path):
    boxes = sandbox.Sandboxes(shared=None, folder=tmp_path)  # type: ignore[arg-type]
    proxy = sandbox.BrokerProxy(boxes)
    token = sandbox.CURRENT.set(A)
    q = proxy.subscribe()
    sandbox.CURRENT.reset(token)
    token = sandbox.CURRENT.set(B)
    proxy.publish({"id": 1, "type": "note"})
    sandbox.CURRENT.reset(token)
    assert q.empty() and isinstance(boxes.broker(), Broker)


def test_without_demo_mode_everyone_shares_one_workpaper(tmp_path, monkeypatch):
    monkeypatch.delenv("SANDBOX_PER_VISITOR", raising=False)
    with client(tmp_path) as c:
        assert c.get("/api/overview").json()["sandboxed"] is False
        note(c, A, "shared")
        assert notes(c, B) == ["shared"]
