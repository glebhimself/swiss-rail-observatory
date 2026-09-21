"""Transactional partition replacement and an ingestion audit trail."""

from __future__ import annotations

import json
import tempfile
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

import duckdb

from .settings import Settings

DDL = """
create schema if not exists raw;
create table if not exists raw.transport (
 event_id varchar, operating_date date, station_id varchar, journey_id varchar,
 operator_id varchar, operator_name varchar, line_name varchar, product varchar,
 scheduled_arrival_local timestamp, scheduled_arrival_utc timestamptz,
 reported_arrival_local timestamp, reported_arrival_utc timestamptz,
 scheduled_departure_local timestamp, arrival_status varchar,
 is_cancelled boolean, is_extra boolean, is_pass_through boolean,
 quality_issue varchar, source_file varchar, source_row bigint
);
create table if not exists raw.weather (
 weather_station_id varchar, interval_end_utc timestamptz,
 temperature_c double, precipitation_mm double, wind_gust_kmh double
);
create table if not exists raw.weather_metadata (
 weather_station_id varchar primary key, station_name varchar,
 latitude double, longitude double, source_url varchar
);
create table if not exists raw.ingestion_log (
 source_key varchar primary key, source_type varchar, source_url varchar,
 source_sha256 varchar, config_sha256 varchar, row_count bigint,
 rejected_count bigint, completed_at timestamptz
);
create table if not exists raw.rejections (
 source_file varchar, source_row bigint, reason varchar, row_json varchar
);
"""


@contextmanager
def connect(settings: Settings):
    settings.prepare()
    conn = duckdb.connect(str(settings.database))
    conn.execute("set TimeZone='UTC'")
    conn.execute(DDL)
    try:
        yield conn
    finally:
        conn.close()


def load_json_rows(conn, table: str, rows: list[dict]):
    if not rows:
        return
    # Bulk JSON loading avoids a Python/SQL round-trip for each event.
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as file:
        path = Path(file.name)
        for row in rows:
            file.write(json.dumps(row) + "\n")
    try:
        conn.execute(f"insert into {table} by name select * from read_json_auto(?)", [str(path)])
    finally:
        path.unlink(missing_ok=True)


def already_loaded(conn, key: str, checksum: str, config_checksum: str) -> bool:
    return (
        conn.execute(
            """select count(*) from raw.ingestion_log
        where source_key=? and source_sha256=? and config_sha256=?""",
            [key, checksum, config_checksum],
        ).fetchone()[0]
        == 1
    )


def record_load(conn, key, kind, url, checksum, config_checksum, rows, rejected=0):
    conn.execute("delete from raw.ingestion_log where source_key=?", [key])
    conn.execute(
        "insert into raw.ingestion_log values (?,?,?,?,?,?,?,?)",
        [
            key,
            kind,
            url,
            checksum,
            config_checksum,
            rows,
            rejected,
            datetime.now(UTC),
        ],
    )
