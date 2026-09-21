// Create a blank query named mart_station_daily and paste this into Advanced Editor.
// ExportFolder is a text parameter pointing at exports/demo or exports/live.
let
    Source = Csv.Document(File.Contents(ExportFolder & "/mart_station_daily.csv"),
        [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    EmptyAsNull = Table.ReplaceValue(Headers, "", null, Replacer.ReplaceValue,
        Table.ColumnNames(Headers)),
    Typed = Table.TransformColumnTypes(EmptyAsNull, {
        {"operating_date", type date},
        {"station_id", type text},
        {"stop_events", Int64.Type},
        {"scheduled_stops", Int64.Type},
        {"cancelled_stops", Int64.Type},
        {"expected_arrivals", Int64.Type},
        {"eligible_arrivals", Int64.Type},
        {"on_time_arrivals", Int64.Type},
        {"measured_arrivals", Int64.Type},
        {"arrivals_with_precipitation", Int64.Type},
        {"delay_seconds_sum", Int64.Type},
        {"p90_delay_seconds", type number}
    }, "en-US")
in
    Typed
