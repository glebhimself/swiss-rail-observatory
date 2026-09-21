select weather_station_id, interval_end_utc
from {{ ref('stg_weather') }}
group by all having count(*) > 1
union all
select weather_station_id, interval_end_utc
from {{ ref('stg_weather') }}
where precipitation_mm < 0 or wind_gust_kmh < 0
   or temperature_c not between -60 and 60
