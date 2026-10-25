"""Replay the season: the file as it stood on any date, from the packet's own record.

As of a date: what had happened (timeline), which documents had arrived, which engine version was current,
e-file submissions and their results, the IRS account as last pulled, notices received, and the deadlines
passed or coming. Alerts say what needed attention then - an e-file rejection points to the issue that
explains it. Nothing here depends on the event log: the packet is the record of the season.
"""
from __future__ import annotations

from datetime import date

STAGES = [  # (timeline event, what the file is doing from then on)
    ("engagement_signed", "Engaged - waiting for documents"),
    ("client_marked_upload_complete", "Documents in - first computation"),
    ("work_started", "Being prepared"),
    ("extension_filed_with_payment", "Extended to 15 October - still being prepared"),
    ("client_approved_and_signed_8879", "Approved by the clients - ready to e-file"),
    ("efile_rejected", "E-file rejected - fixing"),
    ("efile_accepted_federal", "Filed - federal accepted"),
    ("efile_accepted_california", "Filed and accepted (federal and California)"),
    ("next_year_engagement_started", "Filed - next year's return started"),
    ("notice_received", "Under IRS examination"),
]


def _d(s: str) -> str:
    return s[:10]


def key_dates(packet) -> list[dict]:
    out = [{"date": _d(t["at"]), "label": t["event"].replace("_", " ")} for t in packet.raw["timeline"]]
    out += [{"date": d["date"], "label": d["what"]} for d in packet.firm["deadlines"]]
    seen, dates = set(), []
    for x in sorted(out, key=lambda x: x["date"]):
        if x["date"] not in seen:
            seen.add(x["date"])
            dates.append(x)
    return dates


def state_at(packet, findings, at: str) -> dict:
    date.fromisoformat(at)  # raises ValueError for a bad date
    raw = packet.raw
    tl = [t for t in raw["timeline"] if _d(t["at"]) <= at]
    stage = next((label for ev, label in reversed(STAGES) if any(t["event"] == ev for t in tl)), "Before the engagement")
    docs = [d for d in packet.documents if _d(d["received_at"]) <= at]
    versions = [v for v in packet.versions if _d(v["computed_at"]) <= at]
    current = versions[-1] if versions else None
    efile = [e for e in raw["tax_agency_records"]["efile"] if _d(e["date"]) <= at]
    status = {}
    for e in efile:
        status[e["jurisdiction"]] = e["status"]
    transcripts = [t for t in raw["tax_agency_records"]["irs_account_transcript_2025"] if t["as_of"] <= at]
    notices = [n for n in raw["tax_agency_records"]["notices"] if n["dated"] <= at and n["tax_year"] == packet.tax_year]

    alerts = []
    deadlines = []
    for d in packet.firm["deadlines"]:
        deadlines.append({**d, "passed": d["date"] < at})
    if at > "2026-04-15" and not any(t["event"] == "extension_filed_with_payment" for t in tl) and "accepted" not in status.values():
        alerts.append({"kind": "deadline", "text": "The original due date has passed with no extension."})
    last_fed = next((e for e in reversed(efile) if e["jurisdiction"] == "federal"), None)
    if last_fed and last_fed["status"] == "rejected":
        for err in last_fed.get("errors", []):
            related = [f.id for f in findings if f.check.startswith("P3") and any(
                part in err["message"] for part in f.title.split(":")[0].split(" ") if len(part) > 4)]
            alerts.append({"kind": "rejected", "text": f"{err['code']}: {err['message']}", "findings": related})
    for n in notices:
        if n.get("response_due", "") >= at:
            alerts.append({"kind": "notice", "text": f"{n['type']} - response due {n['response_due']}",
                           "document": n.get("document"), "items": n.get("items_under_examination", [])})
    upcoming = [x for x in key_dates(packet) if x["date"] > at][:3]
    return {
        "at": at, "stage": stage,
        "timeline": [{"date": _d(t["at"]), "event": t["event"].replace("_", " "), "actor": t.get("actor"),
                      "detail": t.get("detail"), "refs": t.get("refs", [])} for t in tl],
        "documents": {"received": len(docs), "of": len(packet.documents),
                      "latest": [{"id": d["id"], "title": d["title"], "received": _d(d["received_at"])}
                                 for d in sorted(docs, key=lambda d: d["received_at"])[-5:]]},
        "version": {"version": current["version"], "computed_at": _d(current["computed_at"]), "trigger": current["trigger"],
                    "summary": current["summary"]} if current else None,
        "efile": [{"date": _d(e["date"]), "jurisdiction": e["jurisdiction"], "status": e["status"],
                   "submission_id": e["submission_id"], "errors": e.get("errors", [])} for e in efile],
        "filing_status": status,
        "transcript": transcripts[-1] if transcripts else None,
        "notices": notices, "alerts": alerts, "deadlines": deadlines, "upcoming": upcoming,
    }
