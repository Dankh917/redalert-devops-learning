from __future__ import annotations

from typing import Any

from pymongo.collection import Collection

from ..database import MongoSettings


class AlertsRepository:
    def __init__(self, alerts: Collection, settings: MongoSettings) -> None:
        self._alerts = alerts
        self._settings = settings

    def count_all(self) -> int:
        return self._alerts.count_documents({})

    def get_latest_alert(self) -> dict[str, Any] | None:
        return self._alerts.find_one(
            {},
            projection={"timestamp": True, "_id": False},
            sort=[("timestamp", -1)],
        )

    def get_today_breakdown(self, date_key: str) -> list[dict[str, Any]]:
        return list(
            self._alerts.aggregate(
                [
                    {"$match": {"jerusalem_date": date_key}},
                    {
                        "$group": {
                            "_id": "$kind",
                            "alert_count": {"$sum": 1},
                            "area_hit_count": {"$sum": "$areas_count"},
                            "latest_timestamp": {"$max": "$timestamp"},
                        }
                    },
                    {"$sort": {"_id": 1}},
                ]
            )
        )

    def get_city_map_rows(self, min_alerts: int) -> list[dict[str, Any]]:
        return list(
            self._alerts.aggregate(
                [
                    {"$unwind": "$areas"},
                    {
                        "$lookup": {
                            "from": self._settings.cities_collection,
                            "localField": "areas",
                            "foreignField": "value",
                            "as": "city",
                        }
                    },
                    {"$set": {"city": {"$first": "$city"}}},
                    {"$match": {"city": {"$ne": None}}},
                    {
                        "$group": {
                            "_id": "$city._id",
                            "name": {"$first": {"$ifNull": ["$city.names.en", "$city.names.he", "$areas"]}},
                            "name_he": {"$first": {"$ifNull": ["$city.names.he", "$areas"]}},
                            "name_en": {"$first": {"$ifNull": ["$city.names.en", "$city.names.he", "$areas"]}},
                            "lat": {"$first": "$city.lat"},
                            "lng": {"$first": "$city.lng"},
                            "total_alerts": {"$sum": 1},
                            "last_alert_timestamp": {"$max": "$timestamp"},
                        }
                    },
                    {"$match": {"total_alerts": {"$gte": min_alerts}}},
                    {"$sort": {"total_alerts": -1, "name": 1}},
                ]
            )
        )

    def count_mapped_area_hits(self) -> int:
        rows = list(
            self._alerts.aggregate(
                [
                    {"$unwind": "$areas"},
                    {
                        "$lookup": {
                            "from": self._settings.cities_collection,
                            "localField": "areas",
                            "foreignField": "value",
                            "as": "city",
                        }
                    },
                    {"$set": {"city": {"$first": "$city"}}},
                    {"$match": {"city": {"$ne": None}}},
                    {"$count": "mapped_area_hits"},
                ]
            )
        )
        return int(rows[0]["mapped_area_hits"]) if rows else 0

    def get_unmapped_area_rows(self) -> list[dict[str, Any]]:
        return list(
            self._alerts.aggregate(
                [
                    {"$unwind": "$areas"},
                    {
                        "$lookup": {
                            "from": self._settings.cities_collection,
                            "localField": "areas",
                            "foreignField": "value",
                            "as": "city",
                        }
                    },
                    {"$set": {"city": {"$first": "$city"}}},
                    {"$match": {"city": None}},
                    {"$group": {"_id": "$areas", "count": {"$sum": 1}}},
                    {"$sort": {"count": -1, "_id": 1}},
                ]
            )
        )
