select operator_id, max(operator_name) as operator_name
from {{ ref('stg_transport') }}
group by operator_id
