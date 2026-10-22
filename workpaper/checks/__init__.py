"""Run every check in order. Order matters only for J13, which annotates earlier findings."""
from __future__ import annotations

from ..index import Index
from ..packet import Packet
from . import extraction, judgment, recompute, reconcile  # noqa: F401  (registration side effect)
from .base import CHECKS, Ctx


def run_all(packet: Packet, index: Index | None = None) -> Ctx:
    ctx = Ctx(packet, index or Index(packet))
    for _, fn in CHECKS:
        fn(ctx)
    return ctx
