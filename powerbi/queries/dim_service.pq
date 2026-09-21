// Create a blank query named dim_service and paste this into Advanced Editor.
// ExportFolder is a text parameter pointing at exports/demo or exports/live.
let
    Source = Csv.Document(File.Contents(ExportFolder & "/dim_service.csv"),
        [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    EmptyAsNull = Table.ReplaceValue(Headers, "", null, Replacer.ReplaceValue,
        Table.ColumnNames(Headers)),
    Typed = Table.TransformColumnTypes(EmptyAsNull, {
        {"service_id", type text},
        {"operator_id", type text},
        {"line_name", type text},
        {"product", type text}
    }, "en-US")
in
    Typed
