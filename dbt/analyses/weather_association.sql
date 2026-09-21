-- Compare within station/hour/weekday strata observed under both wet and dry weather.
-- Weight by the smaller group to limit domination by unbalanced strata.
-- Wet >= 1 mm in the prior completed hour. This is descriptive, not causal.
with strata as (
    select
        station_id, hour_number, dayofweek(operating_date) as weekday_number,
        count(*) filter (where precipitation_band = 'Wet') as wet_n,
        count(*) filter (where precipitation_band = 'Dry') as dry_n,
        count(distinct operating_date) filter (where precipitation_band = 'Wet') as wet_days,
        count(distinct operating_date) filter (where precipitation_band = 'Dry') as dry_days,
        avg(arrival_delay_seconds) filter (where precipitation_band = 'Wet') as wet_delay,
        avg(arrival_delay_seconds) filter (where precipitation_band = 'Dry') as dry_delay
    from {{ ref('fct_stop_event') }}
    where is_eligible_arrival
    group by all
), supported as (
    select *, least(wet_n, dry_n) as comparison_weight
    from strata where wet_n >= 5 and dry_n >= 5 and wet_days >= 3 and dry_days >= 3
)
select
    s.station_name,
    count(*) as comparable_strata,
    sum(wet_n) as wet_arrivals,
    sum(dry_n) as dry_arrivals,
    round(sum((wet_delay - dry_delay) * comparison_weight)
        / sum(comparison_weight) / 60.0, 2) as wet_minus_dry_minutes
from supported p
join {{ ref('dim_station') }} s using (station_id)
group by s.station_name
order by wet_minus_dry_minutes desc
