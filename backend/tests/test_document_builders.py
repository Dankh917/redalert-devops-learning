from __future__ import annotations

from app.document_builders import build_alert_document, make_alert_id, make_polygon_geometry


def test_build_alert_document_populates_consistent_domain_fields() -> None:
    code = 101
    kind = 1
    areas = ["Jerusalem", "Tel Aviv"]
    timestamp = 1773129703

    document = build_alert_document(
        code=code,
        kind=kind,
        areas=areas,
        timestamp=timestamp,
        source="historical_api",
    )

    assert document["_id"] == make_alert_id(code, kind, areas, timestamp)
    assert document["code"] == code
    assert document["kind"] == kind
    assert document["areas"] == areas
    assert document["areas_count"] == 2
    assert document["timestamp"] == timestamp
    assert document["utc"] == "2026-03-10T08:01:43Z"
    assert document["jerusalem_time"] == "2026-03-10 10:01:43"
    assert document["jerusalem_date"] == "2026-03-10"
    assert document["source"] == "historical_api"
    assert document["updated_at"] is not None


def test_make_polygon_geometry_closes_open_polygon_ring() -> None:
    geometry = make_polygon_geometry(
        [
            [31.1, 34.8],
            [31.2, 34.9],
            [31.3, 34.7],
        ]
    )

    assert geometry["type"] == "Polygon"
    assert geometry["coordinates"] == [
        [
            [34.8, 31.1],
            [34.9, 31.2],
            [34.7, 31.3],
            [34.8, 31.1],
        ]
    ]
