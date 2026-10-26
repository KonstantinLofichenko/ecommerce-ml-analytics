WITH presence AS (
  SELECT page,search,cart,buys>0 AS buy FROM customer_activity
)
SELECT count(*) AS customers,count_if(page) AS page,
  count_if(page AND cart) AS page_cart,count_if(page AND cart AND buy) AS page_cart_buy,
  count_if(page AND search) AS page_search,
  count_if(page AND search AND cart) AS page_search_cart,
  count_if(page AND search AND cart AND buy) AS page_search_cart_buy,
  count_if(buy AND NOT search) AS purchasers_without_search,
  count_if(buy AND NOT cart) AS purchasers_without_cart FROM presence;
