from __future__ import annotations

from typing import Any

from pymongo.collection import Collection


class MetaRepository:
    def __init__(self, meta: Collection) -> None:
        self._meta = meta

    def get_alerts_sync_meta(self) -> dict[str, Any] | None:
        return self._meta.find_one({"_id": "alerts_sync"})
