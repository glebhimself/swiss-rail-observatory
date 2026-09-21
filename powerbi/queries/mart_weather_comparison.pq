// Create a blank query named mart_weather_comparison and paste this into Advanced Editor.
// ExportFolder is a text parameter pointing at exports/demo or exports/live.
let
    Source = Csv.Document(File.Contents(ExportFolder & "/mart_weather_comparison.csv"),
        [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    EmptyAsNull = Table.ReplaceValue(Headers, "", null, Replacer.ReplaceValue,
        Table.ColumnNames(Headers)),
    Typed = Table.TransformColumnTypes(EmptyAsNull, {
        {"station_id", type text},
        {"hour_number", Int64.Type},
        {"weekday_number", Int64.Type},
        {"precipitation_band", type text},
        {"temperature_band", type text},
        {"eligible_arrivals", Int64.Type},
        {"operating_days", Int64.Type},
        {"on_time_arrivals", Int64.Type},
        {"mean_delay_seconds", type number},
        {"p90_delay_seconds", type number}
    }, "en-US")
in
    Typed
