{{ config(tags=['customer_features_v4']) }}
SELECT client_id FROM {{ ref('ml_customer_features') }}
WHERE unique_pages_30d>page_views_30d
 OR has_cart_activity_30d!=toUInt8(cart_adds_30d>0)
 OR has_behavioral_activity_30d!=toUInt8(page_views_30d+cart_adds_30d+cart_removals_30d+searches_30d>0)
 OR page_views_30d<0 OR unique_pages_30d<0 OR cart_adds_30d<0 OR cart_removals_30d<0 OR searches_30d<0
