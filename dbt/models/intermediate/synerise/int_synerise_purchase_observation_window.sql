{{
    config(
        materialized='table',
        engine='MergeTree()',
        order_by=['observed_start_date']
    )
}}

-- Shared observed envelope, NOT publisher-certified continuous coverage.
SELECT min(first_at) AS observed_start_source, max(last_at) AS observed_end_source,
    toDate(substring(observed_start_source, 1, 10)) AS observed_start_date,
    toDate(substring(observed_end_source, 1, 10)) AS observed_end_date,
    'assumed_continuous_interior_months' AS coverage_policy,
    toUInt8(0) AS coverage_verified
FROM (
{% for event in ['page_visit','search_query','add_to_cart','remove_from_cart','product_buy'] %}
    SELECT min(timestamp) AS first_at, max(timestamp) AS last_at
    FROM {{ source('synerise', event) }}
    {% if not loop.last %}UNION ALL{% endif %}
{% endfor %}
)
