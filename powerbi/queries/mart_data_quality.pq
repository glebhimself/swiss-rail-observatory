// Create a blank query named mart_data_quality and paste this into Advanced Editor.
// ExportFolder is a text parameter pointing at exports/demo or exports/live.
let
    Source = Csv.Document(File.Contents(ExportFolder & "/mart_data_quality.csv"),
        [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    EmptyAsNull = Table.ReplaceValue(Headers, "", null, Replacer.ReplaceValue,
        Table.ColumnNames(Headers)),
    Typed = Table.TransformColumnTypes(EmptyAsNull, {
        {"operating_date", type date},
        {"stop_events", Int64.Type},
        {"unknown_status_events", Int64.Type},
        {"timestamp_or_status_issues", Int64.Type},
        {"expected_arrivals", Int64.Type},
        {"missing_arrivals", Int64.Type},
        {"eligible_arrivals", Int64.Type},
        {"measured_arrivals", Int64.Type},
        {"arrivals_missing_precipitation", Int64.Type}
    }, "en-US")
in
    Typed
