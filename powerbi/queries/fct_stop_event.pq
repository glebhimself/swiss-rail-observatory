// Create a blank query named fct_stop_event and paste this into Advanced Editor.
// ExportFolder is a text parameter pointing at exports/demo or exports/live.
let
    Source = Csv.Document(File.Contents(ExportFolder & "/fct_stop_event.csv"),
        [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    EmptyAsNull = Table.ReplaceValue(Headers, "", null, Replacer.ReplaceValue,
        Table.ColumnNames(Headers)),
    Typed = Table.TransformColumnTypes(EmptyAsNull, {
        {"event_id", type text},
        {"operating_date", type date},
        {"station_id", type text},
        {"journey_id", type text},
        {"operator_id", type text},
        {"operator_name", type text},
        {"line_name", type text},
        {"product", type text},
        {"scheduled_arrival_local", type datetime},
        {"scheduled_arrival_utc", type datetimezone},
        {"reported_arrival_local", type datetime},
        {"reported_arrival_utc", type datetimezone},
        {"scheduled_departure_local", type datetime},
        {"arrival_status", type text},
        {"is_cancelled", type logical},
        {"is_extra", type logical},
        {"is_pass_through", type logical},
        {"quality_issue", type text},
        {"source_file", type text},
        {"source_row", Int64.Type},
        {"service_id", type text},
        {"hour_number", Int64.Type},
        {"is_scheduled_stop", type logical},
        {"arrival_delay_seconds", Int64.Type},
        {"is_expected_arrival", type logical},
        {"is_eligible_arrival", type logical},
        {"is_on_time", type logical},
        {"is_measured_arrival", type logical},
        {"weather_interval_end_utc", type datetimezone},
        {"temperature_c", type number},
        {"precipitation_mm", type number},
        {"wind_gust_kmh", type number},
        {"has_weather_record", type logical},
        {"precipitation_band", type text},
        {"temperature_band", type text}
    }, "en-US"),
    // Power BI's model stores datetime without an offset. Keep these columns in UTC.
    UTC = Table.TransformColumns(Typed, {
        {"scheduled_arrival_utc", each if _ = null then null else DateTimeZone.RemoveZone(DateTimeZone.SwitchZone(_, 0)), type datetime},
        {"reported_arrival_utc", each if _ = null then null else DateTimeZone.RemoveZone(DateTimeZone.SwitchZone(_, 0)), type datetime},
        {"weather_interval_end_utc", each if _ = null then null else DateTimeZone.RemoveZone(DateTimeZone.SwitchZone(_, 0)), type datetime}
    })
in
    UTC
