from datetime import date

import pytest

from swiss_rail.ingest import ingest_transport_file, ingest_weather_csv
from swiss_rail.storage import connect

from .conftest import event, write_events

DAY = date(2026, 6, 1)


def test_rerun_is_idempotent_and_changed_partition_removes_deleted_events(settings):
    path = write_events(
        settings.data / "2026-06-01_istdaten.csv",
        [
            event(),
            event(FAHRT_BEZEICHNER="TEST:2"),
        ],
    )
    assert ingest_transport_file(settings, path, DAY)["rows"] == 2
    assert ingest_transport_file(settings, path, DAY)["status"] == "unchanged"
    write_events(path, [event(AN_PROGNOSE="01.06.2026 11:00:00")])
    assert ingest_transport_file(settings, path, DAY)["rows"] == 1
    with connect(settings) as conn:
        assert conn.execute("select count(*) from raw.transport").fetchone()[0] == 1
        assert conn.execute("select count(*) from raw.ingestion_log").fetchone()[0] == 1
        assert (
            conn.execute("select minute(reported_arrival_local) from raw.transport").fetchone()[0]
            == 0
        )


def test_schema_failure_retains_previous_partition(settings):
    path = write_events(settings.data / "2026-06-01_istdaten.csv", [event()])
    ingest_transport_file(settings, path, DAY)
    path.write_text("html,error\nnot,csv\n")
    with pytest.raises(ValueError, match="schema changed"):
        ingest_transport_file(settings, path, DAY)
    with connect(settings) as conn:
        assert conn.execute("select count(*) from raw.transport").fetchone()[0] == 1


def test_zero_selected_rows_do_not_erase_previous_data(settings):
    path = write_events(settings.data / "2026-06-01_istdaten.csv", [event()])
    ingest_transport_file(settings, path, DAY)
    write_events(path, [event(PRODUKT_ID="Bus")])
    with pytest.raises(ValueError, match="No selected rail events"):
        ingest_transport_file(settings, path, DAY)
    with connect(settings) as conn:
        assert conn.execute("select count(*) from raw.transport").fetchone()[0] == 1


def test_comma_delimited_transport_supported(settings):
    path = write_events(settings.data / "2026-06-01_istdaten.csv", [event()], ",")
    assert ingest_transport_file(settings, path, DAY)["rows"] == 1


def test_weather_corrections_replace_instead_of_append(settings):
    path = settings.data / "weather.csv"
    header = "station_abbr;reference_timestamp;tre200h0;rre150h0;fu3010h1\n"
    path.write_text(header + "SMA;01.06.2026 08:00;12;0;20\n")
    ingest_weather_csv(settings, path, "SMA", DAY, DAY)
    path.write_text(header + "SMA;01.06.2026 08:00;12;1.5;20\n")
    ingest_weather_csv(settings, path, "SMA", DAY, DAY)
    with connect(settings) as conn:
        assert conn.execute(
            "select count(*), max(precipitation_mm) from raw.weather"
        ).fetchone() == (1, 1.5)


def test_deleted_weather_boundary_is_removed(settings):
    path = settings.data / "weather.csv"
    header = "station_abbr;reference_timestamp;tre200h0;rre150h0;fu3010h1\n"
    path.write_text(header + "SMA;01.06.2026 08:00;12;0;20\nSMA;01.06.2026 09:00;13;0;20\n")
    ingest_weather_csv(settings, path, "SMA", DAY, DAY)
    path.write_text(header + "SMA;01.06.2026 09:00;13;0;20\n")
    ingest_weather_csv(settings, path, "SMA", DAY, DAY)
    with connect(settings) as conn:
        assert conn.execute("select count(*) from raw.weather").fetchone()[0] == 1


def test_weather_year_boundary_uses_both_disjoint_assets():
    from swiss_rail.ingest import weather_asset_window

    start, end, today = date(2026, 1, 1), date(2026, 1, 3), date(2026, 9, 5)
    assert weather_asset_window("sma_h_historical_2020-2029.csv", start, end, today) == (
        date(2025, 12, 31),
        date(2025, 12, 31),
    )
    assert weather_asset_window("sma_h_recent.csv", start, end, today) == (
        date(2026, 1, 1),
        date(2026, 1, 4),
    )
