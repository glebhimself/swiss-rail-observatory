select event_id
from {{ ref('fct_stop_event') }}
where weather_interval_end_utc > scheduled_arrival_utc
   or date_diff('minute', weather_interval_end_utc, scheduled_arrival_utc) not between 0 and 59
