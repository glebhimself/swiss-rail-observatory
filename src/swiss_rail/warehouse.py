"""Run dbt and export the validated star schema for Power BI."""

from __future__ import annotations

import csv
import json
import os
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from .settings import Settings
from .storage import connect

TABLES = [
    "dim_date",
    "dim_station",
    "dim_operator",
    "dim_service",
    "dim_hour",
    "fct_stop_event",
    "mart_station_daily",
    "mart_weather_comparison",
    "mart_data_quality",
]


def dbt(settings: Settings, command: str, extra: list[str] | None = None):
    env = os.environ.copy()
    env.update(
        {
            "RAIL_DB": str(settings.database),
            "DBT_SEND_ANONYMOUS_USAGE_STATS": "false",
            "DBT_TARGET_PATH": str(settings.data / "dbt-target"),
            "DBT_LOG_PATH": str(settings.data / "dbt-logs"),
        }
    )
    executable = Path(sys.executable).parent / ("dbt.exe" if os.name == "nt" else "dbt")
    args = [
        str(executable),
        *([command] + (extra or []) if command == "docs" else [command]),
        "--project-dir",
        str(settings.root / "dbt"),
        "--profiles-dir",
        str(settings.root / "dbt"),
        "--vars",
        json.dumps(
            {
                "arrival_threshold_seconds": settings.config["arrival_threshold_seconds"],
                "minimum_group_arrivals": settings.config["minimum_group_arrivals"],
            }
        ),
    ]
    subprocess.run(
        args + ([] if command == "docs" else (extra or [])), env=env, cwd=settings.root, check=True
    )


def build(settings: Settings):
    with connect(settings) as conn:
        if not conn.execute("select count(*) from raw.transport").fetchone()[0]:
            raise ValueError(
                "No transport events loaded. Ingest data before building the warehouse."
            )
    dbt(settings, "build")
    shutil.copyfile(
        settings.data / "dbt-target/run_results.json",
        settings.data / "dbt-target/build_run_results.json",
    )
    # Build creates models/tests; compile includes standalone analytical SQL files.
    dbt(settings, "compile", ["--select", "path:analyses"])


def query_rows(conn, sql: str) -> list[dict]:
    result = conn.execute(sql)
    names = [d[0] for d in result.description]
    return [dict(zip(names, row, strict=True)) for row in result.fetchall()]


def export(settings: Settings) -> dict:
    settings.prepare()
    schema = {}
    with connect(settings) as conn:
        for table in TABLES:
            schema[table] = query_rows(conn, f"describe analytics.{table}")
            # Binding paths avoids SQL quoting errors with spaces or apostrophes.
            conn.execute(
                f"copy (select * from analytics.{table}) to ? (format csv, header true)",
                [str(settings.exports / f"{table}.csv")],
            )
        analyses = {}
        compiled = settings.data / "dbt-target/compiled/swiss_rail/analyses"
        for path in sorted(compiled.glob("*.sql")):
            rows = query_rows(conn, path.read_text())
            analyses[path.stem] = rows
            result = conn.execute(path.read_text())
            with (settings.exports / f"analysis_{path.stem}.csv").open("w", newline="") as file:
                writer = csv.writer(file)
                writer.writerow([column[0] for column in result.description])
                writer.writerows(result.fetchall())
        summary = query_rows(
            conn,
            """
            select count(*) as event_count, count(distinct station_id) as station_count,
                min(operating_date) as first_date, max(operating_date) as last_date,
                count(distinct operating_date) as operating_days,
                count(*) filter (where is_eligible_arrival) as eligible_arrivals,
                count(*) filter (where is_on_time) as on_time_arrivals,
                count(*) filter (where is_measured_arrival) as measured_arrivals,
                round(100.0 * count(*) filter (where is_on_time) /
                    nullif(count(*) filter (where is_eligible_arrival), 0), 2) as on_time_pct,
                round(100.0 * count(*) filter (
                    where is_eligible_arrival and precipitation_mm is not null) /
                    nullif(count(*) filter (where is_eligible_arrival), 0), 2) as weather_match_pct,
                count(*) filter (where is_scheduled_stop and is_cancelled) as cancelled_stops
            from analytics.fct_stop_event
        """,
        )[0]
        summary["raw_rows"] = conn.execute("select count(*) from raw.transport").fetchone()[0]
        summary["duplicates_removed"] = summary["raw_rows"] - summary["event_count"]
        summary["rejected_rows"] = conn.execute("select count(*) from raw.rejections").fetchone()[0]
        summary["mode"] = settings.mode
        summary["synthetic"] = settings.mode == "demo"
        summary["generated_at"] = datetime.now(UTC).isoformat()
        summary["arrival_threshold_seconds"] = settings.config["arrival_threshold_seconds"]
        summary["source_attribution"] = (
            "Synthetic test data; not Swiss transport findings."
            if settings.mode == "demo"
            else "opentransportdata.swiss; Source: MeteoSwiss"
        )
        summary["analyses"] = analyses
        summary["ingestion"] = query_rows(
            conn, "select * from raw.ingestion_log order by source_key"
        )
        # A compact run summary is safe to include in the guide; full ledger stays in exports.
        ledger = summary.pop("ingestion")
        (settings.exports / "ingestion_manifest.json").write_text(
            json.dumps(ledger, indent=2, default=str)
        )
    (settings.exports / "schema.json").write_text(json.dumps(schema, indent=2, default=str))
    (settings.exports / "summary.json").write_text(json.dumps(summary, indent=2, default=str))
    dictionary = ["# Exported schema", "", f"Data mode: {settings.mode}.", ""]
    for table, columns in schema.items():
        dictionary += [f"## {table}", "", "| Column | DuckDB type |", "|---|---|"]
        dictionary += [f"| `{c['column_name']}` | `{c['column_type']}` |" for c in columns]
        dictionary.append("")
    (settings.exports / "data_dictionary.md").write_text("\n".join(dictionary))
    return summary


def status(settings: Settings) -> dict:
    with connect(settings) as conn:
        return {
            "mode": settings.mode,
            "database": str(settings.database),
            "transport_rows": conn.execute("select count(*) from raw.transport").fetchone()[0],
            "operating_days": conn.execute(
                "select count(distinct operating_date) from raw.transport"
            ).fetchone()[0],
            "weather_rows": conn.execute("select count(*) from raw.weather").fetchone()[0],
            "successful_source_loads": conn.execute(
                "select count(*) from raw.ingestion_log"
            ).fetchone()[0],
        }
