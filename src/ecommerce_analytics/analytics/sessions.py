"""Shared session aggregation and strict chronological funnel definitions."""

import duckdb


def prepare_sessions(con: duckdb.DuckDBPyConnection, composite: bool) -> None:
    """Build session summaries using existence of strictly later stage events."""
    key = (
        "struct_pack(user_id := user_id, user_session := user_session)"
        if composite
        else "user_session"
    )
    con.execute(f"""
        CREATE OR REPLACE TEMP TABLE keyed AS
        SELECT user_id, user_session, product_id, event_type, ts,
            {key} AS session_key
        FROM current_events WHERE user_session IS NOT NULL
    """)
    con.execute("""
        CREATE OR REPLACE TEMP TABLE sessions AS
        SELECT session_key, any_value(user_session) AS user_session,
            any_value(user_id) AS user_id,
            count(*) AS events, count(DISTINCT product_id) AS products,
            count(DISTINCT user_id) AS users,
            min(ts) AS start_time, max(ts) AS end_time,
            count(DISTINCT cast(ts AS DATE)) AS calendar_days,
            count(*) FILTER (WHERE ts IS NULL) AS missing_times,
            count(*) FILTER (WHERE event_type = 'purchase') AS purchase_events,
            coalesce(bool_or(event_type = 'view'), false) AS has_view,
            coalesce(bool_or(event_type = 'cart'), false) AS has_cart,
            coalesce(bool_or(event_type = 'purchase'), false) AS has_purchase,
            coalesce(bool_or(event_type = 'remove_from_cart'), false) AS has_remove,
            min(ts) FILTER (WHERE event_type = 'view') AS first_view,
            min(ts) FILTER (WHERE event_type = 'cart') AS first_cart,
            min(ts) FILTER (WHERE event_type = 'purchase') AS first_purchase,
            max(ts) FILTER (WHERE event_type = 'purchase') AS last_purchase
        FROM keyed GROUP BY session_key
    """)
    # Earliest qualifying cart suffices: any later purchase completes the funnel.
    con.execute("""
        CREATE OR REPLACE TEMP TABLE stage_carts AS
        SELECT s.session_key,
            min(e.ts) FILTER (WHERE e.ts > s.first_view) AS strict_cart,
            min(e.ts) FILTER (WHERE e.ts >= s.first_view) AS relaxed_cart
        FROM sessions s LEFT JOIN keyed e
          ON s.session_key = e.session_key AND e.event_type = 'cart'
        GROUP BY s.session_key
    """)
    con.execute("""
        CREATE OR REPLACE TEMP TABLE funnel_sessions AS
        SELECT s.*, c.strict_cart, c.relaxed_cart,
            coalesce(s.last_purchase > c.strict_cart, false) AS strict_complete,
            coalesce(s.last_purchase >= c.relaxed_cart, false) AS relaxed_complete
        FROM sessions s JOIN stage_carts c USING (session_key)
    """)
