"""Per-person settings: simple / expert defaults from the staff records, changes kept per person, quick start
ticked from what the person did."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from workpaper.packet import packet_path

PRIYA, DANIEL, MARCUS, NGOZI = "st-01", "st-02", "st-04", "cu-01"


@pytest.fixture()
def c(tmp_path):
    with TestClient(create_app(str(packet_path()), f"sqlite:///{tmp_path / 's.db'}")) as client:
        yield client


def settings(c, who):
    return c.get("/api/me/settings", headers={"X-Actor": who}).json()


def test_new_staff_start_simple_with_the_quick_start_experienced_staff_expert(c):
    m = settings(c, MARCUS)
    assert m["settings"] == {"mode": "simple", "glossary": True, "quick_start": True}
    assert "2026-03-24" in m["reason"]
    assert settings(c, DANIEL)["settings"]["mode"] == "expert"
    assert settings(c, PRIYA)["settings"]["mode"] == "expert"           # 10 months in: past the six-month window
    assert settings(c, NGOZI)["quick_start"] == []


def test_choices_are_kept_per_person_and_can_be_reset(c):
    r = c.patch("/api/me/settings", headers={"X-Actor": MARCUS}, json={"mode": "expert"}).json()
    assert r["settings"]["mode"] == "expert" and r["changed"] == ["mode"]
    assert settings(c, PRIYA)["settings"]["mode"] == "expert" and settings(c, MARCUS)["settings"]["mode"] == "expert"
    assert c.patch("/api/me/settings", headers={"X-Actor": MARCUS}, json={"mode": "loud"}).status_code == 422
    assert c.delete("/api/me/settings", headers={"X-Actor": MARCUS}).json()["settings"]["mode"] == "simple"


def test_quick_start_ticks_from_visits_and_own_work(c):
    steps = lambda: {s["id"]: s["done"] for s in settings(c, MARCUS)["quick_start"]}
    assert not any(steps().values())
    c.patch("/api/me/settings", headers={"X-Actor": MARCUS}, json={"visited": ["inbox", "search"]})
    c.post("/api/events", headers={"X-Actor": PRIYA},  # someone else's work does not tick Marcus's steps
           json={"type": "question", "target": "line:v3:SchC.1", "payload": {"to": "cu-01", "text": "?"}})
    assert steps() == {"inbox": True, "trace": False, "search": True, "fix": False, "ask": False, "filing": False}
    c.post("/api/events", headers={"X-Actor": MARCUS},
           json={"type": "question", "target": "line:v3:SchC.1", "payload": {"to": "cu-01", "text": "Books total?"}})
    assert steps()["ask"]
    assert c.patch("/api/me/settings", headers={"X-Actor": MARCUS}, json={"visited": ["nowhere"]}).status_code == 422


def test_reviewers_get_a_review_step(c):
    assert "review" in {s["id"] for s in settings(c, DANIEL)["quick_start"]}
    assert "review" not in {s["id"] for s in settings(c, MARCUS)["quick_start"]}
