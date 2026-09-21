-- Missing days inside the loaded interval should be visible, not silently averaged away.
{{ config(severity='warn') }}
select d.date_id
from {{ ref('dim_date') }} d
left join {{ ref('stg_transport') }} t on d.date_id = t.operating_date
where t.operating_date is null
