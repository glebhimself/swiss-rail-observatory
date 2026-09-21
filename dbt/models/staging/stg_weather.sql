select
    weather_station_id,
    interval_end_utc,
    temperature_c,
    precipitation_mm,
    wind_gust_kmh
from {{ source('raw', 'weather') }}
