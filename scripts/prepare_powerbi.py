"""Generate typed Power Query queries from the warehouse's exported schema."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TYPES = {
    "VARCHAR": "type text",
    "DATE": "type date",
    "BOOLEAN": "type logical",
    "BIGINT": "Int64.Type",
    "INTEGER": "Int64.Type",
    "HUGEINT": "Int64.Type",
    "DOUBLE": "type number",
    "TIMESTAMP": "type datetime",
    "TIMESTAMP WITH TIME ZONE": "type datetimezone",
}


def main():
    schema = json.loads((ROOT / "exports/demo/schema.json").read_text())
    destination = ROOT / "powerbi/queries"
    destination.mkdir(parents=True, exist_ok=True)
    for table, columns in schema.items():
        conversion = ",\n        ".join(
            '{"' + column["column_name"] + '", ' + TYPES[column["column_type"]] + "}"
            for column in columns
        )
        zone_columns = [
            c["column_name"] for c in columns if c["column_type"] == "TIMESTAMP WITH TIME ZONE"
        ]
        zone_conversion = ",\n        ".join(
            '{"' + c + '", each if _ = null then null else '
            "DateTimeZone.RemoveZone(DateTimeZone.SwitchZone(_, 0)), type datetime}"
            for c in zone_columns
        )
        text = f"""// Create a blank query named {table} and paste this into Advanced Editor.
// ExportFolder is a text parameter pointing at exports/demo or exports/live.
let
    Source = Csv.Document(File.Contents(ExportFolder & "/{table}.csv"),
        [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    EmptyAsNull = Table.ReplaceValue(Headers, "", null, Replacer.ReplaceValue,
        Table.ColumnNames(Headers)),
    Typed = Table.TransformColumnTypes(EmptyAsNull, {{
        {conversion}
    }}, "en-US")"""
        if zone_columns:
            text += f""",
    // Power BI's model stores datetime without an offset. Keep these columns in UTC.
    UTC = Table.TransformColumns(Typed, {{
        {zone_conversion}
    }})
in
    UTC
"""
        else:
            text += "\nin\n    Typed\n"
        (destination / f"{table}.pq").write_text(text)
    print(f"Prepared {len(schema)} typed Power Query queries.")


if __name__ == "__main__":
    main()
