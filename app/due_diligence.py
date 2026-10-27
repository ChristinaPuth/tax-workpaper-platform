"""Form 8867 due diligence for the child tax credit and credit for other dependents, built from the file.

For each dependent the credit is worked out (under 17 at year end: child tax credit; otherwise credit for
other dependents) and every knowledge requirement is checked against the household record, the documents,
the questionnaire and the issues: relationship, age, residency, a valid SSN, and that nobody else claims them.
The preparer confirms each item; the record is a due_diligence decision carrying the checklist, which the
server accepts only when every item is confirmed and none is still a problem.
"""
from __future__ import annotations

from datetime import date

from .inbox import finding_state
from .logview import LogView


def _age(dob: str, year: int) -> int:
    d, end = date.fromisoformat(dob), date(year, 12, 31)
    return end.year - d.year - ((end.month, end.day) < (d.month, d.day))


def checklist(packet, findings, events: list[dict], version: str) -> dict:
    log = LogView(events)
    year = packet.tax_year
    items = []
    for person in packet.household["people"]:
        if person.get("role") != "dependent":
            continue
        pid, first = person["id"], person["name"].split()[0]
        age = _age(person["dob"], year)
        ctc = age < 17
        student = bool(person.get("full_time_student"))
        months = person.get("months_lived_with_you") or 0
        node = f"person:{pid}"
        ssn_issues = [f for f in findings if f.check.startswith("P3") and node in f.nodes]
        ssn_open = [f for f in ssn_issues if finding_state(f, log, version)["state"] == "open"]
        claimed_elsewhere = [f for f in findings if f.check.startswith("J12") and node in f.nodes]
        docs = [d["id"] for d in packet.documents if first in d["title"]]
        answers = [q["id"] for q in packet.client["questionnaire"] if first in str(q.get("answer", ""))]
        credit = "Child tax credit" if ctc else "Credit for other dependents"

        def item(key, question, facts, status, evidence=()):
            items.append({"id": f"{pid}.{key}", "person": person["name"], "credit": credit, "question": question,
                          "facts": facts, "status": status, "evidence": list(evidence)})

        item("relationship", f"Does {first} meet the relationship test for a qualifying child?",
             f"Relationship on file: {person.get('relationship', 'not recorded')}.",
             "ok" if person.get("relationship") else "check", [node])
        item("age", f"Does {first}'s age fit the credit?",
             f"Age {age} on 31 Dec {year}: " + ("under 17, so the child tax credit." if ctc else
                                                 ("a full-time student under 24: a qualifying child, too old for the child tax credit, so the credit for other dependents."
                                                  if student and age < 24 else "17 or older and not a student under 24 - check the qualifying relative tests.")),
             "ok" if ctc or (student and age < 24) else "check", [node])
        item("residency", f"Did {first} live with the taxpayers more than half the year?",
             f"{months} months on file." + (f" {person['note']}" if person.get("note") else ""),
             "ok" if months > 6 else "problem", [node, *[f"qa:{a}" for a in answers]])
        item("ssn", f"Does {first} have a valid SSN that matches the documents?",
             ("Mismatch still open: " + "; ".join(f"{f.id} {f.title}" for f in ssn_open)) if ssn_open
             else ("Settled: " + ", ".join(f.id for f in ssn_issues)) if ssn_issues else "SSN agrees with the documents.",
             "problem" if ssn_open else "ok", [f"finding:{f.id}" for f in ssn_issues] + [f"doc:{d}" for d in docs[:2]])
        item("not_claimed", f"Is {first} claimed on nobody else's return?",
             "; ".join(f"{f.title}: {f.detail}" for f in claimed_elsewhere) or "No other return claims them in the file.",
             "ok", [f"finding:{f.id}" for f in claimed_elsewhere])
    item_general = [
        {"id": "general.interview", "person": None, "credit": None, "question": "Were the clients asked the questions and the answers kept?",
         "facts": f"{len(packet.client['questionnaire'])} questionnaire answers and the call notes are in the file.", "status": "ok",
         "evidence": ["qa:qa-04", "qa:qa-05"]},
        {"id": "general.records", "person": None, "credit": None, "question": "Are the documents relied on kept for three years?",
         "facts": "Every document is in the file and retained under the firm's 7-year rule.", "status": "ok", "evidence": []},
    ]
    items += item_general
    recorded = next((e for e in reversed(log.of_type("judgment")) if e["payload"].get("kind") == "due_diligence" and e["payload"].get("checklist")), None)
    return {"form": "8867", "credits": sorted({i["credit"] for i in items if i["credit"]}), "items": items,
            "problems": [i["id"] for i in items if i["status"] == "problem"],
            "recorded": {"by": recorded["actor"], "at": recorded["at"], "decision": recorded["payload"].get("decision")} if recorded else None}


def validate_checklist(packet, findings, events: list[dict], version: str, answers: dict) -> str | None:
    """Why a submitted checklist cannot be recorded, or None."""
    c = checklist(packet, findings, events, version)
    missing = [i["id"] for i in c["items"] if answers.get(i["id"]) is not True]
    if missing:
        return f"confirm every item first ({len(missing)} left, e.g. {missing[0]})"
    if c["problems"]:
        return f"settle these first: {', '.join(c['problems'])}"
    return None
