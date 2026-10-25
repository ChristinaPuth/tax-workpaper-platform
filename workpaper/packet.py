"""Load the delivered packet as-is and expose read-only lookups.

The packet is never modified. Everything the workpaper adds (findings, reviews,
adjustments) lives in separate layers keyed by the node ids defined in index.py.
"""
from __future__ import annotations

import json
import os
import re
from functools import cached_property
from pathlib import Path
from typing import Any

# The packet as delivered, unmodified. Override with PACKET_PATH (e.g. in a container).
DEFAULT_PACKET_PATH = Path(__file__).resolve().parents[1] / "data" / "okafor_lindqvist_2025_packet.json"


def packet_path() -> Path:
    return Path(os.environ.get("PACKET_PATH", DEFAULT_PACKET_PATH))


class Packet:
    def __init__(self, raw: dict[str, Any]):
        self.raw = raw

    @classmethod
    def load(cls, path: str | Path) -> "Packet":
        with open(path, encoding="utf-8") as f:
            return cls(json.load(f))

    # ---- top-level sections -------------------------------------------------
    @property
    def tax_year(self) -> int:
        return self.raw["household"]["tax_year"]

    @property
    def household(self) -> dict:
        return self.raw["household"]

    @property
    def documents(self) -> list[dict]:
        return self.raw["documents"]

    @property
    def extracted_values(self) -> list[dict]:
        return self.raw["extracted_values"]

    @property
    def versions(self) -> list[dict]:
        return self.raw["return_versions"]

    @property
    def latest(self) -> dict:
        return self.versions[-1]

    @property
    def params(self) -> dict:
        return self.raw["engine_reference"]["parameters"]

    @property
    def rules(self) -> dict:
        return self.raw["engine_reference"]["rules"]

    @property
    def client(self) -> dict:
        return self.raw["client"]

    @property
    def prior(self) -> dict:
        return self.raw["prior_years"]

    @property
    def agency(self) -> dict:
        return self.raw["tax_agency_records"]

    @property
    def firm(self) -> dict:
        return self.raw["firm"]

    # ---- lookups --------------------------------------------------------------
    @cached_property
    def doc(self) -> dict[str, dict]:
        return {d["id"]: d for d in self.documents}

    @cached_property
    def ev(self) -> dict[str, dict]:
        return {e["id"]: e for e in self.extracted_values}

    @cached_property
    def ev_by_doc(self) -> dict[str, list[dict]]:
        out: dict[str, list[dict]] = {}
        for e in self.extracted_values:
            out.setdefault(e["document_id"], []).append(e)
        return out

    @cached_property
    def page_text(self) -> dict[tuple[str, int], str]:
        return {(d["id"], p["page"]): p["printed_content"] for d in self.documents for p in d["pages"]}

    @cached_property
    def version(self) -> dict[str, dict]:
        return {v["version"]: v for v in self.versions}

    @cached_property
    def lines(self) -> dict[str, dict[str, dict]]:
        """lines[version][key] -> line"""
        return {v["version"]: {l["key"]: l for l in v["lines"]} for v in self.versions}

    def line(self, key: str, version: str | None = None) -> dict | None:
        return self.lines[version or self.latest["version"]].get(key)

    def line_value(self, key: str, version: str | None = None, default=0):
        l = self.line(key, version)
        return default if l is None else l["value"]

    @cached_property
    def qa(self) -> dict[str, dict]:
        return {q["id"]: q for q in self.client["questionnaire"]}

    @cached_property
    def msg(self) -> dict[str, dict]:
        return {m["id"]: m for m in self.client["messages"]}

    @cached_property
    def call(self) -> dict[str, dict]:
        return {c["id"]: c for c in self.client["call_notes"]}

    @cached_property
    def person(self) -> dict[str, dict]:
        return {p["id"]: p for p in self.household["people"]}

    def tax_effect_rate(self, category: str, version: str | None = None) -> tuple[float, float]:
        r = self.version[version or self.latest["version"]]["tax_effect_rates"][category]
        return r["federal_per_dollar"], r["california_per_dollar"]

    def ca_resident_on(self, iso_date: str) -> bool:
        return any(r["state"] == "CA" and r["status"] == "resident" and r["from"] <= iso_date <= r["to"]
                   for r in self.household["residency"])

    def california_category(self, key: str, version: str | None = None) -> str | None:
        """'ca_source_income' when a line is fully California-source, so its California effect uses that rate
        (README: "a sale during California residency, the Sacramento rental"); None for the usual rate."""
        line = self.line(key, version)
        if line is None:
            return None
        form, _, rest = key.partition(".")
        if form == "F8949":
            sold = next((self.ev[s]["value"] for s in line.get("sources", [])
                         if s in self.ev and self.ev[s]["field"].endswith("_sold")), None)
            return "ca_source_income" if sold and self.ca_resident_on(sold) else None
        if form in ("SchE", "F4562-E") and key[-1].isupper():   # property lines end in the property letter
            prop = self.line(f"SchE.1{key[-1]}", version)
            return "ca_source_income" if prop and re.search(r",\s*[A-Za-z .]+ CA\b", str(prop["value"])) else None
        return None

    def resolve_pointer(self, root: str, pointer: str) -> Any:
        """Resolve an RFC 6901 JSON pointer inside prior_years (py) or tax_agency_records (agency)."""
        node: Any = self.prior if root == "py" else self.agency
        for raw in pointer.strip("/").split("/"):
            if raw == "":
                continue
            part = raw.replace("~1", "/").replace("~0", "~")
            node = node[int(part)] if isinstance(node, list) else node[part]
        return node
