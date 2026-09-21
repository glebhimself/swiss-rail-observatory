{{ config(severity='warn') }}
select source_key, rejected_count
from {{ source('raw', 'ingestion_log') }}
where rejected_count > 0
