"""Check registry and shared helpers."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Callable

from ..findings import Correction, Finding, estimate_effect
from ..index import Index
from ..packet import Packet

CHECKS: list[tuple[str, Callable]] = []


def check(check_id: str):
    def deco(fn):
        CHECKS.append((check_id, fn))
        fn.check_id = check_id
        return fn
    return deco


@dataclass
class Ctx:
    p: Packet
    ix: Index
    findings: list[Finding] = field(default_factory=list)
    verified: list[dict] = field(default_factory=list)   # independent recomputations that agreed
    _n: int = 0

    @property
    def ver(self) -> str:
        return self.p.latest["version"]

    def L(self, key: str) -> str:
        return f"line:{self.ver}:{key}"

    def add(self, check_id: str, title: str, severity: str, origin: str, detail: str, nodes: list[str],
            evidence: list[str] | None = None, corrections: list[Correction] | None = None,
            deltas: list[tuple[str, float]] | None = None, effect: tuple[float, float] | None = None,
            effect_note: str | None = None, generic: bool = True) -> Finding:
        self._n += 1
        fed = ca = None
        if effect is not None:
            fed, ca = effect
        elif deltas:
            fed, ca = estimate_effect(self.p, deltas)
        nodes = [n for n in nodes if n]
        for corr in corrections or []:  # a finding also attaches to every line it proposes to change
            lid = self.L(corr.line)
            if lid in self.ix.nodes and lid not in nodes:
                nodes.append(lid)
        f = Finding(id=f"F-{self._n:03d}", check=check_id, title=title, severity=severity, origin=origin,
                    detail=detail, nodes=nodes, evidence=[e for e in (evidence or []) if e],
                    corrections=corrections or [], federal_effect=fed, california_effect=ca,
                    effect_note=effect_note, generic=generic)
        self.findings.append(f)
        return f

    def ok(self, check_id: str, what: str, engine: float, independent: float, nodes: list[str]) -> None:
        self.verified.append({"check": check_id, "what": what, "engine": engine, "independent": independent,
                              "nodes": nodes})

    # ---- helpers -------------------------------------------------------------
    def ev_lines(self, ev_id: str) -> list[str]:
        """Latest-version lines that cite this extracted value directly."""
        return [s for s in self.ix.sources(f"ev:{ev_id}", "sourced_from") if s.startswith(f"line:{self.ver}:")]


MONEY = re.compile(r"-?\(?\$?\d[\d,]*(?:\.\d+)?\)?")


def to_num(s: str) -> float | None:
    t = s.strip("-()$").replace(",", "")
    try:
        return float(t)
    except ValueError:
        return None


def numbers_in(text: str) -> set[float]:
    out = set()
    for m in MONEY.findall(text):
        v = to_num(m)
        if v is not None:
            out.add(round(v, 2))
    return out


def date_forms(iso: str) -> list[str]:
    y, m, d = iso.split("-")
    return [iso, f"{m}/{d}/{y}", f"{int(m)}/{int(d)}/{y}"]


def held_long_term(acquired: str, sold: str) -> bool:
    a, s = date.fromisoformat(acquired), date.fromisoformat(sold)
    try:
        anniv = a.replace(year=a.year + 1)
    except ValueError:  # Feb 29
        anniv = a.replace(year=a.year + 1, day=28)
    return s > anniv


def fmt(x) -> str:
    if isinstance(x, (int, float)):
        return f"{x:,.2f}".rstrip("0").rstrip(".") if isinstance(x, float) and x != int(x) else f"{int(x):,}"
    return str(x)
