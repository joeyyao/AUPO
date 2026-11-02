"""JSON file data store.

The assessment requires file-based storage (no database). Every JSON document is
loaded from the ``data/`` directory and cached in memory until its mtime changes,
so editing a file on disk is picked up without a restart.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from .config import DATA_DIR


class DataFileError(RuntimeError):
    """Raised when a data file is missing or malformed."""


class JsonDataStore:
    def __init__(self, data_dir: Path) -> None:
        self._data_dir = data_dir
        self._lock = threading.Lock()
        self._cache: dict[str, tuple[float, Any]] = {}

    def load(self, filename: str) -> Any:
        path = self._data_dir / filename
        if not path.exists():
            raise DataFileError(f"Data file not found: {path}")

        mtime = path.stat().st_mtime
        with self._lock:
            cached = self._cache.get(filename)
            if cached and cached[0] == mtime:
                return cached[1]
            try:
                with path.open(encoding="utf-8") as handle:
                    payload = json.load(handle)
            except json.JSONDecodeError as exc:  # pragma: no cover - defensive
                raise DataFileError(f"{filename} is not valid JSON: {exc}") from exc
            self._cache[filename] = (mtime, payload)
            return payload

    # ---- typed accessors -------------------------------------------------
    def orders(self) -> list[dict[str, Any]]:
        return list(self.load("orders.json").get("orders", []))

    def products(self) -> list[dict[str, Any]]:
        return list(self.load("products.json").get("rows", []))

    def shipments(self) -> list[dict[str, Any]]:
        return list(self.load("shipments.json").get("shipments", []))

    def shipping_rates(self) -> dict[str, Any]:
        return dict(self.load("shipping_rates.json"))


store = JsonDataStore(DATA_DIR)
