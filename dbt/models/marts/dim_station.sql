select
    s.*,
    w.station_name as weather_station_name,
    w.latitude as weather_latitude,
    w.longitude as weather_longitude,
    -- Haversine distance in km, using curated approximate railway coordinates.
    round(6371 * 2 * asin(sqrt(least(1.0,
        pow(sin(radians(w.latitude - s.latitude) / 2), 2)
        + cos(radians(s.latitude)) * cos(radians(w.latitude))
        * pow(sin(radians(w.longitude - s.longitude) / 2), 2)
    ))), 1) as weather_distance_km
from {{ ref('stations') }} s
left join {{ source('raw', 'weather_metadata') }} w using (weather_station_id)
