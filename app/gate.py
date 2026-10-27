"""The filing gate: the firm's twelve required steps and everything else that blocks filing.

Nothing here is ticked by hand. Each step's status is derived from the packet, the findings and the
event log, and says what is left and where to go. Blocking review notes, unreviewed changes, changes
over the partner threshold without a partner, open errors and reopened sign-offs block filing too.
"""
from __future__ import annotations

from workpaper.working import WorkingReturn

from .inbox import PARTNER_THRESHOLD, finding_state
from .logview import LogView, filing_status

DONE, OPEN, LATER = "done", "open", "later"


def _family(f) -> str:
    return f.check.split("-")[0]


def _settled(st: dict) -> bool:
    return st["state"] != "open"


def _step(n: int, title: str, status: str, detail: str, links: list[str] | None = None,
          progress: tuple[int, int] | None = None) -> dict:
    return {"n": n, "title": title, "status": status, "detail": detail, "links": links or [],
            "progress": {"done": progress[0], "total": progress[1]} if progress else None}


def _findings_step(n: int, title: str, fs: list, states: dict, done_text: str, todo_text: str) -> dict:
    total = len(fs)
    settled = sum(1 for f in fs if _settled(states[f.id]))
    if settled == total:
        return _step(n, title, DONE, done_text, progress=(settled, total) if total else None)
    open_ids = [f.id for f in fs if not _settled(states[f.id])]
    return _step(n, title, OPEN, f"{total - settled} of {total} still open. {todo_text}",
                 links=[f"finding:{i}" for i in open_ids[:20]], progress=(settled, total))


def build_gate(*, packet, index, findings, events: list[dict], working: WorkingReturn, signoffs: list[dict],
               people: dict | None = None) -> dict:
    name = lambda pid: people[pid].name if people and pid in people else pid
    version = working.version
    log = LogView(events)
    states = {f.id: finding_state(f, log, version) for f in findings}
    ret = f"ver:{version}"

    def by(*families: str, severities=("error", "warning")) -> list:
        return [f for f in findings if _family(f) in families and f.severity in severities]

    def valid_return_signoff(level: str) -> dict | None:
        cands = [s for s in signoffs if s["target"] == ret and s["level"] == level]
        valid = [s for s in cands if s["valid"]]
        return (valid or cands or [None])[-1]

    steps = []
    signed = [e for e in packet.extracted_values if e["document_id"] in ("D01", "D02") and "sign" in e["field"]]
    steps.append(_step(1, "Engagement letter and consents signed", DONE if signed else OPEN,
                       "Engagement letter and section 7216 consent signed by both spouses (D01, D02)." if signed
                       else "No signed engagement letter in the file.", ["doc:D01", "doc:D02"]))
    steps.append(_findings_step(2, "Identity verified", by("P3"), states,
                                "Names and SSNs agree with the identity documents (D04, D05, D71).",
                                "Correct the identification number from the documents and record it."))
    d06 = [e for e in log.by_target.get("doc:D06", []) if e["type"] == "verify"]
    steps.append(_step(3, "Prior-year return reviewed", DONE if d06 else OPEN,
                       f"2024 return reviewed ({d06[-1]['payload'].get('method')})." if d06
                       else "Open D06 (2024 return) and mark it verified - agreed to prior year.", ["doc:D06"]))
    steps.append(_findings_step(4, "All documents accounted for", by("P6"), states,
                                "Every document is used, superseded or explained.",
                                "Record why each unused document is not needed, or use it."))
    steps.append(_findings_step(5, "Prior-year variances explained", by("P5"), states,
                                "Every line over the firm threshold has an explanation or a correction.",
                                "Explain each change, or correct it."))
    steps.append(_findings_step(6, "Carryovers agreed to prior year", by("P4"), states,
                                "Carryovers agree with the 2024 return (independent check P4 found no differences).",
                                "Reconcile each carryover to the 2024 return."))
    steps.append(_findings_step(7, "Estimated payments agreed to IRS and FTB records", by("P1", "P2"), states,
                                "Payments agree with the IRS transcript and the FTB account.",
                                "Use the agency records."))
    # only the Form 8867 checklist counts (the server accepts it only complete and with no problem left)
    dd = [e for e in log.of_type("judgment") if e["payload"].get("kind") == "due_diligence" and e["payload"].get("checklist")]
    steps.append(_step(8, "Due diligence completed", DONE if dd else OPEN,
                       f"Due diligence recorded: {dd[-1]['payload'].get('decision')}" if dd
                       else "Complete the Form 8867 checklist for the child tax credit and credit for other dependents.",
                       ["line:v3:F8867.status"]))
    steps.append(_findings_step(9, "Diagnostics resolved", by("P7"), states,
                                "Every engine diagnostic has a recorded disposition.",
                                "Decide how to handle each one and record the decision."))
    for n, level, title in ((10, "reviewer", "Reviewer sign-off"), (11, "partner", "Partner sign-off")):
        s = valid_return_signoff(level)
        if s and s["valid"]:
            steps.append(_step(n, title, DONE, f"Signed by {name(s['actor'])}.", [ret]))
        elif s:
            steps.append(_step(n, title, OPEN, f"Reopened: {s['changed_count']} item(s) changed since "
                                               f"{name(s['actor'])} signed. Sign again after review.", [ret]))
        else:
            steps.append(_step(n, title, OPEN, f"Sign off the whole return at {level} level.", [ret]))
    # married filing jointly: every client on the engagement approves and signs (Form 8879 / FTB 8879)
    clients = [pid for pid, p in (people or {}).items() if p.role == "client"]
    partner_ok = any(s["target"] == ret and s["level"] == "partner" and s["valid"] for s in signoffs)
    approvals = {s["actor"]: s for s in signoffs if s["target"] == ret and s["level"] == "client"}
    held = [c for c in clients if approvals.get(c, {}).get("valid")]
    waiting = [name(c) for c in clients if c not in held]
    if clients and not waiting:
        steps.append(_step(12, "Client approval and e-file authorization", DONE,
                           "Approved and signed electronically (Form 8879, FTB 8879) by "
                           + " and ".join(name(c) for c in clients) + ".", [ret]))
    else:
        reopened = [name(c) for c in clients if c in approvals and not approvals[c]["valid"]]
        detail = ("After the partner signs off, the clients approve the return in their portal and sign Form 8879 "
                  "with their PIN." if not partner_ok
                  else "Waiting for " + " and ".join(waiting) + " to approve and sign in the portal.")
        if reopened:
            detail += f" Approval reopened for {' and '.join(reopened)}: the return changed after they approved."
        steps.append(_step(12, "Client approval and e-file authorization", OPEN, detail, [ret],
                           progress=(len(held), len(clients)) if clients else None))

    blockers = []
    notes = [e for e in log.of_type("review_note") if e["payload"].get("blocking") and e["id"] not in log.resolved_notes]
    for e in notes:
        blockers.append({"kind": "review_note", "title": e["payload"].get("text", ""), "target": e["target"]})
    errors = [f for f in findings if f.severity == "error" and not _settled(states[f.id])]
    if errors:
        blockers.append({"kind": "errors", "title": f"{len(errors)} error(s) not yet corrected or decided",
                         "target": None, "count": len(errors)})
    for a in working.adjustments:
        target = f"line:{version}:{a.key}"
        if not log.signed_after(target, a.event_id, ("reviewer", "partner"), a.actor):
            blockers.append({"kind": "unreviewed", "title": f"{a.key} change not reviewed", "target": target})
        effect = max(abs(a.effect.get("federal") or 0), abs(a.effect.get("california") or 0))
        if effect > PARTNER_THRESHOLD and not log.signed_after(target, a.event_id, ("partner",), a.actor):
            blockers.append({"kind": "partner", "title": f"{a.key} change over {PARTNER_THRESHOLD:,} needs a partner",
                             "target": target})
    from .coverage import BY_HAND, coverage  # here, not at import time: coverage imports inbox like this module
    left = coverage(packet, findings, events, version, signoffs, people or {})["left"]
    if left:
        blockers.append({"kind": "areas", "title": f"{len(left)} of {len(BY_HAND)} areas not yet considered",
                         "target": None, "count": len(left)})
    reopened = [s for s in signoffs if not s["valid"] and s["target"] != ret and s["level"] != "client"]
    if len(reopened) == 1:
        blockers.append({"kind": "reopened", "title": f"Sign-off on {reopened[0]['target'].split(':', 2)[-1]} reopened",
                         "target": reopened[0]["target"]})
    elif reopened:
        blockers.append({"kind": "reopened", "title": f"{len(reopened)} sign-offs reopened - sign again after review",
                         "target": None, "count": len(reopened)})

    fs = filing_status(events)
    filed = fs["filed"]
    required = [s for s in steps if s["status"] != LATER]
    ready = all(s["status"] == DONE for s in required) and not blockers
    return {"ready": ready, "steps": steps, "blockers": blockers,
            "filed": {"at": filed["at"], "by": filed["actor"], "by_name": name(filed["actor"]), "event_id": filed["id"]}
            if filed else None,
            "rejected": {"at": fs["rejected"]["payload"].get("received") or fs["rejected"]["at"], "errors": fs["rejected"]["payload"].get("errors", []),
                         "submission_id": fs["rejected"]["payload"].get("submission_id")} if fs["rejected"] else None,
            "acks": [{"event_id": a["id"], "at": a["at"], "by_name": name(a["actor"]), **a["payload"]} for a in fs["all_acks"]],
            "summary": {"steps_done": sum(1 for s in steps if s["status"] == DONE), "steps_total": len(steps),
                        "blockers": len(blockers)}}
