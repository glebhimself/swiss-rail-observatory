select event_id
from {{ ref('fct_stop_event') }}
where (is_on_time is not null and not is_eligible_arrival)
   or (is_eligible_arrival and (
       is_cancelled or is_extra or is_pass_through or arrival_delay_seconds is null
       or quality_issue is not null or arrival_status = 'UNBEKANNT'))
   or (is_measured_arrival and arrival_status <> 'REAL')
   or (is_eligible_arrival and is_on_time <>
       (arrival_delay_seconds < {{ var('arrival_threshold_seconds') }}))
