select
    s.station_name, e.hour_number,
    count(*) as eligible_arrivals,
    count(distinct operating_date) as operating_days,
    round(avg(arrival_delay_seconds) / 60.0, 2) as mean_delay_minutes,
    round(100.0 * count(*) filter (where is_on_time) / count(*), 2) as on_time_pct
from {{ ref('fct_stop_event') }} e
join {{ ref('dim_station') }} s using (station_id)
where is_eligible_arrival
group by s.station_name, e.hour_number
having count(*) >= {{ var('minimum_group_arrivals') }}
order by on_time_pct
