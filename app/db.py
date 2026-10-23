"""Persistence for everything the workpaper adds on top of the packet.

The packet stays the immutable base layer. What people do - notes, questions, verifications,
adjustments, sign-offs, undo - is an append-only event log keyed by the index's node ids.
Current state = packet + events applied in order; nothing here is ever updated or deleted.

    DATABASE_URL=sqlite:///var/workpaper.db   (default)
    DATABASE_URL=postgresql+psycopg://...      (same code, if we ever switch)
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import (JSON, Column, DateTime, Integer, LargeBinary, MetaData, String, Table, Text,
                        create_engine, event, insert, select)
from sqlalchemy.engine import Engine

DEFAULT_DB = Path(__file__).resolve().parents[1] / "var" / "workpaper.db"

metadata = MetaData()

events = Table(
    "events", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("at", DateTime(timezone=True), nullable=False),
    Column("actor", String(16), nullable=False),          # firm staff id (st-01) or client user id (cu-01)
    Column("role", String(32), nullable=False),           # role at the time of the event
    Column("type", String(32), nullable=False),           # see people.EVENT_TYPES
    Column("target", String(200), index=True),            # index node id (line:v3:SchC.1, ev:ev-0127, doc:D23 ...)
    Column("payload", JSON, nullable=False, default=dict),
    Column("batch_id", String(64), index=True),           # bulk actions share one id so they undo together
    Column("layer", String(32), nullable=False, default="return"),  # "return" or "amendment-1" after filing
)

snapshots = Table(
    "snapshots", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("at", DateTime(timezone=True), nullable=False),
    Column("kind", String(16), nullable=False),           # signoff | filing
    Column("event_id", Integer, nullable=False),          # the event that created it
    Column("scope", JSON, nullable=False),                # node ids covered
    Column("hash", String(64), nullable=False),
    Column("content", JSON, nullable=False),              # what was signed / filed, for "what changed since"
)

attachments = Table(
    "attachments", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("at", DateTime(timezone=True), nullable=False),
    Column("actor", String(16), nullable=False),
    Column("filename", Text, nullable=False),
    Column("mime", String(100), nullable=False),
    Column("data", LargeBinary, nullable=False),
)

user_state = Table(
    "user_state", metadata,
    Column("actor", String(16), primary_key=True),
    Column("last_seen_event_id", Integer, nullable=False, default=0),
)


def database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if url:
        return url
    DEFAULT_DB.parent.mkdir(exist_ok=True)
    return f"sqlite:///{DEFAULT_DB}"


def make_engine(url: str | None = None) -> Engine:
    url = url or database_url()
    eng = create_engine(url, future=True)
    if url.startswith("sqlite"):
        @event.listens_for(eng, "connect")
        def _wal(conn, _):  # readers do not block the writer (SSE clients + API in one process)
            conn.execute("PRAGMA journal_mode=WAL")
    metadata.create_all(eng)
    return eng


def now() -> datetime:
    return datetime.now(timezone.utc)


def append_event(eng: Engine, **row) -> dict:
    row.setdefault("at", now())
    row.setdefault("payload", {})
    row.setdefault("layer", "return")
    with eng.begin() as conn:
        rid = conn.execute(insert(events).values(**row)).inserted_primary_key[0]
    return dict(row, id=rid)


def read_events(eng: Engine, *, target: str | None = None, types: list[str] | None = None,
                after: int = 0, limit: int | None = None) -> list[dict]:
    q = select(events).where(events.c.id > after).order_by(events.c.id)
    if target:
        q = q.where(events.c.target == target)
    if types:
        q = q.where(events.c.type.in_(types))
    if limit:
        q = q.limit(limit)
    with eng.connect() as conn:
        return [event_dict(r._mapping) for r in conn.execute(q)]


def get_event(eng: Engine, event_id: int) -> dict | None:
    with eng.connect() as conn:
        r = conn.execute(select(events).where(events.c.id == event_id)).first()
    return event_dict(r._mapping) if r else None


def event_dict(m) -> dict:
    d = dict(m)
    at = d["at"]
    if at.tzinfo is None:  # SQLite drops the offset; everything is written in UTC
        at = at.replace(tzinfo=timezone.utc)
    d["at"] = at.isoformat()
    return d


def last_seen(eng: Engine, actor: str) -> int:
    with eng.connect() as conn:
        r = conn.execute(select(user_state.c.last_seen_event_id).where(user_state.c.actor == actor)).first()
    return r[0] if r else 0


def mark_seen(eng: Engine, actor: str, event_id: int) -> None:
    with eng.begin() as conn:
        cur = conn.execute(select(user_state).where(user_state.c.actor == actor)).first()
        if cur is None:
            conn.execute(insert(user_state).values(actor=actor, last_seen_event_id=event_id))
        elif event_id > cur._mapping["last_seen_event_id"]:
            conn.execute(user_state.update().where(user_state.c.actor == actor)
                         .values(last_seen_event_id=event_id))


def put_snapshot(eng: Engine, *, kind: str, event_id: int, scope: list[str], hash: str, content: dict) -> None:
    with eng.begin() as conn:
        conn.execute(insert(snapshots).values(at=now(), kind=kind, event_id=event_id, scope=scope, hash=hash,
                                              content=content))


def snapshots_for(eng: Engine, kind: str) -> dict[int, dict]:
    """event_id -> snapshot, for every snapshot of a kind."""
    with eng.connect() as conn:
        rows = conn.execute(select(snapshots).where(snapshots.c.kind == kind)).all()
    return {r._mapping["event_id"]: dict(r._mapping) for r in rows}
