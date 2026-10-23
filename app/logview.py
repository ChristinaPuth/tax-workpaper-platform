"""The event log read as current state: what is undone, what is live, what each node has had done to it.

Every derived view (the Inbox, sign-off status, the filing gate) reads the log through this, so they
agree on what "undone", "resolved" and "answered" mean.
"""
from __future__ import annotations

from collections import defaultdict


class LogView:
    def __init__(self, events: list[dict]):
        self.undone = {e["payload"].get("event_id") for e in events if e["type"] == "undo"}
        self.live = [e for e in events if e["id"] not in self.undone and e["type"] != "undo"]
        self.by_target: dict[str, list[dict]] = defaultdict(list)
        for e in self.live:
            if e.get("target"):
                self.by_target[e["target"]].append(e)
        self.resolved_notes = {e["payload"].get("event_id") for e in self.live if e["type"] == "resolve_note"}
        self.answered = {e["payload"].get("event_id") for e in self.live if e["type"] == "answer"}

    def last(self, target: str, etype: str) -> dict | None:
        es = [e for e in self.by_target.get(target, []) if e["type"] == etype]
        return es[-1] if es else None

    def signed_after(self, target: str, after_id: int, levels: tuple[str, ...], not_by: str | None = None) -> bool:
        return any(e["type"] == "signoff" and e["id"] > after_id and e["payload"].get("level") in levels
                   and e["actor"] != not_by for e in self.by_target.get(target, []))

    def by_actor(self, actor: str, types: tuple[str, ...]) -> list[dict]:
        return [e for e in self.live if e["actor"] == actor and e["type"] in types]

    def of_type(self, *types: str) -> list[dict]:
        return [e for e in self.live if e["type"] in types]
