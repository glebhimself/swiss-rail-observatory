-- Stratify by station, local scheduled hour, and weekday before comparing weather.
select
    station_id, hour_number, dayofweek(operating_date) as weekday_number,
    precipitation_band, temperature_band,
    count(*) as eligible_arrivals,
    count(distinct operating_date) as operating_days,
    count(*) filter (where is_on_time) as on_time_arrivals,
    avg(arrival_delay_seconds) as mean_delay_seconds,
    quantile_cont(arrival_delay_seconds, .9) as p90_delay_seconds
from {{ ref('fct_stop_event') }}
where is_eligible_arrival
group by all
