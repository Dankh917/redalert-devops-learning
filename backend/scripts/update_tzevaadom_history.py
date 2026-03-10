from __future__ import annotations

import argparse
import sys

from app.database import create_mongo_client, ensure_indexes, get_database, load_mongo_settings
from app.services.alert_sync_service import (
    DEFAULT_BATCH_SIZE,
    DEFAULT_OVERLAP_SECONDS,
    DEFAULT_SYNC_TIMEOUT,
    HISTORICAL_ALERTS_URL,
    AlertSyncService,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch Tzeva Adom historical alerts and upsert only new records into MongoDB.",
    )
    parser.add_argument(
        "--url",
        default=HISTORICAL_ALERTS_URL,
        help=f"Historical API URL. Default: {HISTORICAL_ALERTS_URL}",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_SYNC_TIMEOUT,
        help=f"HTTP timeout in seconds. Default: {DEFAULT_SYNC_TIMEOUT}",
    )
    parser.add_argument(
        "--overlap-seconds",
        type=int,
        default=DEFAULT_OVERLAP_SECONDS,
        help=(
            "Recheck this many seconds before the latest stored timestamp so "
            "recent backfills are still merged. Default: "
            f"{DEFAULT_OVERLAP_SECONDS}"
        ),
    )
    parser.add_argument("--mongo-uri", default=None, help="MongoDB connection string.")
    parser.add_argument("--database", default=None, help="MongoDB database name.")
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=f"Bulk-write batch size. Default: {DEFAULT_BATCH_SIZE}.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    settings = load_mongo_settings(args.mongo_uri, args.database)
    client = create_mongo_client(settings.uri)
    db = get_database(client, settings)
    ensure_indexes(db, settings)
    sync_service = AlertSyncService(db, settings)
    try:
        result = sync_service.sync_from_history_api(
            url=args.url,
            timeout=args.timeout,
            overlap_seconds=args.overlap_seconds,
            batch_size=args.batch_size,
        )
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc

    print(
        f"Fetched {result.fetched_rows} rows. "
        f"Skipped {result.skipped_old_rows} old rows and {result.skipped_invalid_rows} invalid rows. "
        f"Processed {result.candidate_rows} candidate rows. "
        f"Upserted {result.upserted_count} new records and modified {result.modified_count} existing records in MongoDB."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
