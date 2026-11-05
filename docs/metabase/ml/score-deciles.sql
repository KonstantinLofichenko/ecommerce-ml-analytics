-- Deterministic display-only deciles for one exact published experiment/model/split.
-- Highest scores are decile 1; client_id breaks ties. Unlike saved tie-expected lift,
-- an arbitrary subset of equal scores may fall into the first decile.
WITH ranked AS (
    SELECT client_id,
           actual_target,
           ntile(10) OVER (ORDER BY prediction_probability DESC, client_id ASC) AS score_decile
      FROM synerise_analytics.ml_customer_predictions
     WHERE export_id = 'c498f2518f8708db6ee32c0802b36619a3a44b1b39ba325b4fe5b572422333e7'
       AND experiment_id = {{experiment}}
       AND model_name = {{model}}
       AND dataset_split = {{split}}
)
SELECT score_decile,
       count() AS customers,
       avg(actual_target) AS actual_repeat_purchase_rate
  FROM ranked
 GROUP BY score_decile
 ORDER BY score_decile;
