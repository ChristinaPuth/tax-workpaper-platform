"""Live updates: every appended event is fanned out to open browser tabs over Server-Sent Events.

One process, in-memory subscriber queues - enough for "several people at once" on one return.
A reconnecting client sends Last-Event-ID and is replayed what it missed from the log first.

Streams end when the server is asked to stop. Uvicorn waits for open connections to close before
it shuts down, and an SSE stream never closes on its own - without this, every redeploy and every
--reload would hang while a browser tab is open. The browser's EventSource reconnects by itself.
"""
from __future__ import annotations

import asyncio
import json
import signal
import threading
import time
from typing import AsyncIterator, Callable

HEARTBEAT_SECONDS = 15
POLL_SECONDS = 0.5  # how quickly an open stream notices that the server is stopping

SHUTTING_DOWN = threading.Event()


def install_exit_signal_hook() -> None:
    """Wrap whatever SIGINT/SIGTERM handler is installed now so it first sets SHUTTING_DOWN.

    Called from the app's startup, which uvicorn runs after it has installed its own handlers
    (it binds them before loading the app, so patching uvicorn's class would be too late). The
    wrapped handler still runs, so uvicorn's graceful shutdown proceeds as before.
    """
    if threading.current_thread() is not threading.main_thread():  # e.g. the test client's portal thread
        return
    SHUTTING_DOWN.clear()
    for sig in (signal.SIGINT, signal.SIGTERM):
        prev = signal.getsignal(sig)
        if getattr(prev, "_workpaper_hook", False):
            continue

        def hook(s, frame, prev=prev):
            SHUTTING_DOWN.set()
            if callable(prev):
                prev(s, frame)
            elif prev == signal.SIG_DFL:
                signal.signal(s, signal.SIG_DFL)
                signal.raise_signal(s)

        hook._workpaper_hook = True  # type: ignore[attr-defined]
        signal.signal(sig, hook)


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
                 heartbeat: float = HEARTBEAT_SECONDS,
                 stopping: threading.Event = SHUTTING_DOWN) -> AsyncIterator[str]:
    q = broker.subscribe()  # subscribe before replaying so nothing falls between the two
    try:
        sent = 0
        for ev in missed():
            sent = ev["id"]
            yield sse(ev)
        last_beat = time.monotonic()
        while not stopping.is_set():
            if is_disconnected is not None and await is_disconnected():
                return
            try:
                ev = await asyncio.wait_for(q.get(), timeout=POLL_SECONDS)
            except asyncio.TimeoutError:
                if time.monotonic() - last_beat >= heartbeat:
                    last_beat = time.monotonic()
                    yield ": keep-alive\n\n"
                continue
            if ev["id"] > sent:
                yield sse(ev)
    finally:
        broker.unsubscribe(q)
