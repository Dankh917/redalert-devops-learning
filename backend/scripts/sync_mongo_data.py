from __future__ import annotations

import argparse
import json
from datetime import datetime
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from pymongo import ReplaceOne, UpdateOne

from app.database import create_mongo_client, ensure_indexes, get_database, load_mongo_settings
from app.document_builders import build_alert_document, make_polygon_geometry
from app.time_utils import UTC

LISTS_VERSIONS_URL = "https://api.tzevaadom.co.il/lists-versions"
CITIES_URL_TEMPLATE = "https://www.tzevaadom.co.il/static/cities.json?v={version}"
POLYGONS_URL_TEMPLATE = "https://www.tzevaadom.co.il/static/polygons.json?v={version}"
ALERTS_URL = "https://www.tzevaadom.co.il/static/historical/all.json"
DEFAULT_TIMEOUT = 60


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create MongoDB collections and import Red Alert alerts, cities, and polygons from the official APIs.",
    )
    parser.add_argument("--mongo-uri", default=None, help="MongoDB connection string.")
    parser.add_argument("--database", default=None, help="MongoDB database name.")
    parser.add_argument("--alerts-url", default=ALERTS_URL, help=f"Alerts API URL. Default: {ALERTS_URL}")
    parser.add_argument(
        "--lists-versions-url",
        default=LISTS_VERSIONS_URL,
        help=f"Lists versions API URL. Default: {LISTS_VERSIONS_URL}",
    )
    parser.add_argument("--cities-url", default=None, help="Optional override for the cities dataset URL.")
    parser.add_argument("--polygons-url", default=None, help="Optional override for the polygons dataset URL.")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help=f"HTTP timeout in seconds. Default: {DEFAULT_TIMEOUT}")
    parser.add_argument("--drop-existing", action="store_true", help="Drop the target collections before importing.")
    parser.add_argument("--batch-size", type=int, default=1000, help="Bulk-write batch size. Default: 1000.")
    return parser.parse_args()


def fetch_json(url: str, timeout: int) -> Any:
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; RedAlertMongoSync/1.0)",
            "Accept": "application/json",
        },
    )

    try:
        with urlopen(request, timeout=timeout) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            payload = response.read().decode(charset)
    except HTTPError as exc:
        raise SystemExit(f"HTTP error while fetching {url}: {exc.code} {exc.reason}") from exc
    except URLError as exc:
        raise SystemExit(f"Network error while fetching {url}: {exc.reason}") from exc

    try:
        return json.loads(payload)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"API returned invalid JSON from {url}: {exc}") from exc


def resolve_static_urls(args: argparse.Namespace) -> tuple[str, str]:
    if args.cities_url and args.polygons_url:
        return args.cities_url, args.polygons_url

    versions = fetch_json(args.lists_versions_url, args.timeout)
    if not isinstance(versions, dict):
        raise SystemExit("Expected lists-versions API to return a JSON object.")

    cities_version = versions.get("cities", 10)
    polygons_version = versions.get("polygons", 5)
    return (
        args.cities_url or CITIES_URL_TEMPLATE.format(version=cities_version),
        args.polygons_url or POLYGONS_URL_TEMPLATE.format(version=polygons_version),
    )


def write_in_batches(collection: Any, operations: list[Any], batch_size: int) -> None:
    for offset in range(0, len(operations), batch_size):
        chunk = operations[offset : offset + batch_size]
        if chunk:
            collection.bulk_write(chunk, ordered=False)


def sync_cities(db: Any, cities_payload: Any, source_url: str, batch_size: int) -> int:
    if not isinstance(cities_payload, dict):
        raise SystemExit("Expected cities payload to contain a top-level JSON object.")

    cities = cities_payload.get("cities")
    if not isinstance(cities, dict):
        raise SystemExit("Expected cities payload to contain a top-level 'cities' object.")

    operations: list[Any] = []
    for value, city in cities.items():
        if not isinstance(city, dict):
            continue
        doc = {
            "_id": int(city["id"]),
            "value": value,
            "names": {
                "he": city.get("he"),
                "en": city.get("en"),
                "ru": city.get("ru"),
                "ar": city.get("ar"),
                "es": city.get("es"),
            },
            "area_id": int(city["area"]),
            "countdown": int(city["countdown"]),
            "lat": float(city["lat"]),
            "lng": float(city["lng"]),
            "location": {
                "type": "Point",
                "coordinates": [float(city["lng"]), float(city["lat"])],
            },
            "source_key": value,
            "updated_at": datetime.now(UTC),
        }
        operations.append(ReplaceOne({"_id": doc["_id"]}, doc, upsert=True))

    collection = db["cities"]
    write_in_batches(collection, operations, batch_size)
    db["dataset_meta"].update_one(
        {"_id": "cities_source"},
        {
            "$set": {
                "version": cities_payload.get("@VERSION"),
                "build_date": cities_payload.get("@BUILD_DATE"),
                "areas": cities_payload.get("areas"),
                "countdown": cities_payload.get("countdown"),
                "source_url": source_url,
                "document_count": collection.count_documents({}),
                "updated_at": datetime.now(UTC),
            }
        },
        upsert=True,
    )
    return collection.count_documents({})


def sync_polygons(db: Any, polygons_payload: Any, source_url: str, batch_size: int) -> int:
    if not isinstance(polygons_payload, dict):
        raise SystemExit("Expected polygons payload to contain a top-level JSON object.")

    operations: list[Any] = []
    for city_id_raw, raw_points in polygons_payload.items():
        if not isinstance(raw_points, list):
            continue
        points: list[list[float]] = []
        for point in raw_points:
            if (
                isinstance(point, list)
                and len(point) == 2
                and isinstance(point[0], (int, float))
                and isinstance(point[1], (int, float))
            ):
                points.append([float(point[0]), float(point[1])])

        city_id = int(city_id_raw)
        doc = {
            "_id": city_id,
            "city_id": city_id,
            "point_count": len(points),
            "points": points,
            "geometry": make_polygon_geometry(points),
            "updated_at": datetime.now(UTC),
        }
        operations.append(ReplaceOne({"_id": city_id}, doc, upsert=True))

    collection = db["polygons"]
    write_in_batches(collection, operations, batch_size)
    db["dataset_meta"].update_one(
        {"_id": "polygons_source"},
        {
            "$set": {
                "source_url": source_url,
                "document_count": collection.count_documents({}),
                "updated_at": datetime.now(UTC),
            }
        },
        upsert=True,
    )
    return collection.count_documents({})


def sync_alerts(db: Any, alerts_payload: Any, source_url: str, batch_size: int) -> int:
    if not isinstance(alerts_payload, list):
        raise SystemExit("Expected alerts payload to contain a top-level JSON array.")

    operations: list[Any] = []
    latest_timestamp = 0

    for row in alerts_payload:
        if not isinstance(row, list) or len(row) != 4:
            continue

        code, kind, areas, timestamp = row
        if not isinstance(code, int) or not isinstance(kind, int) or not isinstance(timestamp, int):
            continue
        if not isinstance(areas, list) or not all(isinstance(area, str) for area in areas):
            continue

        latest_timestamp = max(latest_timestamp, timestamp)
        doc = build_alert_document(code, kind, areas, timestamp, source="bootstrap_remote")
        operations.append(UpdateOne({"_id": doc["_id"]}, {"$set": doc}, upsert=True))

    collection = db["alerts"]
    write_in_batches(collection, operations, batch_size)
    db["dataset_meta"].update_one(
        {"_id": "alerts_sync"},
        {
            "$set": {
                "source": "bootstrap_remote",
                "source_url": source_url,
                "last_synced_at": datetime.now(UTC),
                "latest_timestamp": latest_timestamp,
                "document_count": collection.count_documents({}),
            }
        },
        upsert=True,
    )
    return collection.count_documents({})


def main() -> int:
    args = parse_args()
    settings = load_mongo_settings(args.mongo_uri, args.database)
    client = create_mongo_client(settings.uri)
    db = get_database(client, settings)

    if args.drop_existing:
        for collection_name in (
            settings.alerts_collection,
            settings.cities_collection,
            settings.polygons_collection,
            settings.meta_collection,
        ):
            db[collection_name].drop()

    ensure_indexes(db, settings)

    cities_url, polygons_url = resolve_static_urls(args)
    alerts_payload = fetch_json(args.alerts_url, args.timeout)
    cities_payload = fetch_json(cities_url, args.timeout)
    polygons_payload = fetch_json(polygons_url, args.timeout)

    cities_count = sync_cities(db, cities_payload, cities_url, args.batch_size)
    polygons_count = sync_polygons(db, polygons_payload, polygons_url, args.batch_size)
    alerts_count = sync_alerts(db, alerts_payload, args.alerts_url, args.batch_size)

    print(
        f"Imported into {settings.database}. "
        f"Cities: {cities_count}. "
        f"Polygons: {polygons_count}. "
        f"Alerts: {alerts_count}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
