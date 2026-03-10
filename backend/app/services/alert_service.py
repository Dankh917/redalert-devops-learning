from __future__ import annotations

import logging
import threading
from datetime import datetime
from typing import Any

from ..database import create_mongo_client, ensure_indexes, get_database, load_mongo_settings
from ..repositories.alerts_repository import AlertsRepository
from ..repositories.meta_repository import MetaRepository
from .alert_sync_service import AlertSyncService
from ..time_utils import JERUSALEM_TIMEZONE_NAME, UTC, timestamp_to_jerusalem_iso, utc_to_jerusalem

logger = logging.getLogger(__name__)


class AlertService:
    RECENT_ALERT_WINDOW_SECONDS = 60
    AUTO_REFRESH_COOLDOWN_SECONDS = 20
    AUTO_REFRESH_TIMEOUT_SECONDS = 10

    def __init__(self, mongo_uri: str | None = None, database_name: str | None = None) -> None:
        self._settings = load_mongo_settings(mongo_uri, database_name)
        self._client = create_mongo_client(self._settings.uri)
        self._db = get_database(self._client, self._settings)
        ensure_indexes(self._db, self._settings)

        self._alerts_repository = AlertsRepository(
            self._db[self._settings.alerts_collection],
            self._settings,
        )
        self._meta_repository = MetaRepository(self._db[self._settings.meta_collection])
        self._alert_sync_service = AlertSyncService(self._db, self._settings)
        self._auto_refresh_lock = threading.Lock()
        self._last_auto_refresh_at: datetime | None = None

    @staticmethod
    def _format_meta_datetime(value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            if value.tzinfo is None:
                value = value.replace(tzinfo=UTC)
            return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
        return None

    def _maybe_refresh_recent_alerts(self) -> None:
        latest_alert = self._alerts_repository.get_latest_alert()
        latest_timestamp = int(latest_alert["timestamp"]) if latest_alert and latest_alert.get("timestamp") else 0
        if not latest_timestamp:
            return

        now = datetime.now(UTC)
        latest_alert_at = datetime.fromtimestamp(latest_timestamp, tz=UTC)
        if (now - latest_alert_at).total_seconds() > self.RECENT_ALERT_WINDOW_SECONDS:
            return

        if not self._auto_refresh_lock.acquire(blocking=False):
            return

        try:
            now = datetime.now(UTC)
            if self._last_auto_refresh_at is not None:
                seconds_since_last_refresh = (now - self._last_auto_refresh_at).total_seconds()
                if seconds_since_last_refresh < self.AUTO_REFRESH_COOLDOWN_SECONDS:
                    return

            self._last_auto_refresh_at = now
            self._alert_sync_service.sync_from_history_api(timeout=self.AUTO_REFRESH_TIMEOUT_SECONDS)
        except Exception:
            logger.exception("Automatic alert refresh failed.")
        finally:
            self._auto_refresh_lock.release()

    def get_today_summary(self, reference_time: datetime | None = None) -> dict[str, Any]:
        self._maybe_refresh_recent_alerts()

        if reference_time is None:
            reference_time = utc_to_jerusalem(datetime.now(UTC))
        else:
            reference_time = utc_to_jerusalem(reference_time.astimezone(UTC))

        date_key = reference_time.date().isoformat()
        summary_rows = self._alerts_repository.get_today_breakdown(date_key)
        latest_alert = self._alerts_repository.get_latest_alert()
        sync_meta = self._meta_repository.get_alerts_sync_meta()

        alert_count = sum(int(row["alert_count"]) for row in summary_rows)
        area_hit_count = sum(int(row["area_hit_count"]) for row in summary_rows)
        latest_today_timestamp = max((int(row["latest_timestamp"]) for row in summary_rows), default=0)

        return {
            "date": date_key,
            "timezone": JERUSALEM_TIMEZONE_NAME,
            "alert_count": alert_count,
            "area_hit_count": area_hit_count,
            "kind_breakdown": {
                str(int(row["_id"])): int(row["alert_count"])
                for row in summary_rows
                if row.get("_id") is not None
            },
            "latest_alert_at": timestamp_to_jerusalem_iso(latest_today_timestamp)
            if latest_today_timestamp
            else None,
            "dataset_latest_alert_at": timestamp_to_jerusalem_iso(int(latest_alert["timestamp"]))
            if latest_alert and latest_alert.get("timestamp")
            else None,
            "dataset_loaded_at": self._format_meta_datetime(
                sync_meta.get("last_synced_at") if sync_meta else None
            ),
            "total_records_loaded": self._alerts_repository.count_all(),
        }

    def get_map_summary(self, min_alerts: int = 1, limit: int | None = None) -> dict[str, Any]:
        self._maybe_refresh_recent_alerts()

        mapped_rows = self._alerts_repository.get_city_map_rows(min_alerts)
        available_cities = len(mapped_rows)
        if limit is not None:
            mapped_rows = mapped_rows[:limit]

        mapped_area_hits = self._alerts_repository.count_mapped_area_hits()
        unmapped_rows = self._alerts_repository.get_unmapped_area_rows()
        unmapped_area_hits = sum(int(row["count"]) for row in unmapped_rows)

        latest_alert = self._alerts_repository.get_latest_alert()
        sync_meta = self._meta_repository.get_alerts_sync_meta()

        return {
            "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "dataset_loaded_at": self._format_meta_datetime(
                sync_meta.get("last_synced_at") if sync_meta else None
            ),
            "dataset_latest_alert_at": timestamp_to_jerusalem_iso(int(latest_alert["timestamp"]))
            if latest_alert and latest_alert.get("timestamp")
            else None,
            "total_records_loaded": self._alerts_repository.count_all(),
            "mapped_area_hits": mapped_area_hits,
            "unmapped_area_hits": unmapped_area_hits,
            "unmapped_areas": [
                {"name_he": row["_id"], "count": int(row["count"])}
                for row in unmapped_rows
            ],
            "available_cities": available_cities,
            "returned_cities": len(mapped_rows),
            "min_alerts": min_alerts,
            "cities": [
                {
                    "id": int(row["_id"]),
                    "name": row["name"],
                    "name_he": row["name_he"],
                    "name_en": row["name_en"],
                    "lat": float(row["lat"]),
                    "lng": float(row["lng"]),
                    "total_alerts": int(row["total_alerts"]),
                    "last_alert_at": timestamp_to_jerusalem_iso(int(row["last_alert_timestamp"])),
                }
                for row in mapped_rows
            ],
        }
