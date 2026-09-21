"""Create a portable Power BI handoff without copying raw downloads or credentials."""

from __future__ import annotations

import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    source = ROOT / "exports/demo"
    if not (source / "summary.json").exists():
        raise SystemExit("Run rail demo before packaging the handoff.")
    destination = ROOT / "exports/powerbi-demo.zip"
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(source.iterdir()):
            if path.is_file() and not path.is_symlink() and path.suffix in {".csv", ".json"}:
                archive.write(path, path.relative_to(ROOT))
        # Publish BI assets only; the learning website and Markdown notes are private.
        for folder, extensions in [
            ("powerbi", {".pq", ".dax", ".json", ".pbix"}),
            ("docs/screenshots", {".png"}),
        ]:
            for path in sorted((ROOT / folder).rglob("*")):
                if path.is_file() and not path.is_symlink() and path.suffix in extensions:
                    archive.write(path, path.relative_to(ROOT))
        archive.write(ROOT / "README.md", "README.md")
        archive.writestr(
            "START-HERE.txt",
            "# Power BI demo handoff\n\nExtract the entire archive. "
            "Set ExportFolder to the extracted exports/demo directory. "
            "See README.md for refresh instructions. "
            "The data is synthetic. The author completed the three-page report "
            "and confirmed its totals and filter checks in Power BI Desktop. "
            "Open powerbi/report/report.pbix if included; change ExportFolder "
            "before refreshing on another Windows machine.\n",
        )
        archive.writestr(
            "DATA-NOTICE.txt",
            "All data in exports/demo is synthetic. Do not present these numbers "
            "as findings about Swiss transport. Extract this archive and set "
            "ExportFolder to the extracted exports/demo directory.\n",
        )
    print(f"Power BI handoff: {destination} ({destination.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
