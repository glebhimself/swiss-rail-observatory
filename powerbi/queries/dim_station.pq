// Create a blank query named dim_station and paste this into Advanced Editor.
// ExportFolder is a text parameter pointing at exports/demo or exports/live.
let
    Source = Csv.Document(File.Contents(ExportFolder & "/dim_station.csv"),
        [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    EmptyAsNull = Table.ReplaceValue(Headers, "", null, Replacer.ReplaceValue,
        Table.ColumnNames(Headers)),
    Typed = Table.TransformColumnTypes(EmptyAsNull, {
        {"station_id", type text},
        {"station_name", type text},
        {"canton", type text},
        {"latitude", type number},
        {"longitude", type number},
        {"weather_station_id", type text},
        {"mapping_note", type text},
        {"weather_station_name", type text},
        {"weather_latitude", type number},
        {"weather_longitude", type number},
        {"weather_distance_km", type number}
    }, "en-US")
in
    Typed
