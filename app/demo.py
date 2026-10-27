"""The worked example for demos: the whole review done the way the team would do it, through the API.

    Priya (preparer)  applies the proposed correction for every error that has one, records a decision with
                      its authority for every other open issue, verifies the 2024 return, completes the
                      Form 8867 checklist and records every area as considered
    Daniel (reviewer) signs off each changed line and decision, then the whole return
    Helen (partner)   signs off the changes over the firm's 1,000 threshold
    approved=True:    Helen also signs off the whole return and both clients approve - ready to file

Used by scripts/demo_seed.py (any running server) and by the public demo's "Load the ready-to-file
example" (app/sandbox.py), which builds it once into a template copy.
"""
from __future__ import annotations


class SeedError(Exception):
    pass


PRIYA, DANIEL, HELEN = "st-01", "st-02", "st-03"
RETURN = "ver:v3"

# decisions for issues that are settled by a judgment, not by changing a number (check prefix -> text)
DECISIONS = {
    "X1": ("Corrected the provider EIN on Form 2441 to the number printed on the statement", "D62 as printed"),
    "X3": ("Blank broker basis is unknown, not zero; basis taken from the stock-plan supplement", "D11 supplemental statement"),
    "X4": ("Low-confidence read checked against the page", "Source page reviewed"),
    "J10": ("Zero basis kept until the client provides evidence of the 2021 purchase; question sent", "Treas. Reg. 1.6001-1 (records)"),
    "J12": ("Raised with the clients in writing; outside this engagement", "Engagement letter D01"),
    "P3": ("Theo's SSN corrected to the Social Security card", "D71 Social Security card; D06"),
    "P5": ("Change explained by 2025 activity in the documents", "2025 source documents"),
    "P6": ("Document reviewed; not needed for a return line", "Document index"),
    "P7": ("Engine diagnostic reviewed and handled in the workpaper", "Workpaper review"),
}


def seed(c, approved: bool = False, log=print) -> dict:
    """c: an HTTP client on the app (httpx.Client, or the test client) - its default headers pick the copy."""
    def post(who: str, type_: str, target: str | None = None, **payload) -> dict:
        r = c.post("/api/events", headers={"X-Actor": who}, json={"type": type_, "target": target, "payload": payload})
        if r.status_code != 201:
            raise SeedError(f"{who} {type_} {target}: {r.status_code} {r.text}")
        return r.json()

    if c.get("/api/events?limit=1", headers={"X-Actor": PRIYA}).json():
        raise SeedError("This workpaper already has work on it - start from an empty database.")
    findings = c.get("/api/findings", headers={"X-Actor": PRIYA}).json()
    changed: list[str] = []
    for f in findings:
        if f["severity"] == "info":
            continue
        numeric = [x for x in f["corrections"] if isinstance(x.get("proposed"), (int, float))]
        primary = next((x for x in numeric if f"line:v3:{x['line']}" == f["nodes"][0]), numeric[0] if numeric else None)
        missing = primary and c.get(f"/api/lines/{primary['line']}", headers={"X-Actor": PRIYA}).status_code == 404
        if missing:  # a line the engine never produced (a lot it did not read): carry it into the total
            target = next(n for n in f["nodes"] if n.startswith("line:v3:") and n.endswith("total"))
            total = c.get(f"/api/lines/{target.split(':', 2)[2]}", headers={"X-Actor": PRIYA}).json()["by_version"]["v3"]["value"]
            post(PRIYA, "adjust", target, new_value=round(total + primary["proposed"], 2),
                 reason=f"{f['id']}: add {primary['line']} ({primary['proposed']:,.0f}) read from the source page")
            post(PRIYA, "judgment", target, kind="judgment", decision=f"Added {primary['line']} to the total from the source page",
                 authority=", ".join(n for n in f["evidence"] if n.startswith("page:")) or "Source page", finding_id=f["id"])
        elif primary and f["check"].split("-")[0] not in DECISIONS:
            target = f"line:v3:{primary['line']}"
            post(PRIYA, "adjust", target, new_value=primary["proposed"], reason=f"{f['id']}: {f['title']}", finding_id=f["id"])
            # where the dollars sit on a formula line the estimate cannot follow (miles -> car expense,
            # property tax -> the capped SALT line), apply that proposed line too
            if f["check"].split("-")[0] in ("X5", "J6"):
                for x in numeric:
                    if x is not primary:
                        post(PRIYA, "adjust", f"line:v3:{x['line']}", new_value=x["proposed"],
                             reason=f"{f['id']}: follows from {primary['line']}", finding_id=f["id"])
                        changed.append(f"line:v3:{x['line']}")
        else:
            decision, authority = DECISIONS.get(f["check"].split("-")[0], ("Reviewed with the evidence", "Documents in the file"))
            target = f["nodes"][0]
            post(PRIYA, "judgment", target, kind="explanation" if f["check"].startswith("P5") else "judgment",
                 decision=decision, authority=authority, finding_id=f["id"])
        if target not in changed:
            changed.append(target)
    log(f"Priya settled {len(changed)} items")

    post(PRIYA, "verify", "doc:D06", method="agreed_to_prior_year", note="2024 return agreed to the prior preparer's file")
    items = c.get("/api/due-diligence", headers={"X-Actor": PRIYA}).json()["items"]
    post(PRIYA, "judgment", "line:v3:F8867.status", kind="due_diligence",
         decision="Knowledge requirements met for each credit claimed; answers and documents kept in the file.",
         authority="IRC 6695(g); Treas. Reg. 1.6695-2", checklist={i["id"]: True for i in items})
    for area in c.get("/api/coverage", headers={"X-Actor": PRIYA}).json()["left"]:
        post(PRIYA, "judgment", RETURN, kind="area", area=area, applies=True,
             decision="Area reviewed: documents traced to the return, issues settled", authority="Area report and workpapers")

    batch = c.post("/api/events/batch", headers={"X-Actor": DANIEL},
                   json={"events": [{"type": "signoff", "target": t, "payload": {"level": "reviewer"}} for t in changed]})
    if batch.status_code != 201:
        raise SeedError(f"Daniel's reviews: {batch.text}")
    partner = [b["target"] for b in c.get("/api/gate", headers={"X-Actor": HELEN}).json()["blockers"] if b["kind"] == "partner"]
    if partner:
        r = c.post("/api/events/batch", headers={"X-Actor": HELEN},
                   json={"events": [{"type": "signoff", "target": t, "payload": {"level": "partner"}} for t in partner]})
        if r.status_code != 201:
            raise SeedError(f"Helen's reviews: {r.text}")
    post(DANIEL, "signoff", RETURN, level="reviewer")
    log(f"Daniel reviewed {len(changed)} items and the return; Helen reviewed {len(partner)} changes over 1,000")

    if approved:
        post(HELEN, "signoff", RETURN, level="partner")
        for who, name, pin in (("cu-01", "Ngozi Okafor", "41207"), ("cu-02", "Erik Lindqvist", "88310")):
            post(who, "signoff", RETURN, level="client", typed_name=name, pin=pin, consent=True)
        log("Helen signed off the return; Ngozi and Erik approved it")

    gate = c.get("/api/gate", headers={"X-Actor": HELEN}).json()
    left = [f"{s['n']}. {s['title']}" for s in gate["steps"] if s["status"] != "done"]
    log(f"Gate: {gate['summary']['steps_done']} of {gate['summary']['steps_total']} steps; blockers: "
        f"{[b['title'] for b in gate['blockers']] or 'none'}; left: {left}")
    return gate
