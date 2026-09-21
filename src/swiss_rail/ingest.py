"""Ingest independently replaceable transport days and weather station intervals."""

from __future__ import annotations

import csv
import hashlib
import json
import logging
import re
import tempfile
import zipfile
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import httpx

from .http import client, download, sha256
from .normalize import REQUIRED_TRANSPORT, normalize_transport, normalize_weather, station_id
from .settings import Settings
from .storage import already_loaded, connect, load_json_rows, record_load

LOG = logging.getLogger(__name__)
WEATHER_COLLECTION = "https://data.geo.admin.ch/api/stac/v1/collections/ch.meteoschweiz.ogd-smn"
CATALOGS = [
    "https://data.opentransportdata.swiss/api/3/action/package_show?id=ist-daten-v2",
    "https://opendata.swiss/api/3/action/package_show?id=ist-daten-v2",
]


def days(start: date, end: date):
    if end < start:
        raise ValueError("End date precedes start date")
    for n in range((end - start).days + 1):
        yield start + timedelta(days=n)


def config_hash(settings: Settings) -> str:
    return hashlib.sha256(
        (settings.root / "dbt/seeds/stations.csv").read_bytes() + b"parser-v1"
    ).hexdigest()


def ingest_transport_file(
    settings: Settings, path: Path, day: date, source_url: str | None = None
) -> dict:
    """Replace one day and its ledger entry in the same transaction."""
    key = f"transport:{day.isoformat()}"
    checksum, scope_hash = sha256(path), config_hash(settings)
    selected = {s["station_id"] for s in settings.stations}
    with connect(settings) as conn:
        if already_loaded(conn, key, checksum, scope_hash):
            return {"date": str(day), "status": "unchanged"}
        with path.open(encoding="utf-8-sig", newline="") as file:
            first_line = file.readline()
            delimiter = ";" if first_line.count(";") > first_line.count(",") else ","
            file.seek(0)
            reader = csv.DictReader(file, delimiter=delimiter)
            missing = REQUIRED_TRANSPORT - set(reader.fieldnames or [])
            if missing:
                raise ValueError(f"Transport schema changed or file is not CSV; missing {missing}")
            rows, rejections = [], []
            for number, row in enumerate(reader, start=2):
                if station_id(row.get("BPUIC", "")) not in selected:
                    continue
                if (row.get("PRODUKT_ID") or "").lower() not in {"zug", "train", "treno"}:
                    continue
                try:
                    event = normalize_transport(row, path.name, number)
                    if event["operating_date"] == day.isoformat():
                        rows.append(event)
                except (ValueError, KeyError, TypeError) as error:
                    rejections.append(
                        {
                            "source_file": path.name,
                            "source_row": number,
                            "reason": str(error),
                            "row_json": json.dumps(row),
                        }
                    )
        if not rows:
            raise ValueError(f"No selected rail events for {day}; prior partition retained.")
        if len(rejections) / (len(rows) + len(rejections)) > 0.01:
            raise ValueError("More than 1% of selected rows failed parsing; partition retained.")
        conn.execute("begin")
        try:
            conn.execute("delete from raw.transport where operating_date=?", [day])
            conn.execute("delete from raw.rejections where source_file=?", [path.name])
            load_json_rows(conn, "raw.transport", rows)
            load_json_rows(conn, "raw.rejections", rejections)
            record_load(
                conn,
                key,
                "transport",
                source_url or path.name,
                checksum,
                scope_hash,
                len(rows),
                len(rejections),
            )
            conn.execute("commit")
        except Exception:
            conn.execute("rollback")
            raise
    return {"date": str(day), "status": "loaded", "rows": len(rows), "rejected": len(rejections)}


def ingest_local(settings: Settings, path: Path, start: date, end: date) -> list[dict]:
    """Import downloaded daily CSVs or monthly ZIPs without extracting archive paths."""
    results = []
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            for member in sorted(archive.infolist(), key=lambda x: x.filename):
                match = re.search(r"(\d{4}-\d{2}-\d{2}).*\.csv$", member.filename, flags=re.I)
                if not match or not start <= date.fromisoformat(match[1]) <= end:
                    continue
                if member.file_size > 2_000_000_000:
                    raise ValueError(f"Archive member too large: {member.filename}")
                with tempfile.TemporaryDirectory(dir=settings.data) as folder:
                    target = Path(folder) / Path(member.filename).name
                    with archive.open(member) as source, target.open("wb") as dest:
                        while chunk := source.read(1024 * 1024):
                            dest.write(chunk)
                    results.append(
                        ingest_transport_file(
                            settings, target, date.fromisoformat(match[1]), path.name
                        )
                    )
    else:
        match = re.search(r"(\d{4}-\d{2}-\d{2})", path.name)
        if not match:
            raise ValueError("Name daily CSVs YYYY-MM-DD_istdaten.csv")
        day = date.fromisoformat(match[1])
        if start <= day <= end:
            results.append(ingest_transport_file(settings, path, day))
    if not results:
        raise ValueError(f"No dated CSVs in the requested interval: {path.name}")
    return results


def transport_catalog(http: httpx.Client) -> dict[date, str]:
    failures = []
    for catalog in CATALOGS:
        try:
            response = http.get(catalog)
            response.raise_for_status()
            payload = response.json()
            if not payload.get("success"):
                raise ValueError("Catalog returned an unsuccessful response")
            result = {}
            for resource in payload["result"]["resources"]:
                match = re.search(
                    r"(\d{4}-\d{2}-\d{2})[^/]*\.csv", resource.get("url", ""), flags=re.I
                )
                if match:
                    result[date.fromisoformat(match[1])] = resource["url"]
            if not result:
                raise ValueError("No daily CSV resources in catalog")
            return result
        except (httpx.HTTPError, ValueError, KeyError) as error:
            failures.append(f"{catalog}: {error}")
    raise RuntimeError(
        "Transport catalog unavailable. Import official CSV/ZIP files with "
        "--transport-file. " + "; ".join(failures)
    )


def sync_transport(settings: Settings, start: date, end: date, refresh: bool = False) -> dict:
    settings.prepare()
    report = {
        "requested_start": str(start),
        "requested_end": str(end),
        "completed": [],
        "missing": [],
        "errors": [],
    }
    with client() as http:
        try:
            catalog = transport_catalog(http)
        except RuntimeError as error:
            catalog = {}
            report["errors"].append(str(error))
        for day in days(start, end):
            key = f"transport:{day}"
            with connect(settings) as conn:
                loaded = conn.execute(
                    "select count(*) from raw.ingestion_log where source_key=? and config_sha256=?",
                    [key, config_hash(settings)],
                ).fetchone()[0]
            if loaded and not refresh:
                report["completed"].append({"date": str(day), "status": "already_loaded"})
                continue
            if day not in catalog:
                report["missing"].append(str(day))
                continue
            try:
                url = catalog[day]
                path = download(
                    url,
                    settings.data / "downloads" / f"{day}_istdaten.csv",
                    refresh=refresh,
                    http=http,
                )
                outcome = ingest_transport_file(settings, path, day, url)
                report["completed"].append(outcome)
                LOG.info("Transport %s: %s", day, outcome["status"])
            except (httpx.HTTPError, ValueError) as error:
                report["missing"].append(str(day))
                report["errors"].append(f"{day}: {error}")
                # Do not repeatedly request a host which has denied access.
                if isinstance(error, httpx.HTTPStatusError) and error.response.status_code in {
                    401,
                    403,
                }:
                    report["missing"].extend(str(d) for d in days(day + timedelta(days=1), end))
                    break
    (settings.data / "transport_sync.json").write_text(json.dumps(report, indent=2))
    return report


def ingest_weather_csv(
    settings: Settings, path: Path, station: str, start: date, end: date, url: str = ""
) -> dict:
    rows = []
    with path.open(encoding="cp1252", newline="") as file:
        reader = csv.DictReader(file, delimiter=";")
        required = {"station_abbr", "reference_timestamp", "tre200h0", "rre150h0", "fu3010h1"}
        if required - set(reader.fieldnames or []):
            raise ValueError(
                f"Weather schema changed: missing {required - set(reader.fieldnames or [])}"
            )
        for row in reader:
            result = normalize_weather(row, start, end)
            if result:
                if result["weather_station_id"] != station:
                    raise ValueError(f"Unexpected weather station in {path.name}")
                rows.append(result)
    if not rows:
        return {"station": station, "rows": 0, "status": "outside_requested_interval"}
    checksum = sha256(path)
    key = f"weather:{station}:{path.name}:{start}:{end}"
    with connect(settings) as conn:
        if already_loaded(conn, key, checksum, "weather-v2"):
            return {"station": station, "rows": len(rows), "status": "unchanged"}
        conn.execute("begin")
        try:
            # The caller declares this asset's coverage, so deleted boundary rows
            # are removed too. Historical/recent asset windows never overlap.
            minimum = datetime.combine(start, datetime.min.time(), tzinfo=UTC)
            maximum = datetime.combine(end + timedelta(days=1), datetime.min.time(), tzinfo=UTC)
            conn.execute(
                "delete from raw.weather where weather_station_id=? "
                "and interval_end_utc >= ?::timestamptz and interval_end_utc < ?::timestamptz",
                [station, minimum, maximum],
            )
            load_json_rows(conn, "raw.weather", rows)
            record_load(conn, key, "weather", url or path.name, checksum, "weather-v2", len(rows))
            conn.execute("commit")
        except Exception:
            conn.execute("rollback")
            raise
    return {"station": station, "rows": len(rows), "status": "loaded"}


def weather_asset_window(name: str, start: date, end: date, today: date):
    """Intersect the study boundary days with an asset's declared publication period."""
    requested_start, requested_end = start - timedelta(days=1), end + timedelta(days=1)
    if "_recent" in name:
        low, high = date(today.year, 1, 1), today - timedelta(days=1)
    else:
        years = re.search(r"(\d{4})-(\d{4})", name)
        if not years:
            return None
        low = date(int(years[1]), 1, 1)
        high = min(date(int(years[2]), 12, 31), date(today.year, 1, 1) - timedelta(days=1))
    low, high = max(low, requested_start), min(high, requested_end)
    return (low, high) if low <= high else None


def sync_weather(settings: Settings, start: date, end: date) -> list[dict]:
    results = []
    with client() as http:
        for station in settings.config["weather_stations"]:
            url = f"{WEATHER_COLLECTION}/items/{station.lower()}"
            response = http.get(url)
            response.raise_for_status()
            item = response.json()
            lon, lat = item["geometry"]["coordinates"][:2]
            with connect(settings) as conn:
                conn.execute(
                    "insert or replace into raw.weather_metadata values (?,?,?,?,?)",
                    [station, item["properties"]["title"], lat, lon, url],
                )
            for name, asset in sorted(item["assets"].items()):
                if "_h_" not in name or not name.endswith(".csv") or "_now" in name:
                    continue
                window = weather_asset_window(name, start, end, datetime.now(UTC).date())
                if window is None:
                    continue
                path = download(
                    asset["href"],
                    settings.data / "downloads" / name,
                    refresh="_recent" in name,
                    http=http,
                )
                result = ingest_weather_csv(
                    settings,
                    path,
                    station,
                    window[0],
                    window[1],
                    asset["href"],
                )
                results.append(result)
            LOG.info("Weather %s complete", station)
    return results
