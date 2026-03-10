from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from pymongo import UpdateOne
from pymongo.database import Database

from ..database import MongoSettings
from ..document_builders import build_alert_document
from ..time_utils import UTC

HISTORICAL_ALERTS_URL = "https://www.tzevaadom.co.il/static/historical/all.json"
DEFAULT_SYNC_TIMEOUT = 60
DEFAULT_OVERLAP_SECONDS = 3600
DEFAULT_BATCH_SIZE = 1000


@dataclass(frozen=True)
class AlertSyncResult:
    fetched_rows: int
    skipped_old_rows: int
    skipped_invalid_rows: int
    candidate_rows: int
    upserted_count: int
    modified_count: int
    latest_timestamp: int
    total_records: int


class AlertSyncService:
    def __init__(self, db: Database, settings: MongoSettings) -> None:
        self._db = db
        self._settings = settings
        self._alerts = db[settings.alerts_collection]
        self._meta = db[settings.meta_collection]

    @staticmethod
    def fetch_rows(url: str, timeout: int) -> list[list[Any]]:
        request = Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; RedAlertUpdater/1.0)",
                "Accept": "application/json",
            },
        )

        try:
            with urlopen(request, timeout=timeout) as response:
                charset = response.headers.get_content_charset() or "utf-8"
                payload = response.read().decode(charset)
        except HTTPError as exc:
            raise RuntimeError(f"HTTP error while fetching {url}: {exc.code} {exc.reason}") from exc
        except URLError as exc:
            raise RuntimeError(f"Network error while fetching {url}: {exc.reason}") from exc

        try:
            data = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"API returned invalid JSON: {exc}") from exc

        if not isinstance(data, list):
            raise RuntimeError("Expected API payload to be a top-level JSON array.")

        return data

    def latest_timestamp(self) -> int:
        latest = self._alerts.find_one(
            {},
            projection={"timestamp": True, "_id": False},
            sort=[("timestamp", -1)],
        )
        if not latest or not isinstance(latest.get("timestamp"), int):
            return 0
        return int(latest["timestamp"])

    def sync_from_history_api(
        self,
        url: str = HISTORICAL_ALERTS_URL,
        timeout: int = DEFAULT_SYNC_TIMEOUT,
        overlap_seconds: int = DEFAULT_OVERLAP_SECONDS,
        batch_size: int = DEFAULT_BATCH_SIZE,
        source: str = "historical_api",
    ) -> AlertSyncResult:
        max_timestamp = self.latest_timestamp()
        cutoff_timestamp = max(0, max_timestamp - max(0, overlap_seconds))
        fetched_rows = self.fetch_rows(url, timeout)

        operations: list[Any] = []
        skipped_old = 0
        skipped_invalid = 0
        candidate_rows = 0
        latest_seen_timestamp = max_timestamp

        for row in fetched_rows:
            if not isinstance(row, list) or len(row) != 4:
                skipped_invalid += 1
                continue

            code, kind, areas, timestamp = row
            if not isinstance(code, int) or not isinstance(kind, int) or not isinstance(timestamp, int):
                skipped_invalid += 1
                continue
            if not isinstance(areas, list) or not all(isinstance(area, str) for area in areas):
                skipped_invalid += 1
                continue
            if timestamp < cutoff_timestamp:
                skipped_old += 1
                continue

            latest_seen_timestamp = max(latest_seen_timestamp, timestamp)
            doc = build_alert_document(code, kind, areas, timestamp, source=source)
            operations.append(UpdateOne({"_id": doc["_id"]}, {"$set": doc}, upsert=True))
            candidate_rows += 1

        upserted = 0
        modified = 0
        for offset in range(0, len(operations), batch_size):
            chunk = operations[offset : offset + batch_size]
            if not chunk:
                continue
            result = self._alerts.bulk_write(chunk, ordered=False)
            upserted += result.upserted_count
            modified += result.modified_count

        total_records = self._alerts.count_documents({})
        self._meta.update_one(
            {"_id": "alerts_sync"},
            {
                "$set": {
                    "source": source,
                    "source_url": url,
                    "last_synced_at": datetime.now(UTC),
                    "latest_timestamp": latest_seen_timestamp,
                    "document_count": total_records,
                }
            },
            upsert=True,
        )

        return AlertSyncResult(
            fetched_rows=len(fetched_rows),
            skipped_old_rows=skipped_old,
            skipped_invalid_rows=skipped_invalid,
            candidate_rows=candidate_rows,
            upserted_count=upserted,
            modified_count=modified,
            latest_timestamp=latest_seen_timestamp,
            total_records=total_records,
        )
