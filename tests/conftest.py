from __future__ import annotations

import csv
import shutil
from pathlib import Path

import pytest

from swiss_rail.demo import HEADERS
from swiss_rail.settings import Settings

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def settings(tmp_path):
    shutil.copytree(ROOT / "config", tmp_path / "config")
    shutil.copytree(
        ROOT / "dbt",
        tmp_path / "dbt",
        ignore=shutil.ignore_patterns("logs", "target", "dbt_packages"),
    )
    result = Settings(tmp_path)
    result.prepare()
    return result


def event(**changes):
    row = dict(
        zip(
            HEADERS,
            [
                "01.06.2026",
                "TEST:1",
                "TEST",
                "Test operator",
                "Zug",
                "IR 1",
                "8503000",
                "01.06.2026 10:45",
                "01.06.2026 10:47:59",
                "REAL",
                "01.06.2026 10:48",
                "false",
                "false",
                "false",
            ],
            strict=True,
        )
    )
    row.update(changes)
    return row


def write_events(path, rows, delimiter=";"):
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=HEADERS, delimiter=delimiter)
        writer.writeheader()
        writer.writerows(rows)
    return path
