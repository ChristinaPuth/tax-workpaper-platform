"""The Inbox: what this person should do next, worst first, in plain language.

Everyone gets an Inbox; what is in it depends on the role:
  preparer          issues to fix, review notes to address, client replies
  reviewer          changes waiting for review, then issues nobody has handled yet
  partner           changes over the firm's 1,000 tax-effect threshold waiting for partner sign-off
  quality_reviewer  every error and every change, for sampling
  firm_administrator nothing to review (standards and budgets live elsewhere)
  client            questions addressed to them

Each item says what happened, why it matters and what to do, with the estimated tax effect and the
node to open. Checks that fire many times for one reason (prior-year variance, unused documents)
become one item, so the list stays readable on day one.
"""
from __future__ import annotations

from collections import defaultdict

from workpaper.findings import Finding
from workpaper.working import WorkingReturn

from .logview import LogView
from .people import Person

PARTNER_THRESHOLD = 1000  # firm rule: adjustments with a tax effect over 1,000 need partner sign-off
SEVERITY_RANK = {"error": 0, "warning": 1, "info": 2}
GROUPED = {"P5": "prior-year variance", "P6": "documents not used"}

AREAS = {
    "intake": "Intake & identity",
    "wages": "Wages & stock compensation",
    "investments": "Investments & digital assets",
    "business": "Business (Schedule C)",
    "rentals": "Rentals & property sale",
    "passthroughs": "Pass-throughs & basis",
    "deductions": "Deductions & credits",
    "payments": "Payments",
    "california": "California",
    "totals": "Return totals",
}
# Form 1040 and Schedules 1-3 mix every area, so their lines are mapped one by one; other forms by prefix.
_LINE_AREA = {
    "F1040.1a": "wages", "F1040.1z": "wages",
    "F1040.2b": "investments", "F1040.3a": "investments", "F1040.3b": "investments", "F1040.7": "investments",
    "F1040.4a": "deductions", "F1040.4b": "deductions", "F1040.12": "deductions", "F1040.19": "deductions",
    "F1040.20": "deductions", "F1040.13": "business",
    "F1040.8": "totals", "F1040.9": "totals", "F1040.10": "totals", "F1040.11": "totals", "F1040.14": "totals",
    "F1040.15": "totals", "F1040.16": "totals", "F1040.17": "totals", "F1040.18": "totals", "F1040.22": "totals",
    "F1040.23": "totals", "F1040.24": "totals",
    "F1040.25a": "payments", "F1040.25d": "payments", "F1040.26": "payments", "F1040.31": "payments",
    "F1040.33": "payments", "F1040.37": "payments", "F1040.38": "payments",
    "Sch1.3": "business", "Sch1.15": "business", "Sch1.16": "business", "Sch1.17": "business",
    "Sch1.5": "rentals", "Sch1.13": "deductions", "Sch1.10": "totals", "Sch1.26": "totals",
    "Sch2.1": "wages", "Sch2.11": "wages", "Sch2.4": "business", "Sch2.12": "investments",
    "Sch2.3": "totals", "Sch2.21": "totals",
    "Sch3.1": "investments", "Sch3.8": "totals", "Sch3.10": "payments", "Sch3.11": "payments", "Sch3.15": "payments",
}
_FORM_AREA = {
    "F8959": "wages", "F6251": "wages",
    "SchB": "investments", "SchD": "investments", "F8949": "investments", "F8960": "investments", "F8938": "investments",
    "SchC": "business", "F4562-C": "business", "SchSE": "business", "F8995": "business",
    "SchE": "rentals", "F4562-E": "rentals", "F8582": "rentals", "F4797": "rentals",
    "F7203": "passthroughs",
    "SchA": "deductions", "F8283": "deductions", "F8812": "deductions", "F8863": "deductions", "F2441": "deductions",
    "F8889": "deductions", "F8606": "deductions", "F8867": "deductions",
    "F2210": "payments", "F540NR.7": "payments",
    "SchCA540NR": "california", "F540NR": "california", "FTB": "california", "ScheduleS": "california",
}
_DOC_AREA = {
    "W-2": "wages", "stock_plan_supplement": "wages", "3921": "wages", "3922": "wages", "paystub": "wages",
    "1099-composite": "investments", "1099-INT": "investments", "1099-DA": "investments",
    "transaction_export": "investments", "foreign_bank_statement": "investments",
    "books_profit_loss": "business", "books_transaction_detail": "business", "books_report": "business",
    "1099-NEC": "business", "1099-K": "business", "mileage_log": "business", "client_note": "business",
    "insurance_statement": "business", "retirement_contribution": "business",
    "rental_owner_statement": "rentals", "rental_ledger": "rentals", "closing_statement_seller": "rentals",
    "1099-S": "rentals", "property_tax_bill": "rentals",
    "K-1-1065": "passthroughs", "K-1-1120S": "passthroughs", "K-1-state-supplement": "passthroughs",
    "closing_statement_buyer": "deductions", "1098": "deductions", "property_tax_receipt": "deductions",
    "payoff_statement": "deductions", "donation_receipt": "deductions", "1098-C": "deductions", "1098-T": "deductions",
    "dependent_care_statement": "deductions", "letter": "deductions", "1099-R": "deductions", "5498": "deductions",
    "1099-SA": "deductions", "5498-SA": "deductions",
    "payment_confirmation": "payments",
}

# What each kind of check means for the person fixing it: (why it matters, what to do).
_PLAIN = {
    "X1": ("The number on the return is not what the document prints - the reader swapped or misread characters.",
           "Open the page, read the printed value, and correct the line."),
    "X2": ("A value the reader produced does not appear on the page it came from.",
           "Check the page; if the value is wrong, correct it."),
    "X3": ("A blank field was read as zero and used as an amount.",
           "Confirm the field is really blank and whether the line should use it."),
    "X4": ("The reader was unsure about this value, and the return uses it.",
           "Confirm the amount against the page or with the client."),
    "X5": ("The same page was scanned twice and counted twice.",
           "Remove the duplicate page's amount from the line."),
    "X6": ("A page of the document was never read, so its transactions are missing.",
           "Add what the unread page prints."),
    "X7": ("The document's summary does not equal the sum of its details.",
           "Find the missing or extra detail and reconcile."),
    "X8": ("The same income appears on two documents and is counted twice.",
           "Keep one of them and remove the other from the line."),
    "X9": ("The same document was uploaded twice.",
           "Make sure it is counted once."),
    "R": ("Our own recomputation does not agree with the engine.",
          "Check the inputs; if they are right, the engine needs a rerun."),
    "P1": ("Payments on the return do not match what the IRS actually received.",
           "Use the IRS record and confirm with the client."),
    "P2": ("Payments on the return do not match what the FTB actually received.",
           "Use the FTB record; ask the FTB to move any payment applied to the wrong year."),
    "P3": ("An identification number does not match the documents - the e-file will be rejected.",
           "Correct it from the Social Security card or prior return."),
    "P4": ("A carryover does not agree with last year's return.",
           "Reconcile it to the 2024 return and the prior preparer's file."),
    "P5": ("These lines moved more than the firm's threshold (10% and 1,000) since last year.",
           "Write a short explanation for each, or fix it if the change is an error."),
    "P6": ("These documents are not used anywhere on the return.",
           "Confirm each is not needed and record why, or use it."),
    "P7": ("The tax engine raised this warning itself.",
           "Decide how to handle it and record the decision."),
    "J": ("A fact stated elsewhere in the file should have changed this number.",
          "Review the evidence and apply the proposed correction."),
}


# Checks whose fix is a decision, not a number to apply.
_PLAIN_CHECK = {
    "J10-client-supplied-basis": ("The client says what this cost, but there is no document proving it yet.",
                                  "Ask the client for evidence of the purchase, then decide what basis to use."),
    "J11-client-answer-contradicts-records": ("A client answer contradicts a filed return or a third-party form.",
                                              "Rely on the record, and note the conflict and why."),
    "J12-outside-filings": ("The facts reveal a filing obligation outside this return.",
                            "Raise it with the client in writing and record what was decided (in or out of scope)."),
}
_DECIDE = "Review the evidence and record your decision."


def _plain(check: str, has_correction: bool = True) -> tuple[str, str]:
    if check in _PLAIN_CHECK:
        return _PLAIN_CHECK[check]
    family = check.split("-")[0]
    why, todo = _PLAIN.get(family) or _PLAIN.get(family[0]) or ("", _DECIDE)
    if family.startswith("J") and not has_correction:
        todo = _DECIDE
    return why, todo


def area_of(nodes: list[str], packet) -> str:
    for n in nodes:
        if n.startswith("line:"):
            key = n.split(":", 2)[2]
            if key in _LINE_AREA:
                return _LINE_AREA[key]
            for prefix in sorted(_FORM_AREA, key=len, reverse=True):
                if key.startswith(prefix):
                    return _FORM_AREA[prefix]
    for n in nodes:
        doc = None
        if n.startswith(("doc:", "page:")):
            doc = n.split(":", 1)[1].split("#")[0]
        elif n.startswith("ev:"):
            doc = packet.ev[n[3:]]["document_id"]
        if doc and doc in packet.doc:
            return _DOC_AREA.get(packet.doc[doc]["document_type"], "intake")
    return "intake"


_LINKABLE = ("line:", "ev:", "page:", "doc:")


def _primary_target(f: Finding) -> str | None:
    """The node the Inbox opens: a return line first, else a value, page or document the finding cites.
    None when nothing has a page of its own (e.g. a questionnaire answer) - the UI opens the finding."""
    for prefix in _LINKABLE:
        for n in f.nodes + f.evidence:
            if n.startswith(prefix):
                return n
    return None


def _item(**kw) -> dict:
    kw.setdefault("effect", {"federal": None, "california": None})
    kw["area_label"] = AREAS.get(kw.get("area"), kw.get("area"))
    return kw


def _effect_size(item: dict) -> float:
    e = item.get("effect") or {}
    return abs(e.get("federal") or 0) + abs(e.get("california") or 0)


def _sort(items: list[dict]) -> list[dict]:
    return sorted(items, key=lambda i: (SEVERITY_RANK.get(i.get("severity"), 3), -_effect_size(i), i["title"]))


# ------------------------------------------------------------------ finding state
def finding_state(f: Finding, log: LogView, version: str) -> dict:
    """open | adjusted (a line it proposed to correct was changed) | decided (a decision was recorded on it)
    | reviewed (a reviewer or partner other than the author signed off after the latest of those).

    Only a proposed correction can be settled by an adjustment. Findings that ask for an explanation or
    a decision (prior-year variance, outside filings, engine diagnostics, identity) are settled by
    recording a decision - with its authority - against the finding."""
    lines = [f"line:{version}:{c.line}" for c in f.corrections]
    adj = next((a for t in lines if (a := log.last(t, "adjust"))), None)
    decision = next((e for e in reversed(log.of_type("judgment")) if e["payload"].get("finding_id") == f.id), None)
    latest = max((x for x in (adj, decision) if x), key=lambda x: x["id"], default=None)
    if latest is None:
        return {"state": "open"}
    reviewed = log.signed_after(latest["target"], latest["id"], ("reviewer", "partner"), latest["actor"])
    out = {"state": "reviewed" if reviewed else ("adjusted" if latest is adj else "decided"),
           "by": latest["actor"], "at": latest["at"], "event_id": latest["id"],
           "line": latest["target"].split(":", 2)[2] if latest["target"].startswith("line:") else None}
    if latest is decision:
        out["decision"] = decision["payload"].get("decision")
        out["authority"] = decision["payload"].get("authority")
    return out


def finding_states(findings: list[Finding], events: list[dict], version: str) -> dict[str, dict]:
    log = LogView(events)
    return {f.id: finding_state(f, log, version) for f in findings}


def _plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


# ------------------------------------------------------------------ item builders
def _finding_items(findings: list[Finding], packet, log: LogView, version: str, people: dict) -> list[dict]:
    items, groups = [], defaultdict(list)
    for f in findings:
        family = f.check.split("-")[0]
        if f.severity == "info":
            continue
        if family in GROUPED:  # only what is still open; handled ones wait for review as a decision batch
            if finding_state(f, log, version)["state"] == "open":
                groups[family].append(f)
            continue
        st = finding_state(f, log, version)
        proposal = "; ".join(f"Change {c.line} from {_fmt(c.current)} to {_fmt(c.proposed)}" for c in f.corrections)
        why, todo = _plain(f.check, bool(f.corrections))
        if st["state"] in ("adjusted", "decided"):
            who = people.get(st["by"])
            name = who.name if who else st["by"]
            why = (f"{name} changed {st['line']} on {st['at'][:10]}." if st["state"] == "adjusted"
                   else f"{name} decided on {st['at'][:10]}: {st['decision']} (authority: {st['authority']}).")
            todo = "Nothing to do until a reviewer signs off."
        items.append(_item(
            id=f.id, kind="finding", severity=f.severity, title=f.title, what=f.detail, why=why, todo=todo,
            proposal=proposal or None, effect={"federal": f.federal_effect, "california": f.california_effect},
            area=area_of(f.nodes, packet), target=_primary_target(f), finding_id=f.id, state=st["state"],
            handled_by=st.get("by"), handled_at=st.get("at")))
    for family, fs in groups.items():
        why, todo = _plain(family)
        title = (_plural(len(fs), "prior-year change") + " to explain" if family == "P5"
                 else _plural(len(fs), "document") + " not used")
        items.append(_item(
            id=f"group:{family}", kind="group", severity=min((f.severity for f in fs), key=SEVERITY_RANK.get),
            title=title, what="; ".join(f.title for f in fs[:3]) + ("; ..." if len(fs) > 3 else ""), why=why,
            todo=todo, proposal=None, area=None, target=None, check=family, count=len(fs), state="open"))
    return items


def _fmt(v) -> str:
    if isinstance(v, (int, float)):
        return f"{v:,.0f}" if float(v).is_integer() else f"{v:,.2f}"
    return str(v)


def _adjustment_items(working: WorkingReturn, packet, people: dict, version: str) -> list[dict]:
    out = []
    for a in working.adjustments:
        who = people.get(a.actor)
        label = packet.line(a.key, version)["label"]
        out.append(_item(
            id=f"adj:{a.event_id}", kind="adjustment", severity="warning",
            title=f"{who.name if who else a.actor} changed {a.key} {label}: {_fmt(a.engine)} -> {_fmt(a.new)}",
            what=a.reason, why="A change to the return needs a second person's review before it can be filed.",
            todo="Check the evidence, then sign off - or leave a review note.", proposal=None,
            effect={"federal": a.effect.get("federal"), "california": a.effect.get("california")},
            area=area_of([f"line:{version}:{a.key}"], packet), target=f"line:{version}:{a.key}",
            event_id=a.event_id, actor=a.actor, state="open"))
    return out


def _question_items(person: Person, log: LogView, packet, people: dict) -> list[dict]:
    """Questions addressed to this person (client or colleague) that nobody has answered yet."""
    out = []
    for e in log.of_type("question"):
        if e["payload"].get("to") != person.id or e["id"] in log.answered:
            continue
        who = people.get(e["actor"])
        out.append(_item(
            id=f"q:{e['id']}", kind="question", severity="warning", title=e["payload"].get("text", ""), what=None,
            why=("Your preparer needs this to finish your return." if person.role == "client"
                 else f"{who.name if who else e['actor']} asked you."),
            todo="Reply with what you know - your answer is kept as evidence.", proposal=None,
            area=area_of([e["target"]], packet), target=e["target"], event_id=e["id"], actor=e["actor"],
            state="open"))
    return out


def _decision_items(findings: list[Finding], log: LogView, packet, people: dict, version: str,
                    working: WorkingReturn | None = None) -> list[dict]:
    """Decisions recorded against findings that no reviewer has signed off yet. Decisions recorded together
    (one batch) are reviewed together: one item, one sign-off for all."""
    by_id = {f.id: f for f in findings}
    events = {e["id"]: e for e in log.live}
    out = []
    for f in findings:
        st = finding_state(f, log, version)
        if st["state"] != "decided":
            continue
        who = people.get(st["by"])
        out.append(_item(
            id=f"dec:{st['event_id']}", kind="decision", severity="warning",
            title=f"{who.name if who else st['by']} decided {f.id}: {by_id[f.id].title}",
            what=f"{st['decision']} - Authority: {st['authority']}",
            why="A decision on an issue needs a second person's review before filing.",
            todo="Check the decision and its authority, then sign off - or leave a review note.", proposal=None,
            area=area_of(f.nodes, packet), target=events[st["event_id"]]["target"],
            event_id=st["event_id"], actor=st["by"], finding_id=f.id, state="open",
            batch_id=events[st["event_id"]].get("batch_id")))
    batches: dict[str, list[dict]] = defaultdict(list)
    for item in out:
        if item["batch_id"]:
            batches[item["batch_id"]].append(item)
    # A sign-off covers everything on a node. Signing a batch must not quietly approve a different change
    # waiting on the same node, so those nodes are held back to be reviewed on their own.
    pending: dict[str, set] = defaultdict(set)
    for a in (working.adjustments if working else []):
        t = f"line:{version}:{a.key}"
        if not log.signed_after(t, a.event_id, ("reviewer", "partner"), a.actor):
            pending[t].add(f"adj:{a.event_id}")
    for item in out:
        pending[item["target"]].add(item["batch_id"] or item["id"])
    grouped = []
    for item in out:
        group = batches.get(item["batch_id"]) if item["batch_id"] else None
        if not group or len(group) == 1:
            grouped.append(item)
        elif group[0] is item:
            who = people.get(item["actor"])
            checks = {by_id[g["finding_id"]].check.split("-")[0] for g in group}
            targets = sorted({g["target"] for g in group})
            held = [t for t in targets if pending[t] - {item["batch_id"]}]
            clean = [t for t in targets if t not in held]
            grouped.append(_item(
                id=f"decbatch:{item['batch_id']}", kind="decision_batch", severity="warning",
                title=f"{who.name if who else item['actor']} recorded one decision for {len(group)} issues",
                what=item["what"], why="Decisions recorded together can be reviewed together.",
                todo=(f"Check the decision and its authority, then sign off all {len(clean)} - or leave a review note."
                      + (f" {len(held)} held back: those lines have other changes to review on their own."
                         if held else "")),
                proposal=None, area=None, target=None, actor=item["actor"], state="open", count=len(group),
                check=checks.pop() if len(checks) == 1 else None,
                targets=clean, held_back=held, finding_ids=[g["finding_id"] for g in group]))
    return grouped


def _approval_items(person: Person, signoffs: list[dict], version: str) -> list[dict]:
    """For a client: the return is ready to approve once the partner has signed it; again if it changed since."""
    ret = f"ver:{version}"
    if not any(s["target"] == ret and s["level"] == "partner" and s["valid"] for s in signoffs):
        return []
    mine = [s for s in signoffs if s["target"] == ret and s["actor"] == person.id and s["level"] == "client"]
    if mine and mine[-1]["valid"]:
        return []
    again = bool(mine)
    return [_item(id="approval", kind="approval", severity="warning",
                  title="Your return changed after you approved it" if again else "Your return is ready for your approval",
                  what=None, why=("Something on the return changed after you signed, so your approval no longer holds."
                                  if again else "We cannot file until you and your spouse approve it."),
                  todo="Review the summary, then approve and sign with your PIN.", proposal=None, area=None,
                  target=ret, state="open")]


def _reopened_items(person: Person, signoffs: list[dict], packet, version: str) -> list[dict]:
    """This person's sign-offs that no longer hold. Sign-offs given together (one batch) that reopened
    together come back as one item, to be signed again together."""
    mine = [s for s in signoffs if s["actor"] == person.id and not s["valid"]]
    groups: dict[str, list[dict]] = defaultdict(list)
    for s in mine:
        groups[s["batch_id"] or f"one:{s['event_id']}"].append(s)
    out = []
    for key, group in groups.items():
        s = group[0]
        changes: dict[str, str] = {}
        for g in group:
            for c in g["changed"]:
                changes.setdefault(c["node"].split(":", 2)[-1], c["what"])
        what = "; ".join(f"{k}: {w}" for k, w in list(changes.items())[:3])
        more = f" (+{len(changes) - 3} more)" if len(changes) > 3 else ""
        if len(group) == 1:
            label = "the whole return" if s["target"] == f"ver:{version}" else s["target"].split(":", 2)[-1]
            title = f"Your {s['level']} sign-off on {label} reopened - {s['changed_count']} change(s) since you signed"
            target, targets = s["target"], None
        else:
            title = f"{len(group)} of your {s['level']} sign-offs, given together, reopened"
            target, targets = None, sorted(g["target"] for g in group)
        out.append(_item(
            id=f"reopen:{key}", kind="reopened", severity="error", title=title, what=what + more,
            why="Something you signed changed after you signed it.",
            todo="Review what changed, then sign again - or leave a review note.", proposal=None,
            area=area_of([s["target"]], packet) if len(group) == 1 and s["target"].startswith("line:") else None,
            target=target, targets=targets, level=s["level"], count=len(group), event_id=s["event_id"],
            state="open"))
    return out


def build_inbox(person: Person, *, packet, findings: list[Finding], events: list[dict], working: WorkingReturn,
                people: dict, signoffs: list[dict] | None = None) -> dict:
    signoffs = signoffs or []
    version = working.version
    log = LogView(events)
    sections: list[dict] = []

    def section(key: str, title: str, items: list[dict], hint: str | None = None, needs_you: bool = True):
        # needs_you=False: shown for context (waiting on someone else), not counted as this person's work
        sections.append({"key": key, "title": title, "hint": hint, "items": items, "needs_you": needs_you})

    notes = [e for e in log.live if e["type"] == "review_note" and e["id"] not in log.resolved_notes]
    note_items = [_item(id=f"note:{e['id']}", kind="review_note", severity="error" if e["payload"].get("blocking") else "warning",
                        title=e["payload"].get("text", ""), what=None,
                        why="Blocks filing until resolved." if e["payload"].get("blocking") else "Raised in review.",
                        todo="Address it, then ask the reviewer to resolve it.", proposal=None,
                        area=area_of([e["target"]], packet), target=e["target"], event_id=e["id"], actor=e["actor"],
                        state="open") for e in notes]

    role = person.role
    if role == "client":
        section("approval", "Your approval", _approval_items(person, signoffs, version))
        section("questions", "Questions for you", _question_items(person, log, packet, people))
    elif role == "firm_administrator":
        pass
    else:
        section("reopened", "Your sign-offs reopened", _reopened_items(person, signoffs, packet, version),
                "What you signed changed after you signed it.")
        section("questions", "Questions for you", _question_items(person, log, packet, people))
        decisions = [d for d in _decision_items(findings, log, packet, people, version, working)
                     if d["actor"] != person.id]
        found = _finding_items(findings, packet, log, version, people)
        batches = [i for i in found if i["kind"] == "group"]
        found = [i for i in found if i["kind"] != "group"]
        adjustments = _adjustment_items(working, packet, people, version)
        for a in adjustments:  # who still has to look at each change
            ev_id = a["event_id"]
            a["state"] = ("reviewed" if log.signed_after(a["target"], ev_id, ("reviewer", "partner"), a["actor"])
                          else "open")
            a["needs_partner"] = _effect_size(a) > 0 and max(abs(a["effect"]["federal"] or 0),
                                                              abs(a["effect"]["california"] or 0)) > PARTNER_THRESHOLD
            a["partner_signed"] = log.signed_after(a["target"], ev_id, ("partner",), a["actor"])
        if role == "preparer":
            section("notes", "Review notes to address", _sort(note_items))
            section("fix", "Issues to fix", _sort([i for i in found if i["state"] == "open"]),
                    "Worst first. Each one says what to do.")
            section("batch", "Batch reviews", _sort(batches), "Many lines for one reason - work through the list.")
            replies = [e for e in log.live if e["type"] == "answer"
                       and (q := next((x for x in log.live if x["id"] == e["payload"].get("event_id")), None))
                       and q["actor"] == person.id]
            section("replies", "Replies to your questions", [
                _item(id=f"a:{e['id']}", kind="answer", severity="info", title=e["payload"].get("text", ""), what=None,
                      why="The answer is now evidence on this line.", todo="Use it to settle the line.", proposal=None,
                      area=area_of([e["target"]], packet), target=e["target"], event_id=e["id"], actor=e["actor"],
                      state="open") for e in replies])
            section("done", "Changed, waiting for review",
                    _sort([i for i in found if i["state"] in ("adjusted", "decided")]),
                    "Nothing to do until a reviewer signs off.", needs_you=False)
        elif role == "reviewer":
            section("review", "Waiting for your review",
                    _sort([a for a in adjustments if a["state"] == "open" and a["actor"] != person.id] + decisions),
                    "Changes and decisions by others. You cannot review your own work.")
            section("open", "Issues nobody has handled yet", _sort([i for i in found if i["state"] == "open"]))
            section("notes", "Your open review notes", _sort([n for n in note_items if n["actor"] == person.id]),
                    "Waiting on the preparer.", needs_you=False)
        elif role == "partner":
            ret = f"ver:{version}"
            reviewer_ok = any(x["target"] == ret and x["level"] == "reviewer" and x["valid"] for x in signoffs)
            partner_ok = any(x["target"] == ret and x["level"] == "partner" and x["valid"] for x in signoffs)
            if reviewer_ok and not partner_ok:
                section("return", "Return ready for partner sign-off", [_item(
                    id="return:partner", kind="return", severity="warning",
                    title="The reviewer signed off the whole return", what=None,
                    why="Filing needs a partner sign-off on the whole return (step 11).",
                    todo="Open Filing, check the steps and blockers, then sign off.", proposal=None,
                    area=None, target=ret, state="open")])
            section("partner", "Needs partner sign-off",
                    _sort([a for a in adjustments if a["needs_partner"] and not a["partner_signed"]
                           and a["actor"] != person.id]),
                    f"Changes with an estimated tax effect over {PARTNER_THRESHOLD:,} (firm rule).")
            section("errors", "Errors still open", _sort([i for i in found if i["state"] == "open" and i["severity"] == "error"]))
        elif role == "quality_reviewer":
            section("errors", "All errors", _sort([i for i in found if i["severity"] == "error"]))
            section("changes", "All changes and decisions", _sort(adjustments + decisions))

    total = sum(len(s["items"]) for s in sections if s["needs_you"])
    return {"person": person.id, "role": role, "total": total, "sections": [s for s in sections if s["items"]],
            "empty_message": None if total else _empty_message(role)}


def _empty_message(role: str) -> str:
    return {
        "firm_administrator": "No review work is assigned to administrators. Firm standards and budgets are managed separately.",
        "client": "Nothing needs your attention right now. We will let you know if we have questions.",
    }.get(role, "Nothing needs your attention right now.")

