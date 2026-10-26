"""Documents that arrive corrected: which original a corrected form replaces, and what it changed.

A corrected document replaces the earlier one from the same issuer, of the same type, for the same owner
and year. The two are compared value by value (same page, same field); for each change the lines that
used the original value and the lines that use the corrected one are listed, per return version.
"""
from __future__ import annotations


def _pair(packet, doc_id: str) -> tuple[dict, dict] | None:
    d = packet.doc[doc_id]
    same = [x for x in packet.documents if x["id"] != doc_id and x["issuer"] == d["issuer"]
            and x["document_type"] == d["document_type"] and x["belongs_to"] == d["belongs_to"]
            and x["tax_year"] == d["tax_year"]]
    if d.get("marked_corrected"):
        orig = [x for x in same if not x.get("marked_corrected") and x["received_at"] < d["received_at"]]
        return (orig[-1], d) if orig else None
    corr = [x for x in same if x.get("marked_corrected") and x["received_at"] > d["received_at"]]
    return (d, corr[0]) if corr else None


def correction(packet, doc_id: str) -> dict | None:
    pair = _pair(packet, doc_id)
    if pair is None:
        return None
    orig, corr = pair
    vals = lambda did: {(e["page"], e["field"]): e for e in packet.extracted_values if e["document_id"] == did}  # noqa: E731
    a, b = vals(orig["id"]), vals(corr["id"])
    used: dict[str, dict[str, list[str]]] = {}
    for v in packet.versions:
        for line in v["lines"]:
            for s in line["sources"]:
                used.setdefault(s, {}).setdefault(v["version"], []).append(line["key"])
    changes = []
    for k in sorted(set(a) | set(b), key=lambda k: (k[0], k[1])):
        before, after = a.get(k), b.get(k)
        if before and after and before["value"] == after["value"]:
            continue
        ref = after or before
        changes.append({"page": k[0], "field": k[1], "label": ref.get("label"),
                        "before": before["value"] if before else None, "after": after["value"] if after else None,
                        "before_ev": before["id"] if before else None, "after_ev": after["id"] if after else None,
                        "used_before": used.get(before["id"], {}) if before else {},
                        "used_after": used.get(after["id"], {}) if after else {}})
    superseded_in = [v["version"] for v in packet.versions if orig["id"] in v.get("documents_superseded", [])]
    return {"original": {"id": orig["id"], "title": orig["title"], "received_at": orig["received_at"]},
            "corrected": {"id": corr["id"], "title": corr["title"], "received_at": corr["received_at"]},
            "values_compared": len(set(a) | set(b)), "changes": changes, "superseded_in": superseded_in}
