"""Sensitive data masked for staff and revealed only with clearance (logged); clients kept out of internal work."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from workpaper.packet import packet_path

PRIYA, MARCUS, JO, NGOZI = "st-01", "st-04", "st-05", "cu-01"
H = lambda who: {"X-Actor": who}  # noqa: E731


@pytest.fixture()
def c(tmp_path):
    with TestClient(create_app(str(packet_path()), f"sqlite:///{tmp_path / 's.db'}")) as client:
        yield client


def test_ssns_pins_and_accounts_are_masked_everywhere_for_staff(c):
    for who in (PRIYA, MARCUS, None):
        headers = H(who) if who else {}
        assert "666-74-3309" not in c.get("/api/findings/F-034", headers=headers).text
        assert "•••-••-3309" in c.get("/api/findings/F-034", headers=headers).json()["title"]
    assert c.get("/api/values/ev-0005", headers=H(PRIYA)).json()["extracted"]["text_as_read"] == "••••••"       # IP PIN
    assert c.get("/api/values/ev-0963", headers=H(PRIYA)).json()["extracted"]["text_as_read"].endswith("9901")  # IBAN
    assert "482915" not in c.get("/api/search", params={"q": "PIN"}, headers=H(PRIYA)).text
    assert "666-" not in c.get("/api/labels", headers=H(PRIYA)).text


def test_masking_keeps_page_length_so_highlights_stay_in_place(c):
    masked = c.get("/api/documents/D06/pages/1", headers=H(PRIYA)).json()
    plain = c.post("/api/sensitive/reveal", json={"target": "page:D06#1"}, headers=H(PRIYA)).json()["content"]["printed_content"]
    text = masked["printed_content"]
    assert "•••-••-3390" in text and len(text) == len(plain)
    for f in masked["fields"]:
        if f.get("span"):
            a, b = f["span"]["start"], f["span"]["end"]
            assert "•" in text[a:b] or text[a:b] == plain[a:b]


def test_only_cleared_staff_reveal_and_every_view_is_logged(c):
    assert c.post("/api/sensitive/reveal", json={"target": "person:theo"}, headers=H(MARCUS)).status_code == 403
    assert c.post("/api/sensitive/reveal", json={"target": "person:theo"}, headers=H(NGOZI)).status_code == 403
    r = c.post("/api/sensitive/reveal", json={"target": "person:theo"}, headers=H(PRIYA)).json()
    assert r["content"]["ssn"] == "666-74-3309"
    page = c.post("/api/sensitive/reveal", json={"target": "page:D06#1"}, headers=H(PRIYA)).json()
    assert "666-74-3390" in page["content"]["printed_content"]
    log = c.get("/api/sensitive/log", headers=H(JO)).json()
    assert [(e["actor"], e["target"]) for e in log] == [(PRIYA, "person:theo"), (PRIYA, "page:D06#1")]
    assert c.get("/api/sensitive/log", headers=H(NGOZI)).status_code == 403


def test_clients_see_their_numbers_but_not_the_firms_internal_work(c):
    assert c.get("/api/values/ev-0005", headers=H(NGOZI)).json()["extracted"]["text_as_read"] == "482915"
    for path in ("/api/findings", "/api/events", "/api/reports/areas", "/api/search?q=1", "/api/what-if", "/api/compare"):
        assert c.get(path, headers=H(NGOZI)).status_code == 403, path
    assert c.get("/api/documents/D21", headers=H(NGOZI)).json()["findings"] == []
    assert c.get("/api/gate", headers=H(NGOZI)).json()["blockers"] == []
    assert all(r["finding_id"] is None for s in c.get("/api/reports/summary", headers=H(NGOZI)).json()["sections"] for r in s["rows"])
    assert c.get("/api/inbox", headers=H(NGOZI)).status_code == 200
