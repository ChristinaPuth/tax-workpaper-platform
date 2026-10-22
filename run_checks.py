"""Build the index, run every check, write machine- and human-readable outputs.

    python run_checks.py [packet.json] [out_dir]
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

from workpaper.checks import run_all
from workpaper.index import Index
from workpaper.linking import link_findings
from workpaper.packet import Packet, packet_path
from workpaper.report import render


def main(path: str | None = None, out_dir: str = "out") -> None:
    out = Path(out_dir)
    out.mkdir(exist_ok=True)
    p = Packet.load(path or packet_path())
    ix = Index(p)
    ctx = run_all(p, ix)
    link_findings(ctx)

    (out / "index.json").write_text(json.dumps(ix.to_json()), encoding="utf-8")
    landing = {d["id"]: ix.document_landing(d["id"]) for d in p.documents}
    (out / "document_landing.json").write_text(json.dumps(landing, indent=1), encoding="utf-8")
    findings = [dict(f.to_dict(), related=getattr(f, "related", [])) for f in ctx.findings]
    (out / "findings.json").write_text(json.dumps({"findings": findings, "verified": ctx.verified,
                                                  "index_stats": ix.stats()}, indent=1), encoding="utf-8")

    (out / "errors.md").write_text(render(findings, ctx.verified, ix.stats()), encoding="utf-8")

    sev = Counter(f.severity for f in ctx.findings)
    print(f"index: {ix.stats()['nodes']} nodes, {ix.stats()['edges']} edges, {ix.stats()['unresolved_refs']} unresolved refs")
    print(f"findings: {len(ctx.findings)} ({dict(sev)}), independent recomputations agreeing: {len(ctx.verified)}")
    errors = [f for f in ctx.findings if f.severity == "error"]
    fed = sum(f.federal_effect or 0 for f in errors)
    ca = sum(f.california_effect or 0 for f in errors)
    print(f"errors: {len(errors)}; estimated net effect if all corrected: federal {fed:+,.0f}, California {ca:+,.0f}")


if __name__ == "__main__":
    main(*sys.argv[1:])
