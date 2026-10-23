"""Sign-offs that reopen when what was signed changes.

A sign-off records a scope and a hash of the scope's content:
  - scope: the signed node and everything upstream of it - for a line, the lines it is computed from
    and the values, documents and records it cites, all the way down; for the return (ver:v3), every line.
  - content, per node in scope: the working value, the live adjustment, decisions recorded on it and
    evidence attached to it.
Not in the hash: notes, questions, views, assignments - and verifications, which add assurance rather
than change what was signed (they are reported, not treated as a reopen).

On every read the content is rebuilt from the log; if the hash differs, the sign-off is reopened and
the snapshot taken at signing tells the signer exactly what changed since.
"""
from __future__ import annotations

import hashlib
import json

from workpaper.working import WorkingReturn

from .logview import LogView


def scope_of(packet, index, target: str, version: str) -> list[str]:
    if target == f"ver:{version}":
        roots = [f"line:{version}:{k}" for k in packet.lines[version]]
    else:
        roots = [target]
    seen: set[str] = set()
    stack = list(roots)
    while stack:
        n = stack.pop()
        if n in seen:
            continue
        seen.add(n)
        if n.startswith("line:"):
            stack.extend(index.targets(n, "computed_from"))
            stack.extend(index.targets(n, "sourced_from"))
    return sorted(seen)


def content_of(scope: list[str], packet, working: WorkingReturn, log: LogView) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for n in scope:
        c: dict = {}
        if n.startswith("line:"):
            key = n.split(":", 2)[2]
            w = working.lines.get(key)
            c["value"] = w["value"] if w else packet.line(key, working.version)["value"]
        elif n.startswith("ev:"):
            c["value"] = packet.ev[n[3:]]["value"]
        events = log.by_target.get(n, [])
        adj = [e for e in events if e["type"] == "adjust"]
        if adj:
            c["adjusted"] = {"event": adj[-1]["id"], "to": adj[-1]["payload"].get("new_value")}
        decisions = [e["id"] for e in events if e["type"] == "judgment"]
        if decisions:
            c["decisions"] = decisions
        evidence = [e["id"] for e in events if e["type"] == "attach"]
        if evidence:
            c["evidence"] = evidence
        out[n] = c
    return out


def digest(content: dict) -> str:
    return hashlib.sha256(json.dumps(content, sort_keys=True, default=str).encode()).hexdigest()


def take(packet, index, working: WorkingReturn, log: LogView, target: str) -> tuple[list[str], dict, str]:
    """(scope, content, hash) for a sign-off on target as of now."""
    scope = scope_of(packet, index, target, working.version)
    content = content_of(scope, packet, working, log)
    return scope, content, digest(content)


def _num(v) -> str:
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return f"{v:,.0f}" if float(v).is_integer() else f"{v:,.2f}"
    return str(v)


def _describe(node: str, before: dict | None, after: dict | None) -> dict:
    before, after = before or {}, after or {}
    what = []
    if before.get("value") != after.get("value"):
        what.append(f"{_num(before.get('value'))} -> {_num(after.get('value'))}")
    if before.get("adjusted") != after.get("adjusted"):
        what.append("adjusted" if after.get("adjusted") else "adjustment undone")
    if before.get("decisions") != after.get("decisions"):
        what.append("decision recorded" if after.get("decisions") else "decision withdrawn")
    if before.get("evidence") != after.get("evidence"):
        what.append("evidence changed")
    return {"node": node, "what": ", ".join(what) or "changed"}


def statuses(packet, index, working: WorkingReturn, events: list[dict], snapshots: dict[int, dict]) -> list[dict]:
    """Every live sign-off with valid / reopened and, when reopened, what changed since it was signed."""
    log = LogView(events)
    out = []
    cache: dict[tuple, dict] = {}
    # signing again replaces your own earlier sign-off on the same node at the same level
    latest: dict[tuple, int] = {}
    for e in log.of_type("signoff"):
        latest[(e["target"], e["actor"], e["payload"].get("level"))] = e["id"]
    for e in log.of_type("signoff"):
        if latest[(e["target"], e["actor"], e["payload"].get("level"))] != e["id"]:
            continue
        snap = snapshots.get(e["id"])
        if snap is None:  # signed before sign-offs carried a snapshot: nothing to compare against
            continue
        scope = snap["scope"]
        key = tuple(scope)
        if key not in cache:
            cache[key] = content_of(scope, packet, working, log)
        now = cache[key]
        valid = digest(now) == snap["hash"]
        changed = []
        if not valid:
            then = snap["content"]
            for n in scope:
                if then.get(n) != now.get(n):
                    changed.append(_describe(n, then.get(n), now.get(n)))
        verified_since = [v["id"] for n in scope for v in log.by_target.get(n, [])
                          if v["type"] == "verify" and v["id"] > e["id"]]
        out.append({"event_id": e["id"], "target": e["target"], "level": e["payload"].get("level"),
                    "actor": e["actor"], "at": e["at"], "batch_id": e.get("batch_id"), "valid": valid,
                    "scope_size": len(scope),
                    "changed": changed[:25], "changed_count": len(changed),
                    "verified_since": len(verified_since)})
    return out
