-- A service is an operator/line label/product group, not an origin-destination route.
select distinct
    md5(to_json(list_value(operator_id, line_name, product))) as service_id,
    operator_id, line_name, product
from {{ ref('stg_transport') }}
