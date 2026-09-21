from datetime import date

from swiss_rail.ingest import ingest_transport_file, ingest_weather_csv
from swiss_rail.storage import connect
from swiss_rail.warehouse import build, export

from .conftest import event, write_events


def test_end_to_end_metric_boundaries_and_weather_join(settings):
    path = write_events(
        settings.data / "2026-06-01_istdaten.csv",
        [
            event(),
            event(),  # Duplicate; one eligible event at 179 seconds.
            event(FAHRT_BEZEICHNER="AT_THRESHOLD", AN_PROGNOSE="01.06.2026 10:48:00"),
            event(FAHRT_BEZEICHNER="CANCELLED", FAELLT_AUS_TF="true"),
            event(FAHRT_BEZEICHNER="EXTRA", ZUSATZFAHRT_TF="true"),
            event(FAHRT_BEZEICHNER="PASS", DURCHFAHRT_TF="true"),
            event(FAHRT_BEZEICHNER="UNKNOWN", AN_PROGNOSE_STATUS="UNBEKANNT"),
            event(FAHRT_BEZEICHNER="MISSING", AN_PROGNOSE=""),
            event(
                FAHRT_BEZEICHNER="MIDNIGHT",
                ANKUNFTSZEIT="02.06.2026 00:05",
                AN_PROGNOSE="02.06.2026 00:04:30",
                ABFAHRTSZEIT="02.06.2026 00:06",
            ),
        ],
    )
    ingest_transport_file(settings, path, date(2026, 6, 1))
    weather = settings.data / "weather.csv"
    weather.write_text(
        "station_abbr;reference_timestamp;tre200h0;rre150h0;fu3010h1\n"
        "SMA;01.06.2026 08:00;12;1.5;20\n"
        "SMA;01.06.2026 09:00;13;9;25\n"
        "SMA;01.06.2026 22:00;10;0;15\n"
    )
    ingest_weather_csv(settings, weather, "SMA", date(2026, 6, 1), date(2026, 6, 1))
    build(settings)
    summary = export(settings)
    assert summary["event_count"] == 8
    assert summary["duplicates_removed"] == 1
    assert summary["eligible_arrivals"] == 3
    assert summary["on_time_arrivals"] == 2  # 179 and -30 seconds; exactly 180 is late.
    assert summary["cancelled_stops"] == 1
    assert summary["weather_match_pct"] == 100
    assert len(summary["analyses"]) == 4
    with connect(settings) as conn:
        value = conn.execute(
            "select precipitation_mm from analytics.fct_stop_event where journey_id='TEST:1'"
        ).fetchone()[0]
        assert value == 1.5  # Uses 08:00 UTC, not the still-in-progress 09:00 observation.
        operating_day = conn.execute(
            "select operating_date from analytics.fct_stop_event where journey_id='MIDNIGHT'"
        ).fetchone()[0]
        assert operating_day == date(2026, 6, 1)
