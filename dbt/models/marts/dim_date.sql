with bounds as (
    select min(operating_date) as first_date, max(operating_date) as last_date
    from {{ ref('stg_transport') }}
), dates as (
    select cast(value as date) as date_id
    from bounds, generate_series(first_date, last_date, interval 1 day) t(value)
)
select
    date_id,
    year(date_id) as year_number,
    month(date_id) as month_number,
    strftime(date_id, '%Y-%m') as year_month,
    dayofweek(date_id) as weekday_number,
    dayname(date_id) as weekday_name,
    dayofweek(date_id) in (0, 6) as is_weekend
from dates
