"""Compare two states of the return line by line, and the engine's what-if alternatives.

A state is an engine version (v1, v2, v3) or 'working' - the latest version with people's adjustments
applied. Between versions the diff is computed from the lines themselves (it agrees with the packet's own
changes_from_previous for consecutive versions; a test holds that). Against 'working', lines that only an
engine rerun can update are listed as needing a recompute rather than shown as unchanged.

What-ifs are the engine's own results for specific alternatives (packet what_if). We cannot rerun the
engine, so choosing one is recorded as an election decision - it does not change the working return.
"""
from __future__ import annotations

from workpaper.working import WorkingReturn

from .logview import LogView

SUMMARY_FIELDS = [  # (jurisdiction, key, label)
    ("federal", "agi", "AGI"), ("federal", "taxable_income", "Taxable income"), ("federal", "total_tax", "Total tax"),
    ("federal", "payments", "Payments"), ("federal", "balance_due", "Balance due"), ("federal", "penalty", "Penalty"),
    ("california", "ca_agi", "California AGI"), ("california", "total_tax", "California tax"),
    ("california", "payments", "California payments"), ("california", "balance_due", "California balance due"),
]
WORKING = "working"
AMENDED = "amended"  # after filing: the filed return (frozen working) plus the amendment layer


def _num(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def states(packet) -> list[dict]:
    out = [{"id": v["version"], "label": f"{v['version']} · {v['computed_at'][:10]}", "trigger": v["trigger"]}
           for v in packet.versions]
    out.append({"id": WORKING, "label": f"Working ({packet.latest['version']} + adjustments)",
                "trigger": "The latest version with everyone's adjustments applied (estimated where the engine would recompute)."})
    out.append({"id": AMENDED, "label": "Amended (as filed + amendment)",
                "trigger": "After filing: the return as filed plus the changes made on the amendment (Form 1040-X; California 540NR with Schedule X)."})
    return out


def _lines(packet, state: str, working: WorkingReturn) -> dict[str, dict]:
    version = working.version if state in (WORKING, AMENDED) else state
    out = {}
    for key, line in packet.lines[version].items():
        w = working.lines.get(key) if state in (WORKING, AMENDED) else None
        out[key] = {"value": w["value"] if w else line["value"], "label": line["label"], "form": line["form"],
                    "kind": w["kind"] if w else None}
    return out


def _summary(packet, state: str, working: WorkingReturn) -> dict:
    if state not in (WORKING, AMENDED):
        return packet.version[state]["summary"]
    base = packet.version[working.version]["summary"]
    s = working.summary
    fed = {**base["federal"], "agi": s["agi"]["value"], "total_tax": s["total_tax"]["value"],
           "balance_due": s["balance_due"]["value"]}
    w15 = working.lines.get("F1040.15")
    if w15:
        fed["taxable_income"] = w15["value"]
    ca = {**base["california"], "total_tax": s["ca_total_tax"]["value"], "balance_due": s["ca_balance_due"]["value"]}
    return {"federal": fed, "california": ca}


def compare(packet, working: WorkingReturn, a: str, b: str, amended: WorkingReturn | None = None) -> dict:
    valid = {v["version"] for v in packet.versions} | {WORKING, AMENDED}
    for s in (a, b):
        if s not in valid:
            raise ValueError(f"unknown state {s!r}; use one of {sorted(valid)}")
    pick = lambda st: amended if st == AMENDED and amended is not None else working  # noqa: E731
    la, lb = _lines(packet, a, pick(a)), _lines(packet, b, pick(b))
    rows = []
    for key in sorted(set(la) | set(lb), key=lambda k: (k.split(".")[0], k)):
        x, y = la.get(key), lb.get(key)
        old, new = (x or {}).get("value"), (y or {}).get("value")
        kind = (y or {}).get("kind")
        if x is None:
            change = "added"
        elif y is None:
            change = "removed"
        elif old != new:
            change = "changed"
        elif kind == "stale":
            change = "needs recompute"
        else:
            continue
        on, nn = _num(old), _num(new)
        rows.append({"key": key, "label": (y or x)["label"], "form": (y or x)["form"], "change": change,
                     "old": old, "new": new, "delta": nn - on if on is not None and nn is not None else None,
                     "kind": kind})

    sa, sb = _summary(packet, a, pick(a)), _summary(packet, b, pick(b))
    summary = []
    for j, k, label in SUMMARY_FIELDS:
        old, new = sa[j].get(k), sb[j].get(k)
        summary.append({"jurisdiction": j, "key": k, "label": label, "old": old, "new": new,
                        "delta": new - old if _num(old) is not None and _num(new) is not None else None,
                        "estimated": b in (WORKING, AMENDED) and k not in ("agi", "taxable_income", "payments", "penalty")})

    live = (WORKING, AMENDED)
    va = packet.version[working.version if a in live else a]
    vb = packet.version[working.version if b in live else b]
    docs_a, docs_b = set(va.get("documents_used", [])), set(vb.get("documents_used", []))
    later = packet.versions.index(vb) > packet.versions.index(va)
    return {
        "from": a, "to": b,
        "trigger": (next(x["trigger"] for x in states(packet) if x["id"] == b) if b in live else vb["trigger"])
        if later or b in live else None,
        "computed_at": None if b in live else vb["computed_at"],
        "documents": {"added": sorted(docs_b - docs_a, key=_doc_order), "removed": sorted(docs_a - docs_b, key=_doc_order),
                      "superseded": sorted(set(vb.get("documents_superseded", [])) - set(va.get("documents_superseded", [])))},
        "summary": summary,
        "lines": rows,
        "counts": {c: sum(1 for r in rows if r["change"] == c) for c in ("changed", "added", "removed", "needs recompute")},
        "adjustments": [{"key": x.key, "engine": x.engine, "new": x.new, "reason": x.reason, "actor": x.actor}
                        for x in pick(b if b in live else a).adjustments] if a in live or b in live else [],
    }


def _doc_order(d: str) -> tuple:
    return (len(d), d)


def what_ifs(packet, log: LogView, findings=()) -> dict:
    elections = {}
    for e in log.of_type("judgment"):
        wid = e["payload"].get("what_if")
        if wid:
            elections[wid] = {"event_id": e["id"], "actor": e["actor"], "at": e["at"], "decision": e["payload"].get("decision"),
                              "authority": e["payload"].get("authority")}
    out = []
    for alt in packet.raw["what_if"]["alternatives"]:
        base = alt["base_version"]
        lines = []
        for c in alt["changed_lines"]:
            line = packet.line(c["key"], base)
            lines.append({**c, "label": line["label"] if line else c["key"], "exists": line is not None})
        summary = []
        for j, k, label in SUMMARY_FIELDS:
            b0, b1 = alt[j]["base"].get(k), alt[j]["alternative"].get(k)
            if b0 is None and b1 is None:
                continue
            summary.append({"jurisdiction": j, "key": k, "label": label, "old": b0, "new": b1,
                            "delta": b1 - b0 if _num(b0) is not None and _num(b1) is not None else None})
        out.append({"id": alt["id"], "description": alt["description"], "base_version": base, "choices": alt["choices"],
                    "federal": alt["federal"]["total_tax_change"], "california": alt["california"]["total_tax_change"],
                    "penalty": alt["federal"].get("penalty_change", 0), "summary": summary, "lines": lines,
                    "election": elections.get(alt["id"]),
                    "findings": [f.id for f in findings if alt["id"] in (f.effect_note or "") + f.detail]})
    return {"alternatives": out, "extension": packet.raw["what_if"].get("extension")}
