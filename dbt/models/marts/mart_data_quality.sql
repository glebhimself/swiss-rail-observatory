select
    operating_date,
    count(*) as stop_events,
    count(*) filter (where arrival_status = 'UNBEKANNT') as unknown_status_events,
    count(*) filter (where quality_issue is not null) as timestamp_or_status_issues,
    count(*) filter (where is_expected_arrival) as expected_arrivals,
    count(*) filter (where is_expected_arrival and not is_eligible_arrival) as missing_arrivals,
    count(*) filter (where is_eligible_arrival) as eligible_arrivals,
    count(*) filter (where is_measured_arrival) as measured_arrivals,
    count(*) filter (where is_eligible_arrival and precipitation_mm is null)
        as arrivals_missing_precipitation
from {{ ref('fct_stop_event') }}
group by operating_date
