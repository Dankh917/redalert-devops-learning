from __future__ import annotations

from datetime import date

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from .services.alert_service import AlertService

app = FastAPI(
    title="Red Alert Backend",
    version="0.1.0",
    description="Small API over the Tzeva Adom historical alert dataset.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

alert_service = AlertService()


@app.get("/")
def root() -> dict[str, str]:
    return {
        "message": "Red Alert backend is running.",
        "docs": "/docs",
    }


@app.get("/api/alerts/today")
def alerts_today() -> dict[str, object]:
    return alert_service.get_today_summary()


@app.get("/api/alerts/summary")
def alerts_summary(
    from_date: date | None = Query(
        None,
        description="Optional inclusive start date in YYYY-MM-DD for range summaries.",
    ),
) -> dict[str, object]:
    if from_date is None:
        return alert_service.get_today_summary()
    return alert_service.get_summary(from_date=from_date.isoformat())


@app.get("/api/alerts/map")
def alerts_map(
    min_alerts: int = Query(1, ge=1, description="Only return cities with at least this many alerts."),
    limit: int | None = Query(
        None,
        ge=1,
        description="Optional hard limit for the number of city markers returned.",
    ),
    from_date: date | None = Query(
        None,
        description="Optional inclusive start date in YYYY-MM-DD for range-filtered map data.",
    ),
) -> dict[str, object]:
    return alert_service.get_map_summary(
        min_alerts=min_alerts,
        limit=limit,
        from_date=from_date.isoformat() if from_date is not None else None,
    )
