"""Invariants for the index and regression tests for the errors found in the delivered packet.

    python -m pytest -q
"""
from pathlib import Path

import pytest

from workpaper.checks import run_all
from workpaper.index import Index
from workpaper.packet import Packet, packet_path

PACKET = packet_path()


@pytest.fixture(scope="module")
def p():
    return Packet.load(PACKET)


@pytest.fixture(scope="module")
def ix(p):
    return Index(p)


@pytest.fixture(scope="module")
def ctx(p, ix):
    return run_all(p, ix)


# ---------------------------------------------------------------- index
def test_every_reference_resolves(ix):
    assert ix.unresolved == []


def test_every_extracted_value_points_to_a_page(p, ix):
    for e in p.extracted_values:
        assert ix.targets(f"ev:{e['id']}", "read_from") == [f"page:{e['document_id']}#{e['page']}"]


def test_trace_down_reaches_documents(ix):
    tree = ix.trace_line("v3", "F1040.1a")
    assert {s["document"] for s in tree["sources"]} == {"D08", "D09"}


def test_trace_up_from_document_value(ix):
    lines = ix.lines_fed_by("ev:ev-0315", "v3")  # mileage page 2 total
    assert "line:v3:SchC.9" in lines and "line:v3:F1040.11" in lines


def test_every_document_has_a_landing_status(p, ix):
    for d in p.documents:
        assert ix.document_landing(d["id"])["status"] in {
            "used", "superseded", "not_extracted", "explained_in_note", "used_without_line_link", "unused"}


def test_same_line_links_versions(ix):
    assert "line:v2:F1040.11" in ix.targets("line:v3:F1040.11", "same_line")


# ---------------------------------------------------------------- engine independence
def test_engine_math_recomputes(ctx):
    verified = {v["what"].split(" on ")[0] for v in ctx.verified}
    assert "Schedule D tax worksheet" in verified
    assert not [f for f in ctx.findings if f.check.startswith(("R1", "R2", "R3", "R4", "R5"))]


# ---------------------------------------------------------------- known errors in the packet
EXPECTED = {
    "X1-identifier-not-printed": "D62",
    "X5-duplicate-page-counted-twice": "SchC.44a",
    "X6-partial-extraction": "M18",
    "X8-same-income-two-documents": "7731",
    "R6-fx-rate-period": "SchB.1.6",
    "J1-supplemental-basis-not-applied": "RSU",
    "J2-card-receipts-already-in-books": "1099-K",
    "J3-sehi-eligible-for-employer-plan": "Sch1.17",
    "J4-repair-is-an-improvement": "HVAC",
    "J5-vehicle-donation-limited-to-proceeds": "1098-C",
    "J6-purchase-year-property-tax": "6,912",
    "J7-interest-counted-twice": "2,150",
    "J9-state-source-wages-after-move": "Texas",
    "P1-federal-payments-vs-transcript": "12,000",
    "P2-california-payments-vs-ftb": "10,500",
    "P3-identity-vs-documents": "Theo",
}


@pytest.mark.parametrize("check_id,needle", EXPECTED.items())
def test_known_error_is_found(ctx, check_id, needle):
    hits = [f for f in ctx.findings if f.check == check_id and f.severity == "error" and needle in f.title]
    assert hits, f"{check_id} should report an error mentioning {needle!r}"


def test_errors_carry_corrections_and_effects(ctx):
    for f in ctx.findings:
        if f.severity == "error":
            assert f.corrections, f.id
            assert f.federal_effect is not None and f.california_effect is not None, f.id


def test_resolved_low_confidence_is_downgraded(ctx):
    f = next(f for f in ctx.findings if "ev:ev-1049" in f.nodes and f.check.startswith("X4"))
    assert f.severity == "info" and "msg:msg-08" in f.evidence
