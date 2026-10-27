"""One copy of the workpaper per visitor, for a public demo (SANDBOX_PER_VISITOR=1).

The browser makes up a sandbox id for each tab (sessionStorage) and sends it with every request
(X-Sandbox header, or ?sandbox= for the live stream). Each id gets its own SQLite file under
SANDBOX_DIR, created on first use from the empty schema - so a visitor starts from the packet as
delivered, a reload keeps their work, and a new tab starts over. Visitors never see each other's
events, live updates included. Requests without an id use the shared database as before.

Nothing else changes: app.state.db and app.state.broker are stand-ins that pick the current
visitor's engine and broker, so the rest of the app is unaware of sandboxes. Old sandboxes are
deleted after SANDBOX_MAX_AGE_HOURS, and at most SANDBOX_MAX are kept.
"""
from __future__ import annotations

import os
import re
import threading
import time
from contextvars import ContextVar
from pathlib import Path
from urllib.parse import parse_qs

from sqlalchemy.engine import Engine

from .db import make_engine
from .live import Broker

CURRENT: ContextVar[str | None] = ContextVar("sandbox", default=None)
VALID = re.compile(r"^[a-z0-9]{8,40}$")


def enabled() -> bool:
    return os.environ.get("SANDBOX_PER_VISITOR", "").lower() in ("1", "true", "yes")


class Sandboxes:
    def __init__(self, shared: Engine, folder: Path | None = None):
        self.shared = shared
        self.folder = folder or Path(os.environ.get("SANDBOX_DIR", "var/sandboxes"))
        self.folder.mkdir(parents=True, exist_ok=True)
        self.max_age = float(os.environ.get("SANDBOX_MAX_AGE_HOURS", "48")) * 3600
        self.max_count = int(os.environ.get("SANDBOX_MAX", "300"))
        self.engines: dict[str, Engine] = {}
        self.brokers: dict[str, Broker] = {}
        self.shared_broker = Broker()
        self.lock = threading.Lock()

    def engine(self) -> Engine:
        sid = CURRENT.get()
        if sid is None:
            return self.shared
        with self.lock:
            eng = self.engines.get(sid)
            if eng is None:
                path = self.folder / f"{sid}.db"
                if not path.exists():
                    self._prune()
                eng = self.engines[sid] = make_engine(f"sqlite:///{path}")
            return eng

    def broker(self) -> Broker:
        sid = CURRENT.get()
        if sid is None:
            return self.shared_broker
        with self.lock:
            return self.brokers.setdefault(sid, Broker())

    def _prune(self) -> None:
        """Delete sandboxes nobody has touched for a while, and the oldest beyond the cap."""
        files = sorted(self.folder.glob("*.db"), key=lambda f: f.stat().st_mtime)
        cutoff = time.time() - self.max_age
        doomed = [f for f in files if f.stat().st_mtime < cutoff]
        keep = [f for f in files if f not in doomed]
        doomed += keep[: max(0, len(keep) - self.max_count + 1)]
        for f in doomed:
            sid = f.stem
            if sid in self.engines:
                self.engines.pop(sid).dispose()
                self.brokers.pop(sid, None)
            for extra in (f, f.with_name(f.name + "-wal"), f.with_name(f.name + "-shm")):
                extra.unlink(missing_ok=True)

    def dispose(self) -> None:
        for eng in self.engines.values():
            eng.dispose()
        self.shared.dispose()


class EngineProxy:
    """Stands in for app.state.db: every use goes to the current visitor's engine."""

    def __init__(self, sandboxes: Sandboxes):
        self._sandboxes = sandboxes

    def __getattr__(self, name):
        return getattr(self._sandboxes.engine(), name)

    def dispose(self) -> None:
        self._sandboxes.dispose()


class BrokerProxy:
    """Stands in for app.state.broker: live updates stay inside one visitor's sandbox."""

    def __init__(self, sandboxes: Sandboxes):
        self._sandboxes = sandboxes

    def __getattr__(self, name):
        return getattr(self._sandboxes.broker(), name)


class SandboxMiddleware:
    """Reads the visitor's sandbox id for the duration of each request."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not scope.get("path", "").startswith("/api/"):
            return await self.app(scope, receive, send)
        sid = dict(scope.get("headers") or []).get(b"x-sandbox", b"").decode() or \
            (parse_qs(scope.get("query_string", b"").decode()).get("sandbox") or [""])[0]
        if sid and not VALID.match(sid):
            body = b'{"detail": "sandbox id is 8-40 lowercase letters or digits"}'
            await send({"type": "http.response.start", "status": 400,
                        "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())]})
            return await send({"type": "http.response.body", "body": body})
        token = CURRENT.set(sid or None)
        try:
            await self.app(scope, receive, send)
        finally:
            CURRENT.reset(token)
