"""Replay: the file as it stood on a date, from the packet's record of the season."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from workpaper.packet import packet_path

PRIYA, NGOZI = "st-01", "cu-01"


@pytest.fixture()
def c(tmp_path):
    with TestClient(create_app(str(packet_path()), f"sqlite:///{tmp_path / 'r.db'}")) as client:
        yield client


def at(c, day):
    r = c.get("/api/replay", params={"at": day}, headers={"X-Actor": PRIYA})
    assert r.status_code == 200
    return r.json()


def test_rejected_then_fixed_then_accepted(c):
    d = at(c, "2026-07-13")
    assert d["stage"].startswith("E-file rejected")
    assert d["filing_status"] == {"federal": "rejected", "california": "not_transmitted"}
    rejected = next(a for a in d["alerts"] if a["kind"] == "rejected")
    assert "R0000-504-02" in rejected["text"] and rejected["findings"] == ["F-034"]   # Theo's SSN
    d = at(c, "2026-07-15")
    assert d["filing_status"] == {"federal": "accepted", "california": "accepted"} and not d["alerts"]


def test_the_file_grows_over_the_season(c):
    early, mid = at(c, "2026-01-15"), at(c, "2026-04-16")
    assert early["version"] is None and mid["version"]["version"] == "v2"
    assert early["documents"]["received"] < mid["documents"]["received"]
    assert mid["stage"].startswith("Extended") and mid["transcript"]["as_of"] == "2026-03-12"


def test_the_2028_examination_letter_shows_what_to_answer(c):
    d = at(c, "2028-01-27")
    notice = next(a for a in d["alerts"] if a["kind"] == "notice")
    assert notice["document"] == "D72" and any("Form 8283" in x for x in notice["items"])


def test_signature_pins_are_masked_and_clients_are_kept_out(c):
    details = [t["detail"] for t in at(c, "2026-07-11")["timeline"] if t["detail"]]
    assert not any("41207" in x or "88310" in x for x in details)
    assert c.get("/api/replay", headers={"X-Actor": NGOZI}).status_code == 403
    assert c.get("/api/replay", params={"at": "July"}, headers={"X-Actor": PRIYA}).status_code == 422
