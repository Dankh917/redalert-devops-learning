from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Iterable

from .time_utils import UTC, format_jerusalem_time, timestamp_to_jerusalem_date, timestamp_to_utc_iso


def make_alert_id(code: int, kind: int, areas: Iterable[str], timestamp: int) -> str:
    payload = json.dumps(
        {
            "code": code,
            "kind": kind,
            "areas": list(areas),
            "timestamp": timestamp,
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def build_alert_document(
    code: int,
    kind: int,
    areas: list[str],
    timestamp: int,
    *,
    source: str,
) -> dict[str, object]:
    utc_dt = datetime.fromtimestamp(timestamp, tz=UTC)
    return {
        "_id": make_alert_id(code, kind, areas, timestamp),
        "code": code,
        "kind": kind,
        "areas": areas,
        "areas_count": len(areas),
        "timestamp": timestamp,
        "utc": timestamp_to_utc_iso(timestamp),
        "jerusalem_time": format_jerusalem_time(utc_dt),
        "jerusalem_date": timestamp_to_jerusalem_date(timestamp),
        "source": source,
        "updated_at": datetime.now(UTC),
    }


def make_polygon_geometry(points: list[list[float]]) -> dict[str, object]:
    coordinates = [[float(lng), float(lat)] for lat, lng in points]
    if coordinates and coordinates[0] != coordinates[-1]:
        coordinates.append(coordinates[0])
    return {
        "type": "Polygon",
        "coordinates": [coordinates],
    }
