"""Project-relative paths keep demo and live state separate."""

from __future__ import annotations

import csv
import os
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class Settings:
    root: Path
    mode: str = "demo"

    def __post_init__(self):
        if self.mode not in {"demo", "live"}:
            raise ValueError("Mode must be demo or live")

    @property
    def data(self) -> Path:
        return self.root / "data" / self.mode

    @property
    def database(self) -> Path:
        return self.data / "warehouse.duckdb"

    @property
    def exports(self) -> Path:
        return self.root / "exports" / self.mode

    @property
    def config(self) -> dict:
        return yaml.safe_load((self.root / "config/project.yml").read_text())

    @property
    def stations(self) -> list[dict]:
        with (self.root / "dbt/seeds/stations.csv").open(newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))

    def prepare(self):
        self.data.mkdir(parents=True, exist_ok=True)
        self.exports.mkdir(parents=True, exist_ok=True)


def project_root() -> Path:
    root = Path(os.environ.get("RAIL_ROOT", Path.cwd())).resolve()
    if not (root / "config/project.yml").exists():
        raise ValueError("Run rail from the repository root, or set RAIL_ROOT to that folder.")
    return root
