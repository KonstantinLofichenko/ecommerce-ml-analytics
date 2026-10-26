-- One-time audit only: do not replay INSERTs into loaded tables.
CREATE DATABASE IF NOT EXISTS synerise_raw ENGINE=Atomic;

CREATE TABLE synerise_raw.product_properties (`sku` Int64, `category` Int64, `price` Int64, `name` String) ENGINE=MergeTree ORDER BY (`sku`);

INSERT INTO synerise_raw.product_properties (`sku`, `category`, `price`, `name`) SELECT `sku`, `category`, `price`, `name` FROM file('synerise/e90b8fde/product_properties.parquet','Parquet','`sku` Int64, `category` Int64, `price` Int64, `name` String');

SELECT count() AS n FROM synerise_raw.product_properties;

CREATE TABLE synerise_raw.product_buy (`client_id` Int64, `timestamp` String, `sku` Int64) ENGINE=MergeTree ORDER BY (`client_id`, `timestamp`, `sku`);

INSERT INTO synerise_raw.product_buy (`client_id`, `timestamp`, `sku`) SELECT `client_id`, `timestamp`, `sku` FROM file('synerise/e90b8fde/product_buy.parquet','Parquet','`client_id` Int64, `timestamp` String, `sku` Int64');

SELECT count() AS n FROM synerise_raw.product_buy;

CREATE TABLE synerise_raw.remove_from_cart (`client_id` Int64, `timestamp` String, `sku` Int64) ENGINE=MergeTree ORDER BY (`client_id`, `timestamp`, `sku`);

INSERT INTO synerise_raw.remove_from_cart (`client_id`, `timestamp`, `sku`) SELECT `client_id`, `timestamp`, `sku` FROM file('synerise/e90b8fde/remove_from_cart.parquet','Parquet','`client_id` Int64, `timestamp` String, `sku` Int64');

SELECT count() AS n FROM synerise_raw.remove_from_cart;

CREATE TABLE synerise_raw.add_to_cart (`client_id` Int64, `timestamp` String, `sku` Int64) ENGINE=MergeTree ORDER BY (`client_id`, `timestamp`, `sku`);

INSERT INTO synerise_raw.add_to_cart (`client_id`, `timestamp`, `sku`) SELECT `client_id`, `timestamp`, `sku` FROM file('synerise/e90b8fde/add_to_cart.parquet','Parquet','`client_id` Int64, `timestamp` String, `sku` Int64');

SELECT count() AS n FROM synerise_raw.add_to_cart;

CREATE TABLE synerise_raw.search_query (`client_id` Int64, `timestamp` String, `query` String) ENGINE=MergeTree ORDER BY (`client_id`, `timestamp`);

INSERT INTO synerise_raw.search_query (`client_id`, `timestamp`, `query`) SELECT `client_id`, `timestamp`, `query` FROM file('synerise/e90b8fde/search_query.parquet','Parquet','`client_id` Int64, `timestamp` String, `query` String');

SELECT count() AS n FROM synerise_raw.search_query;

CREATE TABLE synerise_raw.page_visit (`client_id` Int64, `timestamp` String, `url` Int64) ENGINE=MergeTree ORDER BY (`client_id`, `timestamp`, `url`);

INSERT INTO synerise_raw.page_visit (`client_id`, `timestamp`, `url`) SELECT `client_id`, `timestamp`, `url` FROM file('synerise/e90b8fde/page_visit.parquet','Parquet','`client_id` Int64, `timestamp` String, `url` Int64');

SELECT count() AS n FROM synerise_raw.page_visit;
