"""Findings: what a check concluded, attached to index nodes so the UI can surface it in place.

A finding never edits the packet. If it proposes a correction, the correction is
expressed as line changes plus an estimated tax effect, computed the way the README
prescribes: change x return_versions[-1].tax_effect_rates (credits/payments 1:1).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal

Severity = Literal["error", "warning", "info"]
# error   = the return is wrong as computed (a confident mistake in extraction or engine)
# warning = needs a decision or evidence before filing
# info    = engine already handled / record for completeness

Origin = Literal["extraction", "engine", "client", "document", "process"]
# where the defect came from - this is what tells the reviewer whom to trust next time


@dataclass
class Correction:
    line: str                 # line key in the latest version
    current: float | str | None
    proposed: float | str | None
    category: str | None = None   # tax_effect_rates category, or "payment"/"credit"/"none"


@dataclass
class Finding:
    id: str
    check: str                # check id that produced it
    title: str
    severity: Severity
    origin: Origin
    detail: str
    nodes: list[str]          # index node ids this finding attaches to (lines, evs, docs, qa, ...)
    evidence: list[str] = field(default_factory=list)   # node ids that prove the finding
    corrections: list[Correction] = field(default_factory=list)
    federal_effect: float | None = None    # + means more tax / larger balance due
    california_effect: float | None = None
    effect_note: str | None = None
    generic: bool = True      # True: rule would fire on any packet; False: encodes this household's facts

    def to_dict(self) -> dict:
        return asdict(self)


def estimate_effect(packet, deltas: list[tuple[str, float]]) -> tuple[float, float]:
    """deltas: (category, change in the underlying amount). Returns (federal, california) tax change.

    category 'payment'      : more payments -> lower balance (1:1, both returned on the federal side)
    category 'ca_payment'   : California payment, 1:1 on the California side
    """
    fed = ca = 0.0
    for cat, amt in deltas:
        if cat == "payment":
            fed -= amt
        elif cat == "ca_payment":
            ca -= amt
        elif cat == "none":
            continue
        else:
            rf, rc = packet.tax_effect_rate(cat)
            fed += amt * rf
            ca += amt * rc
    return round(fed), round(ca)
