"""Answer a tax notice from the record: one evidence pack per notice.

For each item under examination the pack finds the return lines it names ("Schedule A line 12", "Schedule C
gross receipts"), and gathers what supports them: the value as filed, every source traced down from the line,
the issues raised on those lines with the decisions and changes that settled them (who, why, on what
authority) and the sign-offs that cover them, client answers and messages relied on, and the text of every
source page. Amounts named in the notice are reconciled against the sources (5 Forms 1099-NEC = 142,000).

The pack is built from the notice text and the packet - nothing is written for this particular letter.
"""
from __future__ import annotations

import html
import re
from collections import defaultdict

from workpaper.working import WorkingReturn

from .inbox import finding_state
from .logview import LogView, filing_status

FORM_NAMES = {"schedule a": "SchA", "schedule b": "SchB", "schedule c": "SchC", "schedule d": "SchD",
              "schedule e": "SchE", "schedule 1": "Sch1", "schedule 2": "Sch2", "schedule 3": "Sch3"}
AMOUNT = re.compile(r"\((\d{1,3}(?:,\d{3})+|\d+)\)")


def _lines_named(packet, version: str, text: str) -> list[str]:
    low = text.lower()
    keys: list[str] = []
    for name, form in FORM_NAMES.items():
        for m in re.finditer(rf"{name} line (\d+[a-z]?)", low):
            k = f"{form}.{m.group(1)}"
            if packet.line(k, version) and k not in keys:
                keys.append(k)
        if name in low and not re.search(rf"{name} line", low):
            # "Schedule C gross receipts": the form's lines whose label the item names
            for k, line in packet.lines[version].items():
                if k.split(".")[0] == form and str(line["label"]).lower() in low and k not in keys:
                    keys.append(k)
    return keys


def _upstream(index, version: str, key: str) -> list[str]:
    """The line and every line it is computed from."""
    seen, stack = [], [f"line:{version}:{key}"]
    while stack:
        n = stack.pop()
        if n in seen:
            continue
        seen.append(n)
        stack.extend(t for t in index.targets(n, "computed_from") if t.startswith("line:"))
    return [n.split(":", 2)[2] for n in seen]


def build_pack(notice_id: str, packet, index, working: WorkingReturn, findings, events: list[dict],
               signoffs: list[dict], people: dict) -> dict:
    notice = next((n for n in packet.raw["tax_agency_records"]["notices"] if n["id"] == notice_id), None)
    if notice is None:
        raise KeyError(notice_id)
    v, log = working.version, LogView(events)
    name = lambda pid: people[pid].name if pid in people else pid  # noqa: E731
    items = []
    for text in notice.get("items_under_examination", []):
        named = _lines_named(packet, v, text)
        keys = []
        for k in named:
            for u in _upstream(index, v, k):
                if u not in keys:
                    keys.append(u)
        nodes = {f"line:{v}:{k}" for k in keys}
        fs = [f for f in findings if f.severity != "info" and nodes & set(f.nodes)]
        evs = [s for k in keys for s in packet.line(k, v).get("sources", []) if s.startswith("ev-")]
        docs: list[str] = []
        for e in evs:
            d = packet.ev[e]["document_id"]
            if d not in docs:
                docs.append(d)
        for f in fs:
            for n in f.evidence + f.nodes:
                d = n.split(":", 1)[1].split("#")[0] if n.startswith(("doc:", "page:")) else (
                    packet.ev[n[3:]]["document_id"] if n.startswith("ev:") and n[3:] in packet.ev else None)
                if d and d not in docs:
                    docs.append(d)
        client = sorted({s for k in keys for s in packet.line(k, v).get("sources", []) if s.startswith(("qa-", "msg-"))}
                        | {n.split(":", 1)[1] for f in fs for n in f.evidence + f.nodes if n.startswith(("qa:", "msg:"))})
        # amounts the notice names, reconciled to the sources grouped by kind of document
        by_type: dict[str, list] = defaultdict(list)
        for e in evs:
            ev = packet.ev[e]
            if isinstance(ev["value"], (int, float)):
                by_type[packet.doc[ev["document_id"]]["document_type"]].append(ev)
        recon = []
        for m in AMOUNT.finditer(text):
            amount = float(m.group(1).replace(",", ""))
            match = next(((t, xs) for t, xs in by_type.items() if abs(sum(float(x["value"]) for x in xs) - amount) < 0.5), None)
            recon.append({"amount": amount, "agrees": match is not None, "document_type": match[0] if match else None,
                          "documents": sorted({x["document_id"] for x in match[1]}) if match else [],
                          "total": sum(float(x["value"]) for x in match[1]) if match else None})
        trail = []
        for f in fs:
            st = finding_state(f, log, v)
            history = [{"type": e["type"], "by": name(e["actor"]), "at": e["at"], "layer": e.get("layer", "return"),
                        "what": e["payload"].get("decision") or e["payload"].get("reason") or e["payload"].get("text"),
                        "authority": e["payload"].get("authority"), "new_value": e["payload"].get("new_value")}
                       for e in log.live if e["type"] in ("adjust", "judgment")
                       and (e["payload"].get("finding_id") == f.id or e.get("target") in nodes & set(f.nodes))]
            trail.append({"finding": f.id, "title": f.title, "severity": f.severity, "state": st["state"],
                          "detail": f.detail, "history": history})
        covering = [{"target": s["target"], "level": s["level"], "by": name(s["actor"]), "at": s["at"], "valid": s["valid"]}
                    for s in signoffs if s["target"] == f"ver:{v}" or s["target"] in nodes]
        items.append({
            "text": text,
            "lines": [{"key": k, "label": packet.line(k, v)["label"], "engine": packet.line(k, v)["value"],
                       "as_filed": (working.lines.get(k) or {}).get("value", packet.line(k, v)["value"])} for k in keys],
            "reconciliation": recon, "issues": trail, "signoffs": covering, "client": client,
            "documents": [{"id": d, "title": packet.doc[d]["title"], "received": packet.doc[d]["received_at"][:10],
                           "pages": [{"page": pg["page"], "text": pg["printed_content"]} for pg in packet.doc[d]["pages"]]}
                          for d in docs],
        })
    client_text = {}
    for item in items:
        for ref in item["client"]:
            if ref.startswith("qa-") and ref in packet.qa:
                q = packet.qa[ref]
                client_text[ref] = f"Q: {q.get('question', '')} A: {q.get('answer', '')}"
            elif ref.startswith("msg-") and ref in packet.msg:
                client_text[ref] = packet.msg[ref]["text"]
    return {"notice": notice, "version": v, "filed": (filing_status(events)["filed"] or {}).get("at"),
            "items": items, "client_text": client_text}


def render_html(pack: dict) -> str:
    """A self-contained page to print or attach to the response."""
    e = lambda s: html.escape(str(s if s is not None else ""))  # noqa: E731
    n = pack["notice"]
    out = [f"<!doctype html><html><head><meta charset='utf-8'><title>Evidence pack - {e(n['type'])}</title>",
           "<style>body{font:13px/1.45 system-ui,sans-serif;max-width:900px;margin:24px auto;padding:0 16px;color:#1e293b}"
           "h1{font-size:20px}h2{font-size:16px;margin-top:28px;border-bottom:1px solid #cbd5e1}h3{font-size:14px}"
           "table{border-collapse:collapse;width:100%}td,th{border:1px solid #e2e8f0;padding:3px 6px;text-align:left}"
           ".num{text-align:right;font-variant-numeric:tabular-nums}pre{white-space:pre-wrap;background:#f8fafc;padding:8px;border:1px solid #e2e8f0}"
           ".ok{color:#047857}.bad{color:#b91c1c}@media print{h2{break-before:page}}</style></head><body>",
           f"<h1>Evidence pack: {e(n['agency'])} {e(n['type'])}</h1>",
           f"<p>Tax year {e(n['tax_year'])} · notice dated {e(n['dated'])} · response due {e(n.get('response_due'))} · "
           f"return version {e(pack['version'])}{' · filed ' + e(pack['filed'][:10]) if pack['filed'] else ''}</p>"]
    for i, item in enumerate(pack["items"], 1):
        out.append(f"<h2>Item {i}: {e(item['text'])}</h2><h3>Return lines</h3><table><tr><th>Line</th><th>Label</th>"
                   "<th class=num>As filed</th><th class=num>Engine</th></tr>")
        out += [f"<tr><td>{e(l['key'])}</td><td>{e(l['label'])}</td><td class=num>{e(l['as_filed'])}</td>"
                f"<td class=num>{e(l['engine'])}</td></tr>" for l in item["lines"]]
        out.append("</table>")
        if item["reconciliation"]:
            out.append("<h3>Reconciliation</h3><ul>")
            for r in item["reconciliation"]:
                out.append(f"<li class={'ok' if r['agrees'] else 'bad'}>{r['amount']:,.0f}: "
                           + (f"agrees with {len(r['documents'])} {e(r['document_type'])} ({', '.join(r['documents'])}) totalling {r['total']:,.0f}"
                              if r["agrees"] else "no matching set of source documents") + "</li>")
            out.append("</ul>")
        if item["issues"]:
            out.append("<h3>Issues raised and how they were settled</h3>")
            for t in item["issues"]:
                out.append(f"<p><b>{e(t['finding'])} {e(t['title'])}</b> ({e(t['state'])})<br>{e(t['detail'])}</p><ul>")
                out += [f"<li>{e(h['at'][:10])} {e(h['by'])}: {e(h['type'])}{' → ' + e(h['new_value']) if h['new_value'] is not None else ''}"
                        f" - {e(h['what'])}{' (authority: ' + e(h['authority']) + ')' if h['authority'] else ''}"
                        f"{' [amendment]' if h['layer'] == 'amendment' else ''}</li>" for h in t["history"]]
                out.append("</ul>")
        if item["signoffs"]:
            out.append("<h3>Sign-offs</h3><ul>" + "".join(
                f"<li>{e(s['level'])}: {e(s['by'])} on {e(s['at'][:10])} ({'holds' if s['valid'] else 'reopened'}) - {e(s['target'])}</li>"
                for s in item["signoffs"]) + "</ul>")
        if item["client"]:
            out.append("<h3>From the clients</h3><ul>" + "".join(
                f"<li>{e(r)}: {e(pack['client_text'].get(r, ''))}</li>" for r in item["client"]) + "</ul>")
        out.append("<h3>Source documents</h3>")
        for d in item["documents"]:
            out.append(f"<p><b>{e(d['id'])} {e(d['title'])}</b> · received {e(d['received'])}</p>")
            out += [f"<pre>page {e(pg['page'])}: {e(pg['text'])}</pre>" for pg in d["pages"]]
    out.append("</body></html>")
    return "".join(out)
