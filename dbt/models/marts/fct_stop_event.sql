with events as (
    select
        t.*,
        md5(to_json(list_value(operator_id, line_name, product))) as service_id,
        coalesce(hour(scheduled_arrival_local), hour(scheduled_departure_local), -1) as hour_number,
        not is_extra and not is_pass_through as is_scheduled_stop,
        date_diff('second', scheduled_arrival_utc, reported_arrival_utc) as arrival_delay_seconds
    from {{ ref('stg_transport') }} t
), eligibility as (
    select *,
        is_scheduled_stop and not is_cancelled
            and scheduled_arrival_local is not null as is_expected_arrival,
        is_scheduled_stop and not is_cancelled
            and scheduled_arrival_utc is not null and reported_arrival_utc is not null
            and arrival_status in ('REAL', 'PROGNOSE', 'GESCHAETZT')
            and quality_issue is null as is_eligible_arrival
    from events
)
select
    e.*,
    case when is_eligible_arrival
         then arrival_delay_seconds < {{ var('arrival_threshold_seconds') }} end as is_on_time,
    is_eligible_arrival and arrival_status = 'REAL' as is_measured_arrival,
    w.interval_end_utc as weather_interval_end_utc,
    w.temperature_c, w.precipitation_mm, w.wind_gust_kmh,
    w.interval_end_utc is not null as has_weather_record,
    case when w.precipitation_mm is null then 'Unknown'
         when w.precipitation_mm >= 1 then 'Wet'
         when w.precipitation_mm > 0 then 'Light precipitation'
         else 'Dry' end as precipitation_band,
    case when w.temperature_c is null then 'Unknown'
         when w.temperature_c <= 0 then 'Freezing'
         when w.temperature_c < 10 then 'Cool'
         when w.temperature_c < 25 then 'Mild'
         else 'Warm' end as temperature_band
from eligibility e
left join {{ ref('dim_station') }} s using (station_id)
left join {{ ref('stg_weather') }} w
    on s.weather_station_id = w.weather_station_id
    -- Last completed clock hour at the scheduled arrival time, in UTC.
    -- 10:45 UTC joins the observation ending at 10:00, never 11:00.
    and w.interval_end_utc = date_trunc('hour', e.scheduled_arrival_utc)
