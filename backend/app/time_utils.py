from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

UTC = timezone.utc
JERUSALEM_TIMEZONE_NAME = "Asia/Jerusalem"

try:
    JERUSALEM_TZ = ZoneInfo(JERUSALEM_TIMEZONE_NAME)
except ZoneInfoNotFoundError:
    JERUSALEM_TZ = None


def utc_to_jerusalem(utc_dt: datetime) -> datetime:
    if JERUSALEM_TZ is not None:
        return utc_dt.astimezone(JERUSALEM_TZ)

    offset_hours = 3 if is_israel_dst(utc_dt) else 2
    return utc_dt.astimezone(timezone(timedelta(hours=offset_hours)))


def format_jerusalem_time(utc_dt: datetime) -> str:
    return utc_to_jerusalem(utc_dt).strftime("%Y-%m-%d %H:%M:%S")


def timestamp_to_utc_iso(timestamp: int) -> str:
    return datetime.fromtimestamp(timestamp, tz=UTC).isoformat().replace("+00:00", "Z")


def timestamp_to_jerusalem_iso(timestamp: int) -> str:
    return utc_to_jerusalem(datetime.fromtimestamp(timestamp, tz=UTC)).isoformat()


def timestamp_to_jerusalem_date(timestamp: int) -> str:
    return utc_to_jerusalem(datetime.fromtimestamp(timestamp, tz=UTC)).date().isoformat()


def last_weekday_of_month(year: int, month: int, weekday: int) -> int:
    if month == 12:
        next_month = datetime(year + 1, 1, 1)
    else:
        next_month = datetime(year, month + 1, 1)

    current = next_month - timedelta(days=1)
    while current.weekday() != weekday:
        current -= timedelta(days=1)
    return current.day


def is_israel_dst(utc_dt: datetime) -> bool:
    year = utc_dt.year
    last_sunday_march = last_weekday_of_month(year, 3, 6)
    dst_start_day = last_sunday_march - 2
    dst_start_utc = datetime(year, 3, dst_start_day, 0, 0, tzinfo=UTC)

    last_sunday_october = last_weekday_of_month(year, 10, 6)
    dst_end_utc = datetime(year, 10, last_sunday_october - 1, 23, 0, tzinfo=UTC)

    return dst_start_utc <= utc_dt < dst_end_utc
