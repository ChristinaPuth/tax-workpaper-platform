"""Live updates: every appended event is fanned out to open browser tabs over Server-Sent Events.

One process, in-memory subscriber queues - enough for "several people at once" on one return.
A reconnecting client sends Last-Event-ID and is replayed what it missed from the log first.
"""
from __future__ import annotations

import asyncio
import json
from typing import AsyncIterator, Callable

HEARTBEAT_SECONDS = 15


class Broker:
    def __init__(self) -> None:
        self._subs: set[asyncio.Queue] = set()

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=1000)
        self._subs.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._subs.discard(q)

    def publish(self, ev: dict) -> None:
        for q in list(self._subs):
            try:
                q.put_nowait(ev)
            except asyncio.QueueFull:  # a stalled tab; it will resync from Last-Event-ID on reconnect
                self._subs.discard(q)

    @property
    def subscribers(self) -> int:
        return len(self._subs)


def sse(ev: dict) -> str:
    return f"id: {ev['id']}\nevent: {ev['type']}\ndata: {json.dumps(ev, default=str)}\n\n"


async def stream(broker: Broker, missed: Callable[[], list[dict]], *,
                 is_disconnected: Callable[[], "asyncio.Future[bool]"] | None = None,
                 heartbeat: float = HEARTBEAT_SECONDS) -> AsyncIterator[str]:
    q = broker.subscribe()  # subscribe before replaying so nothing falls between the two
    try:
        sent = 0
        for ev in missed():
            sent = ev["id"]
            yield sse(ev)
        while True:
            if is_disconnected is not None and await is_disconnected():
                return
            try:
                ev = await asyncio.wait_for(q.get(), timeout=heartbeat)
            except asyncio.TimeoutError:
                yield ": keep-alive\n\n"
                continue
            if ev["id"] > sent:
                yield sse(ev)
    finally:
        broker.unsubscribe(q)
