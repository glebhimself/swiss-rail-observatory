select
    s.station_name,
    count(*) as eligible_arrivals,
    count(*) filter (where is_measured_arrival) as measured_arrivals,
    round(100.0 * avg(cast(is_on_time as integer)), 2) as all_reported_on_time_pct,
    round(100.0 * avg(cast(is_on_time as integer))
          filter (where is_measured_arrival), 2) as measured_only_on_time_pct
from {{ ref('fct_stop_event') }} e
join {{ ref('dim_station') }} s using (station_id)
where is_eligible_arrival
group by s.station_name
order by s.station_name
