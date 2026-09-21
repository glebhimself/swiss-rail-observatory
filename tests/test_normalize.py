from datetime import date

import pytest

from swiss_rail.normalize import boolean, local_timestamp, normalize_transport, normalize_weather
from swiss_rail.normalize import station_id as canonical_station

from .conftest import event


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("8503000", "8503000"),
        ("850300002", "8503000"),
        ("ch:1:sloid:3000:0:1", "8503000"),
        ("ch:1:sloid:10", "8500010"),
        ("ch:1:sloid:10008", "8510008"),
        ("INVALID", "INVALID"),
    ],
)
def test_platform_normalization(raw, expected):
    assert canonical_station(raw) == expected


@pytest.mark.parametrize(
    ("text", "utc", "issue"),
    [
        ("01.06.2026 10:45", "2026-06-01T08:45:00+00:00", None),
        ("01.01.2026 00:15:30", "2025-12-31T23:15:30+00:00", None),
        ("25.10.2026 02:30", None, "ambiguous_local_time"),
        ("29.03.2026 02:30", None, "nonexistent_local_time"),
        ("not a time", None, "invalid_timestamp"),
        ("", None, None),
    ],
)
def test_timestamps_never_guess_dst(text, utc, issue):
    _, actual_utc, actual_issue = local_timestamp(text)
    assert (actual_utc, actual_issue) == (utc, issue)


def test_correction_keeps_event_identity_but_repeat_visit_does_not():
    first = normalize_transport(event(), "source.csv", 2)
    corrected = normalize_transport(event(AN_PROGNOSE="01.06.2026 10:50:00"), "source.csv", 3)
    repeat = normalize_transport(event(ANKUNFTSZEIT="01.06.2026 12:45"), "source.csv", 4)
    assert first["event_id"] == corrected["event_id"]
    assert first["event_id"] != repeat["event_id"]


def test_blank_status_means_prediction_not_measured():
    assert normalize_transport(event(AN_PROGNOSE_STATUS=""), "x", 1)["arrival_status"] == "PROGNOSE"


def test_invalid_boolean_is_rejected():
    with pytest.raises(ValueError):
        boolean("maybe")


def test_missing_rain_is_not_zero():
    result = normalize_weather(
        {
            "station_abbr": "SMA",
            "reference_timestamp": "01.06.2026 08:00",
            "tre200h0": "12.4",
            "rre150h0": "",
            "fu3010h1": "18",
        },
        date(2026, 6, 1),
        date(2026, 6, 1),
    )
    assert result["precipitation_mm"] is None
    assert result["interval_end_utc"] == "2026-06-01T08:00:00+00:00"
