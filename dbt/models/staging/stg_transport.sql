-- Grain: one scheduled visit by a journey to a selected station on an operating day.
-- Corrections within a file take the last source row. Never include a prediction
-- in the event key; otherwise a corrected prediction would create a second event.
select * exclude (dedup_rank)
from (
    select *, row_number() over (
        partition by event_id order by source_row desc
    ) as dedup_rank
    from {{ source('raw', 'transport') }}
)
where dedup_rank = 1
