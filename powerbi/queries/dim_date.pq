// Create a blank query named dim_date and paste this into Advanced Editor.
// ExportFolder is a text parameter pointing at exports/demo or exports/live.
let
    Source = Csv.Document(File.Contents(ExportFolder & "/dim_date.csv"),
        [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    EmptyAsNull = Table.ReplaceValue(Headers, "", null, Replacer.ReplaceValue,
        Table.ColumnNames(Headers)),
    Typed = Table.TransformColumnTypes(EmptyAsNull, {
        {"date_id", type date},
        {"year_number", Int64.Type},
        {"month_number", Int64.Type},
        {"year_month", type text},
        {"weekday_number", Int64.Type},
        {"weekday_name", type text},
        {"is_weekend", type logical}
    }, "en-US")
in
    Typed
