{% test nullable_rate_between_zero_and_one(model, column_name) %}

SELECT
    {{ column_name }}
FROM {{ model }}
WHERE {{ column_name }} IS NOT NULL
  AND (
      {{ column_name }} < 0
      OR {{ column_name }} > 1
      OR isNaN({{ column_name }})
  )

{% endtest %}