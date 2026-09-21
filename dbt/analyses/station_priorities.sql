-- A ranking of stop-event reliability, not passenger-weighted punctuality.
select
    s.station_name,
    count(*) as eligible_arrivals,
    count(distinct e.operating_date) as operating_days,
    round(100.0 * count(*) filter (where is_on_time) / count(*), 2) as on_time_pct,
    round(quantile_cont(arrival_delay_seconds, .9) / 60.0, 2) as p90_delay_minutes
from {{ ref('fct_stop_event') }} e
join {{ ref('dim_station') }} s using (station_id)
where is_eligible_arrival
group by s.station_name
having count(*) >= {{ var('minimum_group_arrivals') }}
order by on_time_pct, eligible_arrivals desc
