"""The report queries. Plain strings with :named parameters (run through sqlalchemy.text), no imports.

Definitions used everywhere, so numbers on different reports agree:
- A *sale* is an order with `paid_at` set that was not cancelled. It counts on the day it was paid (store time).
- Refunds count on the day the refund was made, and are subtracted from sales; cancelled orders count as if they never happened.
- Revenue figures include shipping and sales tax unless a column says otherwise ("merchandise" = items after discounts).
- A *customer* is an email address with at least one sale.
- Traffic only covers visitors who accepted analytics (orders and revenue are complete either way).
Parameters: :start and :end are UTC bounds [start, end), :tz is the store's time zone, :gran is day, week or month.
"""

PAID = "o.paid_at >= :start AND o.paid_at < :end AND o.status <> 'cancelled'"
BUCKET = "date_trunc(:gran, ({col} AT TIME ZONE :tz))::date"


def bucket(col: str) -> str:
    return BUCKET.format(col=col)


# ------------------------------------------------------------------------------------------------ sales
SALES_KPIS = f"""
SELECT count(*)::int AS orders,
       COALESCE(sum(o.grand_total), 0) AS gross,
       COALESCE(sum(o.subtotal), 0) AS items_subtotal,
       COALESCE(sum(o.discount_total), 0) AS discounts,
       COALESCE(sum(o.shipping_total), 0) AS shipping,
       COALESCE(sum(o.tax_total), 0) AS tax,
       count(*) FILTER (WHERE o.discount_total > 0 OR o.coupon_code IS NOT NULL)::int AS discounted_orders,
       count(DISTINCT lower(o.email))::int AS customers
FROM orders o
WHERE {PAID}
"""

REFUNDS = """
SELECT COALESCE(sum(p.amount), 0) AS refunds, count(*)::int AS refund_count
FROM payments p JOIN orders o ON o.id = p.order_id
WHERE p.kind = 'refund' AND p.status = 'succeeded' AND p.created_at >= :start AND p.created_at < :end AND o.status <> 'cancelled'
"""

ITEM_KPIS = f"""
SELECT COALESCE(sum(oi.quantity), 0)::int AS units,
       COALESCE(sum(oi.refunded_quantity), 0)::int AS units_refunded,
       COALESCE(sum(oi.unit_price * oi.quantity - oi.discount_total), 0) AS merchandise,
       COALESCE(sum(oi.unit_price * oi.quantity - oi.discount_total - oi.unit_cost * oi.quantity) FILTER (WHERE oi.unit_cost IS NOT NULL), 0) AS profit,
       COALESCE(sum(oi.unit_price * oi.quantity - oi.discount_total) FILTER (WHERE oi.unit_cost IS NOT NULL), 0) AS costed_merchandise,
       count(*)::int AS lines,
       count(*) FILTER (WHERE oi.unit_cost IS NULL)::int AS lines_without_cost,
       COALESCE(sum((oi.list_price - oi.unit_price) * oi.quantity) FILTER (WHERE oi.list_price IS NOT NULL AND oi.list_price > oi.unit_price), 0) AS sale_savings
FROM order_items oi JOIN orders o ON o.id = oi.order_id
WHERE {PAID}
"""

SALES_SERIES = f"""
SELECT {bucket('o.paid_at')} AS bucket, count(*)::int AS orders, COALESCE(sum(o.grand_total), 0) AS gross
FROM orders o WHERE {PAID} GROUP BY 1 ORDER BY 1
"""

REFUND_SERIES = f"""
SELECT {bucket('p.created_at')} AS bucket, COALESCE(sum(p.amount), 0) AS refunds
FROM payments p JOIN orders o ON o.id = p.order_id
WHERE p.kind = 'refund' AND p.status = 'succeeded' AND p.created_at >= :start AND p.created_at < :end AND o.status <> 'cancelled'
GROUP BY 1 ORDER BY 1
"""

SALES_BY_CATEGORY = f"""
SELECT COALESCE(c.id, 0) AS category_id, COALESCE(c.name, 'Uncategorized') AS category,
       COALESCE(sum(oi.quantity), 0)::int AS units,
       COALESCE(sum(oi.unit_price * oi.quantity - oi.discount_total), 0) AS merchandise,
       count(DISTINCT oi.order_id)::int AS orders
FROM order_items oi
JOIN orders o ON o.id = oi.order_id
LEFT JOIN products p ON p.id = oi.product_id
LEFT JOIN products root ON root.id = p.parent_id
LEFT JOIN categories c ON c.id = COALESCE(p.category_id, root.category_id)
WHERE {PAID}
GROUP BY 1, 2 ORDER BY merchandise DESC LIMIT 20
"""

SALES_BY_PAYMENT = f"""
SELECT COALESCE(o.payment_provider, 'unknown') AS method, count(*)::int AS orders, COALESCE(sum(o.grand_total), 0) AS gross
FROM orders o WHERE {PAID} GROUP BY 1 ORDER BY gross DESC
"""

SALES_BY_REGION = f"""
SELECT COALESCE(o.shipping_address->>'country', '?') AS country, COALESCE(o.shipping_address->>'region', '?') AS region,
       count(*)::int AS orders, COALESCE(sum(o.grand_total), 0) AS gross
FROM orders o WHERE {PAID} GROUP BY 1, 2 ORDER BY gross DESC LIMIT 25
"""

SALES_HEATMAP = f"""
SELECT extract(dow FROM (o.paid_at AT TIME ZONE :tz))::int AS dow, extract(hour FROM (o.paid_at AT TIME ZONE :tz))::int AS hour, count(*)::int AS orders
FROM orders o WHERE {PAID} GROUP BY 1, 2
"""

ORDER_SIZES = f"""
SELECT CASE WHEN o.grand_total < 50 THEN 1 WHEN o.grand_total < 100 THEN 2 WHEN o.grand_total < 200 THEN 3 WHEN o.grand_total < 300 THEN 4 ELSE 5 END AS band,
       count(*)::int AS orders, COALESCE(sum(o.grand_total), 0) AS gross
FROM orders o WHERE {PAID} GROUP BY 1 ORDER BY 1
"""

DISCOUNT_SPLIT = f"""
SELECT (o.coupon_code IS NOT NULL OR o.discount_total > 0) AS discounted, count(*)::int AS orders,
       COALESCE(sum(o.grand_total), 0) AS gross, COALESCE(avg(o.grand_total), 0) AS aov
FROM orders o WHERE {PAID} GROUP BY 1
"""

NEAR_FREE_SHIPPING = f"""
SELECT count(*)::int AS orders,
       count(*) FILTER (WHERE o.shipping_total > 0 AND (o.subtotal - o.discount_total) >= CAST(:threshold AS numeric) * 0.7
                          AND (o.subtotal - o.discount_total) < CAST(:threshold AS numeric))::int AS near
FROM orders o WHERE {PAID}
"""

FULFILLMENT = f"""
SELECT count(*) FILTER (WHERE o.shipped_at IS NOT NULL)::int AS shipped,
       COALESCE(avg(extract(epoch FROM (o.shipped_at - o.paid_at)) / 3600) FILTER (WHERE o.shipped_at IS NOT NULL), 0) AS hours_to_ship,
       COALESCE(avg(extract(epoch FROM (o.delivered_at - o.shipped_at)) / 86400) FILTER (WHERE o.delivered_at IS NOT NULL), 0) AS days_in_transit
FROM orders o WHERE {PAID}
"""

UNSHIPPED = """
SELECT count(*)::int FROM orders
WHERE paid_at IS NOT NULL AND status IN ('paid', 'processing') AND shipped_at IS NULL AND paid_at < now() - interval '2 days'
"""

TO_SHIP = """
SELECT count(*)::int FROM orders WHERE paid_at IS NOT NULL AND status IN ('paid', 'processing') AND shipped_at IS NULL
"""

PAYMENTS_WAITING = """
SELECT count(*)::int AS n, COALESCE(sum(grand_total), 0) AS value FROM orders WHERE status = 'pending' AND payment_status = 'unpaid'
"""

FIRST_ORDERS = """
WITH paid AS (
    SELECT lower(email) AS email, paid_at FROM orders WHERE paid_at IS NOT NULL AND status <> 'cancelled'
), firsts AS (SELECT email, min(paid_at) AS first_at FROM paid GROUP BY 1)
SELECT count(DISTINCT p.email) FILTER (WHERE f.first_at >= :start AND f.first_at < :end)::int AS new_customers,
       count(DISTINCT p.email) FILTER (WHERE f.first_at < :start)::int AS returning_customers
FROM paid p JOIN firsts f ON f.email = p.email
WHERE p.paid_at >= :start AND p.paid_at < :end
"""

NEW_VS_RETURNING_SERIES = f"""
WITH paid AS (
    SELECT lower(email) AS email, paid_at FROM orders WHERE paid_at IS NOT NULL AND status <> 'cancelled'
), firsts AS (SELECT email, min(paid_at) AS first_at FROM paid GROUP BY 1)
SELECT {bucket('p.paid_at')} AS bucket,
       count(*) FILTER (WHERE p.paid_at = f.first_at)::int AS new_orders,
       count(*) FILTER (WHERE p.paid_at > f.first_at)::int AS returning_orders
FROM paid p JOIN firsts f ON f.email = p.email
WHERE p.paid_at >= :start AND p.paid_at < :end GROUP BY 1 ORDER BY 1
"""

# ------------------------------------------------------------------------------------------------ products
PRODUCT_TABLE = f"""
WITH sold AS (
    SELECT COALESCE(p.parent_id, p.id) AS pid, sum(oi.quantity)::int AS units,
           sum(oi.unit_price * oi.quantity - oi.discount_total) AS merchandise,
           sum(oi.unit_price * oi.quantity - oi.discount_total - oi.unit_cost * oi.quantity) FILTER (WHERE oi.unit_cost IS NOT NULL) AS profit,
           count(DISTINCT oi.order_id)::int AS orders,
           sum(oi.refunded_quantity)::int AS returned
    FROM order_items oi JOIN orders o ON o.id = oi.order_id JOIN products p ON p.id = oi.product_id
    WHERE {PAID} GROUP BY 1
), bought AS (
    SELECT COALESCE(p.parent_id, p.id) AS pid, count(DISTINCT o.session_id)::int AS sessions
    FROM order_items oi JOIN orders o ON o.id = oi.order_id JOIN products p ON p.id = oi.product_id
    WHERE {PAID} AND o.session_id IS NOT NULL GROUP BY 1
), seen AS (
    SELECT e.product_id AS pid,
           count(*) FILTER (WHERE e.type = 'product_view')::int AS views,
           count(DISTINCT e.session_id) FILTER (WHERE e.type = 'product_view')::int AS viewers,
           count(DISTINCT e.session_id) FILTER (WHERE e.type = 'add_to_cart')::int AS carted,
           count(*) FILTER (WHERE e.type = 'wishlist_add')::int AS wishlist_adds
    FROM analytics_events e
    WHERE e.created_at >= :start AND e.created_at < :end AND e.product_id IS NOT NULL GROUP BY 1
), stock AS (
    SELECT COALESCE(p.parent_id, p.id) AS pid, sum(p.stock_quantity)::int AS units_in_stock, bool_or(p.stock_quantity IS NOT NULL) AS tracked
    FROM products p WHERE p.status = 'published' AND NOT EXISTS (SELECT 1 FROM products c WHERE c.parent_id = p.id) GROUP BY 1
)
SELECT p.id, p.title, p.slug, p.sku, p.stock_status::text AS stock_status, p.rating_avg, p.rating_count, p.base_price,
       COALESCE(sold.units, 0) AS units, COALESCE(sold.merchandise, 0) AS merchandise, sold.profit AS profit, COALESCE(sold.orders, 0) AS orders,
       COALESCE(sold.returned, 0) AS returned, COALESCE(bought.sessions, 0) AS bought_sessions,
       COALESCE(seen.views, 0) AS views, COALESCE(seen.viewers, 0) AS viewers, COALESCE(seen.carted, 0) AS carted,
       COALESCE(seen.wishlist_adds, 0) AS wishlist_adds,
       CASE WHEN stock.tracked THEN stock.units_in_stock END AS stock
FROM products p
LEFT JOIN sold ON sold.pid = p.id LEFT JOIN bought ON bought.pid = p.id LEFT JOIN seen ON seen.pid = p.id LEFT JOIN stock ON stock.pid = p.id
WHERE p.parent_id IS NULL AND p.status = 'published'
ORDER BY COALESCE(sold.merchandise, 0) DESC, COALESCE(seen.views, 0) DESC, p.id
"""

BOUGHT_TOGETHER = """
WITH lines AS (
    SELECT DISTINCT oi.order_id, COALESCE(p.parent_id, p.id) AS pid
    FROM order_items oi JOIN orders o ON o.id = oi.order_id JOIN products p ON p.id = oi.product_id
    WHERE o.paid_at IS NOT NULL AND o.status <> 'cancelled' AND o.paid_at >= now() - interval '365 days'
)
SELECT a.pid AS first_id, b.pid AS second_id, pa.title AS first_title, pb.title AS second_title, count(*)::int AS orders
FROM lines a JOIN lines b ON a.order_id = b.order_id AND a.pid < b.pid
JOIN products pa ON pa.id = a.pid JOIN products pb ON pb.id = b.pid
GROUP BY 1, 2, 3, 4 HAVING count(*) >= 2 ORDER BY orders DESC, first_id, second_id LIMIT 10
"""

REVIEW_SUMMARY = """
SELECT count(*) FILTER (WHERE status = 'approved')::int AS approved,
       count(*) FILTER (WHERE status = 'pending')::int AS pending,
       count(*) FILTER (WHERE status = 'rejected')::int AS rejected,
       COALESCE(avg(rating) FILTER (WHERE status = 'approved'), 0) AS average,
       count(*) FILTER (WHERE status = 'approved' AND reply IS NOT NULL)::int AS answered,
       count(*) FILTER (WHERE status = 'approved' AND rating <= 2)::int AS critical,
       count(*) FILTER (WHERE status = 'approved' AND rating <= 2 AND reply IS NULL)::int AS critical_unanswered,
       count(*) FILTER (WHERE status = 'approved' AND created_at >= :start AND created_at < :end)::int AS new_in_range
FROM reviews
"""

REVIEW_DISTRIBUTION = """
SELECT rating, count(*)::int AS n FROM reviews WHERE status = 'approved' GROUP BY 1 ORDER BY 1
"""

LOWEST_RATED = """
SELECT id, title, slug, rating_avg, rating_count FROM products
WHERE parent_id IS NULL AND status = 'published' AND rating_count >= 2 ORDER BY rating_avg ASC, rating_count DESC, id LIMIT 5
"""

REVIEW_REQUESTS = f"""
SELECT count(*) FILTER (WHERE o.review_requested_at IS NOT NULL)::int AS requested,
       count(*)::int AS orders,
       count(*) FILTER (WHERE EXISTS (SELECT 1 FROM reviews r WHERE r.order_id = o.id))::int AS reviewed
FROM orders o WHERE {PAID}
"""

# ------------------------------------------------------------------------------------------------ traffic
SESSION_RANGE = "s.started_at >= :start AND s.started_at < :end"

TRAFFIC_KPIS = f"""
SELECT count(*)::int AS sessions, count(DISTINCT s.visitor_id)::int AS visitors,
       count(*) FILTER (WHERE s.is_new_visitor)::int AS new_sessions,
       COALESCE(sum(s.page_views), 0)::int AS page_views,
       count(*) FILTER (WHERE s.page_views <= 1)::int AS bounced,
       COALESCE(avg(extract(epoch FROM (s.last_seen_at - s.started_at))) FILTER (WHERE s.page_views > 1), 0) AS avg_seconds,
       count(*) FILTER (WHERE EXISTS (SELECT 1 FROM orders o WHERE o.session_id = s.id AND o.status <> 'cancelled'))::int AS converted
FROM analytics_sessions s WHERE {SESSION_RANGE}
"""

TRAFFIC_SERIES = f"""
SELECT {bucket('s.started_at')} AS bucket, count(*)::int AS sessions, count(DISTINCT s.visitor_id)::int AS visitors
FROM analytics_sessions s WHERE {SESSION_RANGE} GROUP BY 1 ORDER BY 1
"""

TRAFFIC_BY_CHANNEL = f"""
WITH visits AS (
    SELECT s.channel, count(*)::int AS sessions, count(DISTINCT s.visitor_id)::int AS visitors,
           count(*) FILTER (WHERE s.page_views <= 1)::int AS bounced
    FROM analytics_sessions s WHERE {SESSION_RANGE} GROUP BY 1
), sales AS (
    SELECT COALESCE(o.channel, 'unknown') AS channel, count(*)::int AS orders, sum(o.grand_total - o.refunded_total) AS revenue
    FROM orders o WHERE {PAID} AND o.channel IS NOT NULL GROUP BY 1
)
SELECT COALESCE(v.channel, sa.channel) AS channel, COALESCE(v.sessions, 0) AS sessions, COALESCE(v.visitors, 0) AS visitors,
       COALESCE(v.bounced, 0) AS bounced, COALESCE(sa.orders, 0) AS orders, COALESCE(sa.revenue, 0) AS revenue
FROM visits v FULL JOIN sales sa ON sa.channel = v.channel ORDER BY sessions DESC, orders DESC
"""

TRAFFIC_DIMENSION = """
SELECT COALESCE({col}, '(none)') AS label, count(*)::int AS sessions, count(*) FILTER (WHERE s.page_views <= 1)::int AS bounced
FROM analytics_sessions s WHERE s.started_at >= :start AND s.started_at < :end GROUP BY 1 ORDER BY sessions DESC, label LIMIT {limit}
"""

LANDING_PAGES = f"""
SELECT COALESCE(s.landing_path, '(unknown)') AS path, count(*)::int AS sessions, count(*) FILTER (WHERE s.page_views <= 1)::int AS bounced,
       count(*) FILTER (WHERE EXISTS (SELECT 1 FROM orders o WHERE o.session_id = s.id AND o.status <> 'cancelled'))::int AS converted
FROM analytics_sessions s WHERE {SESSION_RANGE} GROUP BY 1 ORDER BY sessions DESC, path LIMIT 15
"""

REFERRERS = f"""
SELECT s.referrer_host AS host, s.channel, count(*)::int AS sessions
FROM analytics_sessions s WHERE {SESSION_RANGE} AND s.referrer_host IS NOT NULL GROUP BY 1, 2 ORDER BY sessions DESC, host LIMIT 15
"""

CAMPAIGNS = f"""
SELECT s.utm_campaign AS campaign, COALESCE(s.utm_source, '') AS source, COALESCE(s.utm_medium, '') AS medium, count(*)::int AS sessions,
       count(*) FILTER (WHERE EXISTS (SELECT 1 FROM orders o WHERE o.session_id = s.id AND o.status <> 'cancelled'))::int AS orders,
       COALESCE((SELECT sum(o.grand_total - o.refunded_total) FROM orders o JOIN analytics_sessions s2 ON s2.id = o.session_id
                 WHERE s2.started_at >= :start AND s2.started_at < :end AND s2.utm_campaign = s.utm_campaign AND o.paid_at IS NOT NULL AND o.status <> 'cancelled'), 0) AS revenue
FROM analytics_sessions s WHERE {SESSION_RANGE} AND s.utm_campaign IS NOT NULL GROUP BY 1, 2, 3 ORDER BY sessions DESC LIMIT 15
"""

CONSENT = """
SELECT COALESCE(sum(accepted), 0)::int AS accepted, COALESCE(sum(declined), 0)::int AS declined
FROM consent_daily WHERE day >= (CAST(:start AS timestamptz) AT TIME ZONE :tz)::date AND day < (CAST(:end AS timestamptz) AT TIME ZONE :tz)::date
"""

LIVE_NOW = """
SELECT count(DISTINCT visitor_id)::int AS visitors FROM analytics_sessions WHERE last_seen_at > now() - interval '30 minutes'
"""

# ------------------------------------------------------------------------------------------------ behaviour
TOP_PAGES = """
SELECT e.path, count(*)::int AS views, count(DISTINCT e.session_id)::int AS sessions
FROM analytics_events e WHERE e.type = 'page_view' AND e.created_at >= :start AND e.created_at < :end AND e.path IS NOT NULL
GROUP BY 1 ORDER BY views DESC, path LIMIT 20
"""

SEARCH_TERMS = """
SELECT e.data->>'q' AS term, count(*)::int AS searches,
       COALESCE(avg(NULLIF(e.data->>'results', '')::numeric), 0) AS avg_results,
       count(*) FILTER (WHERE (e.data->>'results') = '0')::int AS no_results
FROM analytics_events e WHERE e.type = 'search' AND e.created_at >= :start AND e.created_at < :end AND e.data->>'q' IS NOT NULL
GROUP BY 1 ORDER BY searches DESC, term LIMIT 25
"""

EVENT_TOTALS = """
SELECT e.type, count(*)::int AS events, count(DISTINCT e.session_id)::int AS sessions
FROM analytics_events e WHERE e.created_at >= :start AND e.created_at < :end AND e.type <> 'web_vital' GROUP BY 1 ORDER BY events DESC
"""

SESSION_DEPTH = f"""
SELECT CASE WHEN s.page_views <= 1 THEN 1 WHEN s.page_views = 2 THEN 2 WHEN s.page_views <= 5 THEN 3 ELSE 4 END AS band, count(*)::int AS sessions
FROM analytics_sessions s WHERE {SESSION_RANGE} GROUP BY 1 ORDER BY 1
"""

SEARCHERS = f"""
SELECT count(*) FILTER (WHERE EXISTS (SELECT 1 FROM analytics_events e WHERE e.session_id = s.id AND e.type = 'search'))::int AS searched,
       count(*) FILTER (WHERE EXISTS (SELECT 1 FROM analytics_events e WHERE e.session_id = s.id AND e.type = 'search')
                          AND EXISTS (SELECT 1 FROM orders o WHERE o.session_id = s.id AND o.status <> 'cancelled'))::int AS searched_and_ordered,
       count(*) FILTER (WHERE EXISTS (SELECT 1 FROM orders o WHERE o.session_id = s.id AND o.status <> 'cancelled'))::int AS ordered
FROM analytics_sessions s WHERE {SESSION_RANGE}
"""

# ------------------------------------------------------------------------------------------------ funnel
FUNNEL_STEPS = """
count(*)::int AS sessions,
count(*) FILTER (WHERE EXISTS (SELECT 1 FROM analytics_events e WHERE e.session_id = s.id AND e.type = 'product_view'))::int AS viewed,
count(*) FILTER (WHERE EXISTS (SELECT 1 FROM analytics_events e WHERE e.session_id = s.id AND e.type = 'add_to_cart'))::int AS carted,
count(*) FILTER (WHERE EXISTS (SELECT 1 FROM analytics_events e WHERE e.session_id = s.id AND e.type = 'begin_checkout'))::int AS checkout,
count(*) FILTER (WHERE EXISTS (SELECT 1 FROM orders o WHERE o.session_id = s.id AND o.status <> 'cancelled'))::int AS ordered,
count(*) FILTER (WHERE EXISTS (SELECT 1 FROM orders o WHERE o.session_id = s.id AND o.status <> 'cancelled' AND o.paid_at IS NOT NULL))::int AS paid
"""

FUNNEL = f"SELECT {FUNNEL_STEPS} FROM analytics_sessions s WHERE {SESSION_RANGE}"
FUNNEL_BY = "SELECT {col} AS label, " + FUNNEL_STEPS + f" FROM analytics_sessions s WHERE {SESSION_RANGE}" + " GROUP BY 1 ORDER BY sessions DESC"

# ------------------------------------------------------------------------------------------------ customers
CUSTOMER_TOTALS = """
WITH paid AS (
    SELECT lower(email) AS email, grand_total - refunded_total AS net, paid_at FROM orders WHERE paid_at IS NOT NULL AND status NOT IN ('cancelled', 'refunded')
), per AS (SELECT email, count(*) AS orders, sum(net) AS revenue, min(paid_at) AS first_at, max(paid_at) AS last_at FROM paid GROUP BY 1)
SELECT count(*)::int AS customers, count(*) FILTER (WHERE orders >= 2)::int AS repeat_customers,
       COALESCE(avg(revenue), 0) AS avg_lifetime_value, COALESCE(avg(orders), 0) AS avg_orders
FROM per
"""

CUSTOMER_STATS = """
SELECT lower(email) AS email, count(*)::int AS orders, COALESCE(sum(grand_total - refunded_total), 0) AS revenue, max(paid_at) AS last_order_at
FROM orders WHERE paid_at IS NOT NULL AND status NOT IN ('cancelled', 'refunded') GROUP BY 1
"""

SECOND_ORDER_GAP = """
WITH paid AS (
    SELECT lower(email) AS email, paid_at, row_number() OVER (PARTITION BY lower(email) ORDER BY paid_at) AS n
    FROM orders WHERE paid_at IS NOT NULL AND status NOT IN ('cancelled', 'refunded')
)
SELECT COALESCE(percentile_cont(0.5) WITHIN GROUP (ORDER BY extract(epoch FROM (b.paid_at - a.paid_at)) / 86400), 0) AS median_days, count(*)::int AS n
FROM paid a JOIN paid b ON a.email = b.email AND a.n = 1 AND b.n = 2
"""

TOP_CUSTOMERS = """
SELECT lower(email) AS email, (array_agg(customer_name ORDER BY paid_at DESC) FILTER (WHERE customer_name IS NOT NULL))[1] AS name,
       count(*)::int AS orders, sum(grand_total - refunded_total) AS revenue, max(paid_at) AS last_order_at
FROM orders WHERE paid_at IS NOT NULL AND status NOT IN ('cancelled', 'refunded')
GROUP BY 1 ORDER BY revenue DESC, email LIMIT 10
"""

CUSTOMER_GEO = f"""
SELECT COALESCE(o.shipping_address->>'region', '?') AS region, COALESCE(o.shipping_address->>'country', '?') AS country,
       count(DISTINCT lower(o.email))::int AS customers, COALESCE(sum(o.grand_total - o.refunded_total), 0) AS revenue
FROM orders o WHERE {PAID} GROUP BY 1, 2 ORDER BY customers DESC, revenue DESC LIMIT 15
"""

COHORTS = """
WITH paid AS (
    SELECT lower(email) AS email, date_trunc('month', paid_at AT TIME ZONE :tz)::date AS month
    FROM orders WHERE paid_at IS NOT NULL AND status NOT IN ('cancelled', 'refunded')
), firsts AS (SELECT email, min(month) AS cohort FROM paid GROUP BY 1)
SELECT f.cohort, (extract(year FROM age(p.month, f.cohort)) * 12 + extract(month FROM age(p.month, f.cohort)))::int AS months_later,
       count(DISTINCT p.email)::int AS customers
FROM paid p JOIN firsts f ON f.email = p.email
WHERE f.cohort >= (date_trunc('month', (CAST(:end AS timestamptz) AT TIME ZONE :tz)) - interval '11 months')::date
GROUP BY 1, 2 ORDER BY 1, 2
"""

NEWSLETTER = """
SELECT count(*) FILTER (WHERE n.source <> ALL(CAST(:service_only AS text[])) AND n.unsubscribed_at IS NULL)::int AS subscribers,
       count(*) FILTER (WHERE n.source <> ALL(CAST(:service_only AS text[])) AND n.created_at >= :start AND n.created_at < :end)::int AS joined,
       count(*) FILTER (WHERE n.unsubscribed_at >= :start AND n.unsubscribed_at < :end)::int AS left_list
FROM newsletter_subscribers n
"""

NEWSLETTER_BY_SOURCE = """
SELECT n.source, count(*)::int AS subscribers FROM newsletter_subscribers n
WHERE n.source <> ALL(CAST(:service_only AS text[])) AND n.unsubscribed_at IS NULL GROUP BY 1 ORDER BY subscribers DESC
"""

# ------------------------------------------------------------------------------------------------ promotions
SALE_PERFORMANCE = f"""
SELECT s.id, s.name, s.kind, s.value, s.starts_at, s.ends_at, s.is_active,
       COALESCE(sum(oi.quantity), 0)::int AS units, COALESCE(sum(oi.unit_price * oi.quantity), 0) AS revenue,
       COALESCE(sum((oi.list_price - oi.unit_price) * oi.quantity), 0) AS given_away,
       count(DISTINCT oi.order_id)::int AS orders
FROM sales s
LEFT JOIN order_items oi ON oi.sale_id = s.id AND oi.order_id IN (SELECT o.id FROM orders o WHERE {PAID})
GROUP BY s.id ORDER BY s.id DESC LIMIT 20
"""

COUPON_PERFORMANCE = f"""
SELECT r.coupon_id, c.code, c.source, c.kind, count(*)::int AS orders, COALESCE(sum(r.amount), 0) AS discount,
       COALESCE(sum(o.grand_total - o.refunded_total), 0) AS revenue
FROM coupon_redemptions r JOIN coupons c ON c.id = r.coupon_id JOIN orders o ON o.id = r.order_id
WHERE {PAID} GROUP BY 1, 2, 3, 4 ORDER BY orders DESC, discount DESC, code LIMIT 20
"""

COUPON_SOURCES = """
SELECT c.source, count(DISTINCT c.id) FILTER (WHERE c.created_at >= :start AND c.created_at < :end)::int AS issued,
       count(r.id) FILTER (WHERE o.id IS NOT NULL)::int AS redeemed,
       COALESCE(sum(r.amount) FILTER (WHERE o.id IS NOT NULL), 0) AS discount,
       COALESCE(sum(o.grand_total - o.refunded_total), 0) AS revenue
FROM coupons c
LEFT JOIN coupon_redemptions r ON r.coupon_id = c.id
LEFT JOIN orders o ON o.id = r.order_id AND o.paid_at >= :start AND o.paid_at < :end AND o.status <> 'cancelled'
GROUP BY 1 ORDER BY redeemed DESC, issued DESC
"""

CAMPAIGN_PERFORMANCE = """
SELECT cm.id, cm.name, cm.segment, cm.recipients, cm.sent_at,
       count(DISTINCT cp.id)::int AS coupons,
       count(r.id) FILTER (WHERE o.id IS NOT NULL)::int AS redeemed,
       COALESCE(sum(r.amount) FILTER (WHERE o.id IS NOT NULL), 0) AS discount,
       COALESCE(sum(o.grand_total - o.refunded_total) FILTER (WHERE o.id IS NOT NULL), 0) AS revenue
FROM campaigns cm
LEFT JOIN coupons cp ON cp.campaign = 'campaign-' || cm.id
LEFT JOIN coupon_redemptions r ON r.coupon_id = cp.id
LEFT JOIN orders o ON o.id = r.order_id AND o.paid_at IS NOT NULL AND o.status <> 'cancelled'
WHERE cm.status = 'sent' AND cm.sent_at >= :start AND cm.sent_at < :end
GROUP BY cm.id ORDER BY cm.sent_at DESC LIMIT 20
"""

OFFER_PERFORMANCE = f"""
SELECT d->>'type' AS type, d->>'label' AS label, count(DISTINCT o.id)::int AS orders, COALESCE(sum((d->>'amount')::numeric), 0) AS discount
FROM orders o CROSS JOIN LATERAL jsonb_array_elements(o.discounts) AS d
WHERE {PAID} AND d->>'type' IN ('rule', 'free_shipping') AND (d->>'code') IS NULL
GROUP BY 1, 2 ORDER BY orders DESC, label
"""

CART_FUNNEL = """
SELECT count(*)::int AS started,
       count(*) FILTER (WHERE c.converted_order_id IS NOT NULL)::int AS converted,
       count(*) FILTER (WHERE c.converted_order_id IS NULL AND c.last_activity_at <= :active_cutoff)::int AS abandoned,
       COALESCE(sum(c.subtotal) FILTER (WHERE c.converted_order_id IS NULL AND c.last_activity_at <= :active_cutoff), 0) AS abandoned_value,
       count(*) FILTER (WHERE c.checkout_started_at IS NOT NULL)::int AS reached_checkout,
       count(*) FILTER (WHERE c.checkout_started_at IS NOT NULL AND c.converted_order_id IS NOT NULL)::int AS checkout_completed
FROM carts c WHERE c.item_count > 0 AND c.created_at >= :start AND c.created_at < :end
"""

CART_RECOVERY = """
SELECT count(*) FILTER (WHERE c.reminder_count > 0)::int AS carts_reminded,
       COALESCE(sum(c.reminder_count), 0)::int AS reminders_sent,
       count(*) FILTER (WHERE c.reminder_count > 0 AND c.converted_order_id IS NOT NULL AND c.converted_at > c.last_reminder_at)::int AS recovered,
       COALESCE(sum(o.grand_total - o.refunded_total) FILTER (WHERE c.reminder_count > 0 AND c.converted_at > c.last_reminder_at AND o.paid_at IS NOT NULL), 0) AS recovered_revenue
FROM carts c LEFT JOIN orders o ON o.id = c.converted_order_id
WHERE c.created_at >= :start AND c.created_at < :end
"""

# ------------------------------------------------------------------------------------------------ inventory
STOCK_LEVELS = """
SELECT p.id, COALESCE(root.title, p.title) AS title, p.title AS variant, COALESCE(root.slug, p.slug) AS slug, p.sku, p.stock_quantity AS stock,
       p.stock_status::text AS stock_status, p.base_price, p.cost_price,
       COALESCE((SELECT sum(oi.quantity - oi.refunded_quantity) FROM order_items oi JOIN orders o ON o.id = oi.order_id
                 WHERE oi.product_id = p.id AND o.paid_at >= now() - interval '30 days' AND o.status <> 'cancelled'), 0)::int AS sold_30d,
       COALESCE((SELECT sum(oi.quantity - oi.refunded_quantity) FROM order_items oi JOIN orders o ON o.id = oi.order_id
                 WHERE oi.product_id = p.id AND o.paid_at >= now() - interval '90 days' AND o.status <> 'cancelled'), 0)::int AS sold_90d,
       (SELECT count(*) FROM stock_alerts a WHERE a.product_id = p.id AND a.notified_at IS NULL)::int AS waiting
FROM products p LEFT JOIN products root ON root.id = p.parent_id
WHERE p.status = 'published' AND NOT EXISTS (SELECT 1 FROM products c WHERE c.parent_id = p.id)
  AND (root.id IS NULL OR root.status = 'published')
ORDER BY p.id
"""

# ------------------------------------------------------------------------------------------------ catalog health
CATALOG_ROWS = """
SELECT p.id, p.title, p.slug, p.sku, p.description, p.base_price, p.cost_price, p.category_id, p.seo_description,
       jsonb_array_length(COALESCE(p.images, '[]'::jsonb))::int AS images, COALESCE(array_length(p.tags, 1), 0)::int AS tags,
       (SELECT count(*) FROM products c WHERE c.parent_id = p.id)::int AS variants
FROM products p WHERE p.parent_id IS NULL AND p.status = 'published' ORDER BY p.id
"""

# ------------------------------------------------------------------------------------------------ performance
VITALS = """
SELECT e.data->>'name' AS name, count(*)::int AS samples,
       percentile_cont(0.75) WITHIN GROUP (ORDER BY e.value) AS p75, percentile_cont(0.5) WITHIN GROUP (ORDER BY e.value) AS median
FROM analytics_events e WHERE e.type = 'web_vital' AND e.created_at >= :start AND e.created_at < :end AND e.value IS NOT NULL GROUP BY 1 ORDER BY 1
"""

VITALS_BY_DEVICE = """
SELECT s.device, e.data->>'name' AS name, count(*)::int AS samples, percentile_cont(0.75) WITHIN GROUP (ORDER BY e.value) AS p75
FROM analytics_events e JOIN analytics_sessions s ON s.id = e.session_id
WHERE e.type = 'web_vital' AND e.created_at >= :start AND e.created_at < :end AND e.value IS NOT NULL GROUP BY 1, 2 ORDER BY 1, 2
"""

SLOWEST_PAGES = """
SELECT e.path, count(*)::int AS samples, percentile_cont(0.75) WITHIN GROUP (ORDER BY e.value) AS p75
FROM analytics_events e
WHERE e.type = 'web_vital' AND e.data->>'name' = 'LCP' AND e.created_at >= :start AND e.created_at < :end AND e.value IS NOT NULL AND e.path IS NOT NULL
GROUP BY 1 HAVING count(*) >= 3 ORDER BY p75 DESC LIMIT 10
"""

CLIENT_ERRORS = """
SELECT e.data->>'message' AS message, e.path, count(*)::int AS occurrences
FROM analytics_events e WHERE e.type = 'client_error' AND e.created_at >= :start AND e.created_at < :end
GROUP BY 1, 2 ORDER BY occurrences DESC LIMIT 10
"""

# ------------------------------------------------------------------------------------------------ overview extras
RECENT_ORDERS = """
SELECT id, number, email, customer_name, status::text AS status, payment_status, grand_total, placed_at
FROM orders ORDER BY placed_at DESC NULLS LAST, id DESC LIMIT 6
"""

WAITING_REVIEWS = "SELECT count(*)::int FROM reviews WHERE status = 'pending'"
STOCK_WAITLIST = """
SELECT p.id, COALESCE(root.title, p.title) AS title, count(*)::int AS requests
FROM stock_alerts a JOIN products p ON p.id = a.product_id LEFT JOIN products root ON root.id = p.parent_id
WHERE a.notified_at IS NULL AND (p.stock_status = 'out_of_stock' OR p.stock_quantity = 0) GROUP BY 1, 2 ORDER BY requests DESC, title LIMIT 10
"""
