"""FastAPI app: load the packet once at startup, build the index, run every check.

app/api.py is read-only over the packet; app/events_api.py is the only write surface - an
append-only event log (app/db.py) keyed by the same node ids the index defines, behind the
role checks in app/people.py, fanned out live over SSE (app/live.py).

    uvicorn app.main:app --reload
"""
from __future__ import annotations

import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from workpaper.checks import run_all
from workpaper.findings import Finding
from workpaper.index import Index
from workpaper.linking import link_findings
from workpaper.packet import Packet
from workpaper.packet import packet_path as default_packet_path

from .api import router
from .db import make_engine
from .events_api import router as events_router
from .live import Broker
from .documents import page_coverage
from .people import directory

FRONTEND_DIST = Path(__file__).resolve().parents[1] / "frontend" / "dist"


@dataclass
class Store:
    packet: Packet
    index: Index
    findings: list[Finding]
    verified: list[dict]
    coverage: dict[str, dict] = field(default_factory=dict)
    loaded_in: float = 0.0


@lru_cache(maxsize=2)  # the packet is read-only, so one load serves every app in the process
def load_store(packet_path: str) -> Store:
    t0 = time.monotonic()
    p = Packet.load(packet_path)
    ix = Index(p)
    ctx = run_all(p, ix)
    link_findings(ctx)
    coverage = {d["id"]: page_coverage(p, d["id"]) for d in p.documents}
    return Store(packet=p, index=ix, findings=ctx.findings, verified=ctx.verified, coverage=coverage,
                 loaded_in=time.monotonic() - t0)


def create_app(packet_path: str | None = None, database_url: str | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.store = load_store(packet_path or str(default_packet_path()))
        app.state.people = directory(app.state.store.packet)
        app.state.db = make_engine(database_url)
        app.state.broker = Broker()
        yield
        app.state.db.dispose()

    app = FastAPI(title="Okafor-Lindqvist Workpaper API", version="2b", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
    app.include_router(router)
    app.include_router(events_router)
    if FRONTEND_DIST.is_dir():  # the built React app, served from the same origin as the API
        app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
    return app


app = create_app()
