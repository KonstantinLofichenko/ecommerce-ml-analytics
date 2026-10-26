-- Fixed historical contract, not a production transformation.
select count() as actual_count
from {{ source('ecommerce_raw', 'raw_events') }}
having actual_count != 20692840
