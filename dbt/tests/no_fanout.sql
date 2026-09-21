-- The weather join must not multiply transport events.
select 1 as failure
where (select count(*) from {{ ref('stg_transport') }})
   <> (select count(*) from {{ ref('fct_stop_event') }})
