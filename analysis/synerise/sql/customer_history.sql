SELECT count(*) AS customers,count_if(days>1) AS multi_day_customers,
  count_if(months>1) AS multi_month_customers,
  count_if(buys>0) AS purchasing_customers,count_if(buy_days>1) AS multi_purchase_day_customers,
  median(n) AS median_events,quantile_cont(n,0.9) AS p90_events,max(n) AS maximum_events,
  median(days) AS median_active_days,quantile_cont(days,0.9) AS p90_active_days,
  median(epoch(last_ts-first_ts)/86400) AS median_span_days,
  quantile_cont(epoch(last_ts-first_ts)/86400,0.9) AS p90_span_days,
  median(epoch((SELECT max(ts) FROM events)-last_ts)/86400) AS median_last_activity_recency_days
FROM customer_activity;
