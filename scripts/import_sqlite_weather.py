#!/usr/bin/env python3
"""Import historical weather records from the old Local Services SQLite database.

The SQLite source is opened read-only. Records are matched by (created_at, location)
so the import can be safely re-run without duplicating existing weather observations.
"""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

import psycopg


COLUMNS = (
    "created_at",
    "location",
    "geolocation",
    "description",
    "temperature",
    "pressure",
    "feelslike",
    "humidity",
    "visibility",
    "windspeed",
    "winddirection",
    "clouds",
    "sunrise",
    "sunset",
)


def import_weather(sqlite_path: Path, database_url: str, dry_run: bool = False) -> tuple[int, int]:
    if not sqlite_path.exists():
        raise FileNotFoundError(f"SQLite database not found: {sqlite_path}")

    sqlite_uri = f"file:{sqlite_path.resolve()}?mode=ro"
    source = sqlite3.connect(sqlite_uri, uri=True)
    source.row_factory = sqlite3.Row

    try:
        rows = source.execute(
            """
            SELECT created_at, location, geolocation, description,
                   temperature, pressure, feelslike, humidity, visibility,
                   windspeed, winddirection, clouds, sunrise, sunset
            FROM chart
            ORDER BY id
            """
        ).fetchall()
    finally:
        source.close()

    if dry_run:
        print(f"Source: {sqlite_path}")
        print(f"Rows found: {len(rows)}")
        return 0, len(rows)

    imported = 0
    skipped = 0

    with psycopg.connect(database_url) as db:
        with db.cursor() as cur:
            for row in rows:
                values = tuple(row[column] for column in COLUMNS)
                cur.execute(
                    """
                    INSERT INTO chart (
                        created_at, location, geolocation, description,
                        temperature, pressure, feelslike, humidity, visibility,
                        windspeed, winddirection, clouds, sunrise, sunset
                    )
                    SELECT %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    WHERE NOT EXISTS (
                        SELECT 1
                        FROM chart
                        WHERE created_at = %s AND location = %s
                    )
                    """,
                    values + (row["created_at"], row["location"]),
                )
                if cur.rowcount:
                    imported += 1
                else:
                    skipped += 1

        db.commit()

    return imported, skipped


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "sqlite_path",
        nargs="?",
        default="/import/flaskr.sqlite",
        help="Path to the old SQLite database (default: /import/flaskr.sqlite)",
    )
    parser.add_argument(
        "--database-url",
        default=None,
        help="PostgreSQL connection URL; defaults to DATABASE_URL",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Read and count source rows without changing PostgreSQL",
    )
    args = parser.parse_args()

    import os

    database_url = args.database_url or os.environ.get("DATABASE_URL")
    if not database_url and not args.dry_run:
        parser.error("DATABASE_URL is required unless --dry-run is used")

    imported, skipped = import_weather(
        Path(args.sqlite_path),
        database_url or "",
        dry_run=args.dry_run,
    )

    if args.dry_run:
        return

    print(f"Imported: {imported}")
    print(f"Skipped existing: {skipped}")
    print(f"Total processed: {imported + skipped}")


if __name__ == "__main__":
    main()
