"""Validate source structure and preserve uncertainty before loading SQL tables."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

ZURICH = ZoneInfo("Europe/Zurich")
STATUSES = {"REAL", "PROGNOSE", "GESCHAETZT", "UNBEKANNT"}
REQUIRED_TRANSPORT = {
    "BETRIEBSTAG",
    "FAHRT_BEZEICHNER",
    "BETREIBER_ID",
    "PRODUKT_ID",
    "BPUIC",
    "ANKUNFTSZEIT",
    "AN_PROGNOSE",
    "AN_PROGNOSE_STATUS",
    "ABFAHRTSZEIT",
    "FAELLT_AUS_TF",
    "ZUSATZFAHRT_TF",
    "DURCHFAHRT_TF",
}


def station_id(value: str) -> str:
    """Normalize BPUIC platform codes and Swiss SLOIDs to a station BPUIC."""
    value = (value or "").strip()
    if re.fullmatch(r"\d{7}(\d{2})?", value):
        return value[:7]
    match = re.fullmatch(r"ch:1:sloid:(\d{1,5})(?::.*)?", value, flags=re.I)
    if match:
        return "85" + match.group(1).zfill(5)
    return value  # Unknown schemes never get guessed into the selected Swiss stations.


def boolean(value: str) -> bool:
    value = (value or "").strip().lower()
    if value in {"", "false", "0"}:
        return False
    if value in {"true", "1"}:
        return True
    raise ValueError(f"Unexpected boolean: {value!r}")


def local_timestamp(value: str) -> tuple[str | None, str | None, str | None]:
    """Return local, UTC, and a quality issue. Never guess a DST fold."""
    if not value or not value.strip():
        return None, None, None
    dt = None
    for fmt in ("%d.%m.%Y %H:%M:%S", "%d.%m.%Y %H:%M"):
        try:
            dt = datetime.strptime(value.strip(), fmt)
            break
        except ValueError:
            pass
    if dt is None:
        return None, None, "invalid_timestamp"
    candidates = set()
    for fold in (0, 1):
        utc = dt.replace(tzinfo=ZURICH, fold=fold).astimezone(UTC)
        if utc.astimezone(ZURICH).replace(tzinfo=None) == dt:
            candidates.add(utc)
    if len(candidates) != 1:
        issue = "ambiguous_local_time" if candidates else "nonexistent_local_time"
        return dt.isoformat(), None, issue
    return dt.isoformat(), candidates.pop().isoformat(), None


def normalize_transport(row: dict, source: str, row_number: int) -> dict:
    day = datetime.strptime(row["BETRIEBSTAG"].strip(), "%d.%m.%Y").date()
    station = station_id(row["BPUIC"])
    journey = row["FAHRT_BEZEICHNER"].strip()
    operator = row["BETREIBER_ID"].strip()
    if not journey or not operator or not station:
        raise ValueError("Missing journey, operator, or station identifier")
    scheduled, scheduled_utc, issue1 = local_timestamp(row["ANKUNFTSZEIT"])
    reported, reported_utc, issue2 = local_timestamp(row["AN_PROGNOSE"])
    departure, _, issue3 = local_timestamp(row["ABFAHRTSZEIT"])
    status = (row["AN_PROGNOSE_STATUS"] or "PROGNOSE").strip().upper() or "PROGNOSE"
    issues = sorted(set(filter(None, [issue1, issue2, issue3])))
    if status not in STATUSES:
        issues.append("unknown_status")
    # Scheduled arrival/departure distinguish repeat visits on the same journey.
    key = [
        day.isoformat(),
        journey,
        operator,
        station,
        row["ANKUNFTSZEIT"].strip(),
        row["ABFAHRTSZEIT"].strip(),
    ]
    return {
        "event_id": hashlib.sha256(json.dumps(key).encode()).hexdigest()[:32],
        "operating_date": day.isoformat(),
        "station_id": station,
        "journey_id": journey,
        "operator_id": operator,
        "operator_name": row.get("BETREIBER_NAME", "") or operator,
        "line_name": row.get("LINIEN_TEXT", "") or row.get("VERKEHRSMITTEL_TEXT", "") or "Unknown",
        "product": row["PRODUKT_ID"],
        "scheduled_arrival_local": scheduled,
        "scheduled_arrival_utc": scheduled_utc,
        "reported_arrival_local": reported,
        "reported_arrival_utc": reported_utc,
        "scheduled_departure_local": departure,
        "arrival_status": status,
        "is_cancelled": boolean(row["FAELLT_AUS_TF"]),
        "is_extra": boolean(row["ZUSATZFAHRT_TF"]),
        "is_pass_through": boolean(row["DURCHFAHRT_TF"]),
        "quality_issue": "|".join(issues) or None,
        "source_file": source,
        "source_row": row_number,
    }


def normalize_weather(row: dict, start: date, end: date) -> dict | None:
    ts = datetime.strptime(row["reference_timestamp"], "%d.%m.%Y %H:%M").replace(tzinfo=UTC)
    # Include a boundary day for after-midnight services and the prior-hour join.
    if not start <= ts.date() <= end:
        return None

    def number(column):
        value = row.get(column, "").strip()
        return float(value) if value else None

    return {
        "weather_station_id": row["station_abbr"].upper(),
        "interval_end_utc": ts.isoformat(),
        "temperature_c": number("tre200h0"),
        "precipitation_mm": number("rre150h0"),
        "wind_gust_kmh": number("fu3010h1"),
    }
