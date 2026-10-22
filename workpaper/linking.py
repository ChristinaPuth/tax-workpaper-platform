"""Cross-reference findings that touch the same line or value, after all checks have run.

Shared by run_checks.py (CLI) and app/main.py (API) so both see identical results: the
checks themselves only know about one finding at a time, this pass relates them to each
other and to the documents they cite.
"""
from __future__ import annotations

from collections import defaultdict


def link_findings(ctx) -> None:
    by_node = defaultdict(list)
    for f in ctx.findings:
        for n in f.nodes:
            if n.startswith(("line:", "ev:")):
                by_node[n].append(f)
    for f in ctx.findings:
        related = {g.id for n in f.nodes if n.startswith(("line:", "ev:")) for g in by_node[n] if g.id != f.id}
        f.related = sorted(related)
    # a document the engine ignored but a finding relies on is not "unused" - it is the evidence
    cited = defaultdict(set)
    for f in ctx.findings:
        if f.check.startswith("P6"):
            continue
        for n in f.evidence + f.nodes:
            doc = ctx.ix.doc_of(n) if n.startswith(("page:", "ev:", "doc:")) else None
            if doc:
                cited[doc].add(f.id)
    for f in ctx.findings:
        if f.check.startswith("P6") and f.nodes and f.nodes[0] in cited and f.severity == "warning":
            ids = ", ".join(sorted(cited[f.nodes[0]]))
            f.severity = "info"
            f.detail += f" Not an engine input, but it is the evidence for {ids}."
    # variance lines explained by an error finding on the same line
    for f in ctx.findings:
        if f.check.startswith("P5"):
            errs = [g for g in by_node.get(f.nodes[0], []) if g.severity == "error"]
            if errs:
                f.detail += " Partly explained by " + ", ".join(g.id for g in errs) + "."
