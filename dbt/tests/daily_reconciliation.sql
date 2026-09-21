select operating_date, station_id
from {{ ref('mart_station_daily') }}
where on_time_arrivals > eligible_arrivals
   or eligible_arrivals > expected_arrivals
   or measured_arrivals > eligible_arrivals
   or cancelled_stops > scheduled_stops
   or arrivals_with_precipitation > eligible_arrivals
