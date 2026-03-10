from __future__ import annotations

import os
from dataclasses import dataclass

from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.database import Database


@dataclass(frozen=True)
class MongoSettings:
    uri: str
    database: str
    alerts_collection: str = "alerts"
    cities_collection: str = "cities"
    polygons_collection: str = "polygons"
    meta_collection: str = "dataset_meta"


def load_mongo_settings(uri: str | None = None, database: str | None = None) -> MongoSettings:
    return MongoSettings(
        uri=uri or os.getenv("MONGO_URI", "mongodb://127.0.0.1:27017"),
        database=database or os.getenv("MONGO_DB", "red_alert"),
    )


def create_mongo_client(uri: str) -> MongoClient:
    client = MongoClient(uri, serverSelectionTimeoutMS=5000, tz_aware=True)
    client.admin.command("ping")
    return client


def get_database(client: MongoClient, settings: MongoSettings) -> Database:
    return client[settings.database]


def ensure_indexes(db: Database, settings: MongoSettings) -> None:
    alerts = db[settings.alerts_collection]
    cities = db[settings.cities_collection]
    polygons = db[settings.polygons_collection]

    alerts.create_index([("timestamp", DESCENDING)])
    alerts.create_index([("jerusalem_date", ASCENDING)])
    alerts.create_index([("areas", ASCENDING)])

    cities.create_index([("value", ASCENDING)], unique=True)
    cities.create_index([("area_id", ASCENDING)])
    cities.create_index([("location", "2dsphere")])

    polygons.create_index([("city_id", ASCENDING)], unique=True)
