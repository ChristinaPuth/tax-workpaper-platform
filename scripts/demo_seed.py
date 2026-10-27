"""Bring a running workpaper to "ready for the partner" (or, with --approved, ready to file) for a demo.

    python scripts/demo_seed.py                       # http://localhost:8000
    python scripts/demo_seed.py http://localhost:8002
    python scripts/demo_seed.py http://localhost:8000 --approved   # also partner sign-off and both clients' approval

What it does is in app/demo.py. Run it on an empty database (a fresh var/ folder); it stops at the first refusal.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.demo import SeedError, seed  # noqa: E402


def main(base: str, approved: bool) -> None:
    with httpx.Client(base_url=base, timeout=120) as c:
        for _ in range(30):  # the server may still be starting (e.g. right after docker run)
            try:
                c.get("/api/overview")
                break
            except httpx.TransportError:
                time.sleep(1)
        try:
            seed(c, approved)
        except SeedError as e:
            sys.exit(str(e))


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    main(args[0] if args else "http://localhost:8000", approved="--approved" in sys.argv)
