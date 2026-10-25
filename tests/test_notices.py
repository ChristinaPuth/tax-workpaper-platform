"""Answering a notice: the evidence pack built from the notice text and the record."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from workpaper.packet import packet_path

PRIYA, MARCUS, NGOZI = "st-01", "st-04", "cu-01"
NOTICE = "N-2025-L566"


@pytest.fixture()
def c(tmp_path):
    with TestClient(create_app(str(packet_path()), f"sqlite:///{tmp_path / 'n.db'}")) as client:
        yield client


def pack(c):
    return c.get(f"/api/notices/{NOTICE}/pack", headers={"X-Actor": PRIYA}).json()


def test_each_item_finds_its_lines_documents_and_issues(c):
    charity, receipts = pack(c)["items"]
    assert [l["key"] for l in charity["lines"]] == ["SchA.12", "F8283.A1.vehicle", "F8283.A1.stock"]
    assert {"D65", "D66"} <= {d["id"] for d in charity["documents"]}          # the 1098-C comes from the issue's evidence
    assert "F-018" in {t["finding"] for t in charity["issues"]} and "qa-39" in charity["client"]
    assert [l["key"] for l in receipts["lines"]] == ["SchC.1"]


def test_amounts_in_the_notice_are_reconciled_to_source_documents(c):
    recon = {r["amount"]: r for r in pack(c)["items"][1]["reconciliation"]}
    assert recon[142000]["agrees"] and recon[142000]["documents"] == ["D16", "D17", "D18", "D19", "D20"]
    assert recon[12400]["agrees"] and recon[12400]["documents"] == ["D21"]


def test_the_settlement_of_an_issue_is_in_the_trail(c):
    c.post("/api/events", headers={"X-Actor": PRIYA}, json={"type": "adjust", "target": "line:v3:F8283.A1.vehicle",
           "payload": {"new_value": 2900, "reason": "1098-C box 4c: sold for 2,900"}})
    charity = pack(c)["items"][0]
    vehicle = next(l for l in charity["lines"] if l["key"] == "F8283.A1.vehicle")
    assert vehicle["as_filed"] == 2900 and vehicle["engine"] == 6000
    trail = next(t for t in charity["issues"] if t["finding"] == "F-018")
    assert trail["state"] == "adjusted" and trail["history"][0]["new_value"] == 2900


def test_the_export_is_masked_without_clearance_and_logged_with_it(c):
    masked = c.get(f"/api/notices/{NOTICE}/pack.html", headers={"X-Actor": MARCUS})
    assert masked.status_code == 200 and "attachment" in masked.headers["content-disposition"]
    assert "666-" not in masked.text
    plain = c.get(f"/api/notices/{NOTICE}/pack.html", headers={"X-Actor": PRIYA})
    assert "142,000" in plain.text
    assert [e["target"] for e in c.get("/api/sensitive/log", headers={"X-Actor": PRIYA}).json()] == [f"notice:{NOTICE}"]
    assert c.get(f"/api/notices/{NOTICE}/pack.html", headers={"X-Actor": NGOZI}).status_code == 403
    assert c.get("/api/notices/nope/pack", headers={"X-Actor": PRIYA}).status_code == 404
