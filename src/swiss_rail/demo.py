"""Deterministic synthetic inputs for offline demos and integration tests.

No generated value is presented as an observation about Swiss transport.
"""

from __future__ import annotations

import csv
import math
import random
from datetime import UTC, date, datetime, timedelta

from .ingest import days, ingest_transport_file, ingest_weather_csv
from .settings import Settings
from .storage import connect

HEADERS = [
    "BETRIEBSTAG",
    "FAHRT_BEZEICHNER",
    "BETREIBER_ID",
    "BETREIBER_NAME",
    "PRODUKT_ID",
    "LINIEN_TEXT",
    "BPUIC",
    "ANKUNFTSZEIT",
    "AN_PROGNOSE",
    "AN_PROGNOSE_STATUS",
    "ABFAHRTSZEIT",
    "FAELLT_AUS_TF",
    "ZUSATZFAHRT_TF",
    "DURCHFAHRT_TF",
]


def generate_demo(settings: Settings, start: date = date(2026, 6, 1), count: int = 90):
    if settings.mode != "demo":
        raise ValueError("Synthetic data can only be written to demo storage")
    settings.prepare()
    raw = settings.data / "inputs"
    raw.mkdir(exist_ok=True)
    randomizer = random.Random(260905)
    end = start + timedelta(days=count - 1)
    for day_index, day in enumerate(days(start, end)):
        path = raw / f"{day}_istdaten.csv"
        with path.open("w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=HEADERS, delimiter=";")
            writer.writeheader()
            for station_index, station in enumerate(settings.stations):
                for departure in range(36):
                    scheduled = datetime.combine(day, datetime.min.time()) + timedelta(
                        hours=6, minutes=departure * 30
                    )
                    wet = (day_index + station_index) % 5 == 0
                    peak = scheduled.hour in {7, 8, 17, 18}
                    delay = int(
                        randomizer.expovariate(1 / 100)
                        + station_index * 12
                        + (110 if wet else 0)
                        + (65 if peak else 0)
                        - 70
                    )
                    if randomizer.random() < 0.035:
                        delay += 900
                    cancelled = randomizer.random() < 0.015
                    unknown = randomizer.random() < 0.035
                    status = (
                        "UNBEKANNT"
                        if unknown
                        else randomizer.choices(
                            ["REAL", "PROGNOSE", "GESCHAETZT"], weights=[60, 35, 5]
                        )[0]
                    )
                    row = {
                        "BETRIEBSTAG": day.strftime("%d.%m.%Y"),
                        "FAHRT_BEZEICHNER": f"DEMO:{departure:03}",
                        "BETREIBER_ID": "DEMO:1",
                        "BETREIBER_NAME": "Synthetic rail operator",
                        "PRODUKT_ID": "Zug",
                        "LINIEN_TEXT": f"DEMO IR {departure % 4 + 1}",
                        "BPUIC": station["station_id"],
                        "ANKUNFTSZEIT": scheduled.strftime("%d.%m.%Y %H:%M"),
                        "AN_PROGNOSE": ""
                        if cancelled or unknown
                        else (scheduled + timedelta(seconds=delay)).strftime("%d.%m.%Y %H:%M:%S"),
                        "AN_PROGNOSE_STATUS": status,
                        "ABFAHRTSZEIT": (scheduled + timedelta(minutes=2)).strftime(
                            "%d.%m.%Y %H:%M"
                        ),
                        "FAELLT_AUS_TF": str(cancelled).lower(),
                        "ZUSATZFAHRT_TF": str(departure == 35).lower(),
                        "DURCHFAHRT_TF": str(departure == 34 and day_index % 7 == 0).lower(),
                    }
                    writer.writerow(row)
                    if departure == 0:  # An exact duplicate to exercise deduplication.
                        writer.writerow(row)
        ingest_transport_file(settings, path, day, "synthetic://seed-260905")
    for index, station in enumerate(settings.stations):
        weather = station["weather_station_id"]
        path = raw / f"ogd-smn_{weather.lower()}_h_demo.csv"
        with path.open("w", newline="", encoding="cp1252") as file:
            writer = csv.writer(file, delimiter=";")
            writer.writerow(
                ["station_abbr", "reference_timestamp", "tre200h0", "rre150h0", "fu3010h1"]
            )
            for day_index, day in enumerate(
                days(start - timedelta(days=1), end + timedelta(days=1))
            ):
                for hour in range(24):
                    stamp = datetime.combine(day, datetime.min.time(), tzinfo=UTC).replace(
                        hour=hour
                    )
                    wet = (day_index - 1 + index) % 5 == 0
                    temperature = round(15 + 6 * math.sin(hour / 24 * 2 * math.pi) + index / 2, 1)
                    rain = round(0.2 + (hour % 5) * 0.3, 1) if wet else 0
                    missing = hour == 13 and day_index % 13 == 0
                    writer.writerow(
                        [
                            weather,
                            stamp.strftime("%d.%m.%Y %H:%M"),
                            "" if missing else temperature,
                            "" if missing else rain,
                            25 if wet else 9,
                        ]
                    )
        ingest_weather_csv(
            settings,
            path,
            weather,
            start - timedelta(days=1),
            end + timedelta(days=1),
            "synthetic://seed-260905",
        )
        with connect(settings) as conn:
            conn.execute(
                "insert or replace into raw.weather_metadata values (?,?,?,?,?)",
                [
                    weather,
                    f"Synthetic {weather}",
                    float(station["latitude"]) + 0.03,
                    float(station["longitude"]) + 0.02,
                    "synthetic://regional-proxy",
                ],
            )
    return {"mode": "demo", "days": count, "start": str(start), "end": str(end)}
