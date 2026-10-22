"""API tests: one client loads the packet once (module-scoped, same cost as run_checks.py)."""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from workpaper.packet import packet_path

PACKET = packet_path()


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    app = create_app(str(PACKET), f"sqlite:///{tmp_path_factory.mktemp('db') / 'test.db'}")
    with TestClient(app) as c:
        yield c


def test_overview(client):
    r = client.get("/api/overview")
    assert r.status_code == 200
    body = r.json()
    assert body["latest_version"] == "v3"
    assert body["index_stats"]["unresolved_refs"] == 0
    assert body["documents_total"] == 74
    assert body["findings_total"] > 0


def test_versions(client):
    r = client.get("/api/versions")
    versions = r.json()
    assert [v["version"] for v in versions] == ["v1", "v2", "v3"]


def test_version_lines_and_area_filter(client):
    r = client.get("/api/versions/v3/lines", params={"area": "F1040"})
    lines = r.json()
    assert lines and all(l["form"] == "F1040" for l in lines)


def test_version_lines_unknown_version(client):
    assert client.get("/api/versions/v9/lines").status_code == 404


def test_line_detail(client):
    r = client.get("/api/lines/F1040.1a")
    body = r.json()
    assert body["rule"] == "R-W2-BOX1-SUM"
    assert "R-W2-BOX1-SUM" in body["rule_text"] or body["rule_text"]
    assert "v1" in body["by_version"] and "v3" in body["by_version"]


def test_line_detail_unknown(client):
    assert client.get("/api/lines/NOPE.1").status_code == 404


def test_trace_matches_index(client):
    r = client.get("/api/trace/v3/F1040.1a")
    tree = r.json()
    assert {s["document"] for s in tree["sources"]} == {"D08", "D09"}


def test_trace_unknown_line(client):
    assert client.get("/api/trace/v3/NOPE.1").status_code == 404


def test_impact_upward_trace(client):
    r = client.get("/api/impact/ev:ev-0315")
    body = r.json()
    keys = {l["key"] for l in body["lines_fed"]}
    assert "SchC.9" in keys and "F1040.11" in keys


def test_impact_unknown_node(client):
    assert client.get("/api/impact/ev:nope").status_code == 404


def test_list_documents(client):
    r = client.get("/api/documents")
    docs = r.json()
    assert len(docs) == 74
    d23 = next(d for d in docs if d["id"] == "D23")
    assert d23["landing_status"] == "used"


def test_document_detail(client):
    r = client.get("/api/documents/D23")
    body = r.json()
    assert body["landing"]["status"] == "used"
    assert body["coverage"]["located"] + body["coverage"]["not_located"] == body["landing"]["values"]


def test_document_not_found(client):
    assert client.get("/api/documents/D99").status_code == 404


def test_w2_box3_box5_disambiguated(client):
    """D09 prints '118,000.00' twice (Box 3 and Box 5); each must locate its own span."""
    r = client.get("/api/documents/D09/pages/1")
    fields = {f["ev_id"]: f for f in r.json()["fields"]}
    box3, box5 = fields["ev-0037"], fields["ev-0039"]
    assert box3["span"] is not None and box5["span"] is not None
    assert box3["span"] != box5["span"]


def test_document_page_not_found(client):
    assert client.get("/api/documents/D09/pages/99").status_code == 404


def test_findings_filter_by_severity(client):
    r = client.get("/api/findings", params={"severity": "error"})
    findings = r.json()
    assert findings and all(f["severity"] == "error" for f in findings)


def test_finding_detail(client):
    r = client.get("/api/findings/F-001")
    assert r.json()["check"] == "X1-identifier-not-printed"


def test_finding_not_found(client):
    assert client.get("/api/findings/F-999").status_code == 404


def test_search(client):
    r = client.get("/api/search", params={"q": "1,840"})
    body = r.json()
    assert body["extracted_values"]


def test_lines_carry_finding_flags(client):
    rows = {r["key"]: r for r in client.get("/api/versions/v3/lines").json()}
    assert rows["SchC.1"]["findings"].get("error") == 1          # 1099-K counted twice
    assert rows["SchC.1"]["rule"] == "R-SCHC-GROSS"
    assert rows["F1040.1z"]["findings"] == {}


def test_value_layers_expose_a_misread(client):
    v = client.get("/api/values/ev-1045").json()                # Little Sprouts EIN
    assert v["extracted"]["text_as_read"] == "74-3829516"
    assert v["printed"]["found"] is False                        # the transposed digits are not on the page
    assert [u["key"] for u in v["used"]] == ["F2441.1b"]
    assert any(f["id"] == "F-001" for f in v["findings"])
    ok = client.get("/api/values/ev-0103").json()                # books revenue 151,300
    assert ok["printed"]["text"] == "151,300.00" and ok["used"][0]["key"] == "SchC.1"


def test_node_preview(client):
    n = client.get("/api/nodes/ev:ev-0127").json()
    assert n["kind"] == "extracted_value" and n["document"] == "D21"
    assert client.get("/api/nodes/line:v3:NOPE").status_code == 404


def test_frontend_routes_fall_back_to_the_app_shell(tmp_path, monkeypatch):
    import app.main as main
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<div id=root></div>")
    (tmp_path / "assets" / "app.js").write_text("console.log(1)")
    monkeypatch.setattr(main, "FRONTEND_DIST", tmp_path)
    with TestClient(main.create_app(str(PACKET), f"sqlite:///{tmp_path / 'db.sqlite'}")) as c:
        assert "id=root" in c.get("/documents/D23?page=3").text      # client-side route
        assert c.get("/assets/app.js").text == "console.log(1)"
        assert c.get("/api/overview").json()["latest_version"] == "v3"  # API still wins
        assert c.get("/api/nope").status_code == 404                  # unknown API path is not the shell
