select
    operating_date, station_id,
    count(*) as stop_events,
    count(*) filter (where is_scheduled_stop) as scheduled_stops,
    count(*) filter (where is_scheduled_stop and is_cancelled) as cancelled_stops,
    count(*) filter (where is_expected_arrival) as expected_arrivals,
    count(*) filter (where is_eligible_arrival) as eligible_arrivals,
    count(*) filter (where is_on_time) as on_time_arrivals,
    count(*) filter (where is_measured_arrival) as measured_arrivals,
    count(*) filter (where is_eligible_arrival and precipitation_mm is not null)
        as arrivals_with_precipitation,
    sum(arrival_delay_seconds) filter (where is_eligible_arrival) as delay_seconds_sum,
    quantile_cont(arrival_delay_seconds, 0.9) filter (where is_eligible_arrival)
        as p90_delay_seconds
from {{ ref('fct_stop_event') }}
group by operating_date, station_id
