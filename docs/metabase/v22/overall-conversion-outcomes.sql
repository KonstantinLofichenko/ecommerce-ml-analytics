-- Four mutually exclusive outcomes in the SAME seven-day-eligible customer cohort.
-- This is not the old all-converter distribution (>7 days is included in non-conversion).
SELECT 'Overall first-cart customers' AS cohort,
    tupleElement(outcome_tuple,1) AS outcome_order,
    tupleElement(outcome_tuple,2) AS outcome,
    tupleElement(outcome_tuple,3) AS customers,
    eligible_customers_7d,
    toFloat64(customers)/nullIf(eligible_customers_7d,0) AS outcome_share
FROM (
    SELECT eligible_customers_7d,
        arrayJoin([
            tuple(1,'Converted within 1 hour',toInt64(converted_1h)),
            tuple(2,'Converted >1–24 hours',toInt64(converted_24h)-toInt64(converted_1h)),
            tuple(3,'Converted >24 hours–7 days',toInt64(converted_7d)-toInt64(converted_24h)),
            tuple(4,'Not converted within 7 days',toInt64(eligible_customers_7d)-toInt64(converted_7d))
        ]) AS outcome_tuple
    FROM synerise_analytics.fct_synerise_time_to_conversion
    WHERE metric_scope='customer'
)
ORDER BY outcome_order
