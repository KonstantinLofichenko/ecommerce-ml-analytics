# Verified source schema

| File | Column | DuckDB type | Nullable schema | Observed nulls |
| --- | --- | --- | --- | --- |
| page_visit | client_id | BIGINT | YES | 0 |
| page_visit | timestamp | VARCHAR | YES | 0 |
| page_visit | url | BIGINT | YES | 0 |
| search_query | client_id | BIGINT | YES | 0 |
| search_query | timestamp | VARCHAR | YES | 0 |
| search_query | query | VARCHAR | YES | 0 |
| add_to_cart | client_id | BIGINT | YES | 0 |
| add_to_cart | timestamp | VARCHAR | YES | 0 |
| add_to_cart | sku | BIGINT | YES | 0 |
| remove_from_cart | client_id | BIGINT | YES | 0 |
| remove_from_cart | timestamp | VARCHAR | YES | 0 |
| remove_from_cart | sku | BIGINT | YES | 0 |
| product_buy | client_id | BIGINT | YES | 0 |
| product_buy | timestamp | VARCHAR | YES | 0 |
| product_buy | sku | BIGINT | YES | 0 |
| product_properties | sku | BIGINT | YES | 0 |
| product_properties | category | BIGINT | YES | 0 |
| product_properties | price | BIGINT | YES | 0 |
| product_properties | name | VARCHAR | YES | 0 |

The name/query fields are VARCHAR vector encodings, not nested arrays. All timestamps are VARCHAR, parsed as timezone-naive TIMESTAMP.
