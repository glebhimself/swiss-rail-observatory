"""Run from the repository root: rail demo, rail sync, rail build, rail export."""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
from datetime import date, timedelta
from pathlib import Path

import httpx

from .demo import generate_demo
from .ingest import ingest_local, sync_transport, sync_weather
from .settings import Settings, project_root
from .warehouse import build, dbt, export, status


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description="Swiss Rail Observatory warehouse")
    command.add_argument("--mode", choices=["demo", "live"], default="demo")
    sub = command.add_subparsers(dest="command", required=True)
    demo = sub.add_parser("demo", help="Generate synthetic inputs, build, test, and export")
    demo.add_argument("--days", type=int, default=90)
    for name in ["sync", "ingest"]:
        operation = sub.add_parser(
            name,
            help="Download official data"
            if name == "sync"
            else "Import previously downloaded CSV or ZIP files",
        )
        operation.add_argument("--start", type=date.fromisoformat)
        operation.add_argument("--end", type=date.fromisoformat)
        if name == "sync":
            operation.add_argument(
                "--source", choices=["all", "transport", "weather"], default="all"
            )
            operation.add_argument(
                "--refresh",
                action="store_true",
                help="Recheck loaded transport days for source corrections",
            )
        else:
            operation.add_argument("--transport-file", action="append", type=Path, required=True)
    for name in ["build", "export", "status", "docs"]:
        sub.add_parser(name)
    return command


def main():
    args = parser().parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        settings = Settings(project_root(), args.mode)
        settings.prepare()
        if args.command == "demo":
            if args.days < 1 or args.days > 366:
                raise ValueError("Demo days must be between 1 and 366")
            generate_demo(settings, count=args.days)
            build(settings)
            result = export(settings)
        elif args.command in {"sync", "ingest"}:
            if settings.mode != "live":
                raise ValueError(
                    "Official data must use --mode live, to keep demo inputs separate."
                )
            end = args.end or date.today() - timedelta(days=2)
            start = args.start or end - timedelta(days=settings.config["study_days"] - 1)
            if end < start:
                raise ValueError("End date precedes start date")
            if args.command == "ingest":
                result = [
                    r for p in args.transport_file for r in ingest_local(settings, p, start, end)
                ]
            else:
                result, failures = {}, []
                if args.source in {"all", "transport"}:
                    result["transport"] = sync_transport(settings, start, end, args.refresh)
                    if result["transport"]["missing"] or result["transport"]["errors"]:
                        failures.append(
                            "Transport interval is incomplete. See data/live/transport_sync.json."
                        )
                if args.source in {"all", "weather"}:
                    try:
                        result["weather"] = sync_weather(settings, start, end)
                    except (httpx.HTTPError, ValueError) as error:
                        failures.append(f"Weather sync failed: {error}")
                print(json.dumps(result, indent=2, default=str))
                if failures:
                    raise ValueError(" ".join(failures))
                return
        elif args.command == "build":
            build(settings)
            result = {"status": "dbt models and tests passed", "mode": settings.mode}
        elif args.command == "export":
            result = export(settings)
        elif args.command == "docs":
            dbt(settings, "docs", ["generate"])
            result = {"docs": str(settings.data / "dbt-target/index.html")}
        else:
            result = status(settings)
        if isinstance(result, dict) and "analyses" in result:
            result = {k: v for k, v in result.items() if k != "analyses"}
        print(json.dumps(result, indent=2, default=str))
    except (ValueError, RuntimeError, httpx.HTTPError, subprocess.CalledProcessError) as error:
        logging.error("%s", error)
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
