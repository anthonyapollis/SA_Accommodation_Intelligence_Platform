-- ============================================================
-- SA Accommodation Intelligence Platform
-- BigQuery Analytics Query Library
-- Dataset: accommodation_intelligence
-- Author : Anthony Apollis | 2026-06-27
--
-- All queries are structured for:
--   • Partition pruning on DATE columns (event_date, scraped_date)
--   • Clustered column first-look optimisation
--   • POPIA-aware consent filtering where relevant
-- ============================================================


-- ────────────────────────────────────────────────────────────
-- Q1. MARKET OVERVIEW — listings by type and tier
--     Baseline snapshot: what does the SA accommodation market
--     actually look like on LekkeSlaap?
-- ────────────────────────────────────────────────────────────
SELECT
    fl.listing_type,
    fl.price_tier,
    COUNT(*)                                        AS listings,
    ROUND(AVG(fl.price_zar), 0)                     AS avg_price_zar,
    ROUND(MIN(fl.price_zar), 0)                     AS min_price_zar,
    ROUND(MAX(fl.price_zar), 0)                     AS max_price_zar,
    ROUND(APPROX_QUANTILES(fl.price_zar, 4)[OFFSET(2)], 0) AS median_price_zar,
    ROUND(AVG(fl.review_count), 1)                  AS avg_reviews,
    ROUND(AVG(fl.demand_score), 2)                  AS avg_demand_score
FROM `accommodation_intelligence.fact_listings`   AS fl
WHERE scraped_date = '2026-06-27'
GROUP BY listing_type, price_tier
ORDER BY listings DESC, avg_price_zar DESC;


-- ────────────────────────────────────────────────────────────
-- Q2. REGION COMPETITIVENESS MATRIX
--     Which regions have the highest average price AND demand?
--     Quadrant-ready: plot avg_price_zar vs avg_demand_score
-- ────────────────────────────────────────────────────────────
SELECT
    dr.region,
    dr.country,
    COUNT(fl.property_id)                           AS total_listings,
    ROUND(AVG(fl.price_zar), 0)                     AS avg_price_zar,
    ROUND(AVG(fl.demand_score), 2)                  AS avg_demand_score,
    ROUND(AVG(fl.review_count), 1)                  AS avg_reviews,
    COUNTIF(fl.price_tier = 'Luxury')               AS luxury_count,
    COUNTIF(fl.price_tier = 'Budget')               AS budget_count,
    ROUND(
        COUNTIF(fl.price_tier IN ('Premium','Luxury')) * 100.0
        / NULLIF(COUNT(*), 0), 1
    )                                               AS premium_plus_pct
FROM `accommodation_intelligence.fact_listings`   AS fl
JOIN `accommodation_intelligence.dim_region`      AS dr ON fl.region_id = dr.region_id
WHERE scraped_date = '2026-06-27'
  AND fl.price_zar IS NOT NULL
GROUP BY dr.region, dr.country
HAVING total_listings >= 5
ORDER BY avg_demand_score DESC, avg_price_zar DESC;


-- ────────────────────────────────────────────────────────────
-- Q3. FLASH DEAL / PROMOTIONAL IMPACT ANALYSIS
--     Do listings with active flash deals have
--     lower actual prices or just inflated review counts?
-- ────────────────────────────────────────────────────────────
SELECT
    fl.has_promo_flag,
    fl.listing_type,
    COUNT(*)                                        AS listings,
    ROUND(AVG(fl.price_zar), 0)                     AS avg_price_zar,
    ROUND(AVG(fl.discount_pct), 1)                  AS avg_discount_pct,
    ROUND(AVG(fl.review_count), 1)                  AS avg_reviews,
    ROUND(AVG(fl.demand_score), 2)                  AS avg_demand_score,
    ROUND(
        AVG(CASE WHEN fl.has_promo_flag THEN fl.price_zar END)
        - AVG(CASE WHEN NOT fl.has_promo_flag THEN fl.price_zar END), 0
    )                                               AS promo_vs_standard_price_diff
FROM `accommodation_intelligence.fact_listings` AS fl
WHERE scraped_date = '2026-06-27'
GROUP BY fl.has_promo_flag, fl.listing_type
ORDER BY fl.has_promo_flag DESC, avg_price_zar DESC;


-- ────────────────────────────────────────────────────────────
-- Q4. GA4 SESSION METRICS — daily trend (Jan–Jun 2025)
--     Mimics GA4 "Overview" report; shows engagement quality
-- ────────────────────────────────────────────────────────────
SELECT
    event_date,
    COUNT(DISTINCT session_id)                      AS sessions,
    COUNT(DISTINCT user_pseudo_id)                  AS users,
    COUNTIF(session_engaged = 1)                    AS engaged_sessions,
    ROUND(
        COUNTIF(session_engaged = 1) * 100.0
        / NULLIF(COUNT(*), 0), 1
    )                                               AS engagement_rate_pct,
    COUNTIF(bounced = 1)                            AS bounced_sessions,
    ROUND(AVG(engagement_secs), 1)                  AS avg_engagement_secs,
    ROUND(
        COUNTIF(bounced = 1) * 100.0
        / NULLIF(COUNT(*), 0), 1
    )                                               AS bounce_rate_pct
FROM `accommodation_intelligence.fact_web_sessions`
WHERE event_date BETWEEN '2025-01-01' AND '2025-06-30'
GROUP BY event_date
ORDER BY event_date;


-- ────────────────────────────────────────────────────────────
-- Q5. BOOKING CONVERSION FUNNEL
--     listing_view → search_nearby → contact_host
--        → booking_initiated → booking_confirmed
--     Equivalent to GA4 ecommerce funnel exploration
-- ────────────────────────────────────────────────────────────
WITH funnel_base AS (
    SELECT
        session_id,
        MAX(CASE WHEN event_name = 'listing_view'       THEN 1 ELSE 0 END) AS s1_view,
        MAX(CASE WHEN event_name = 'search_nearby'      THEN 1 ELSE 0 END) AS s2_search,
        MAX(CASE WHEN event_name = 'contact_host'       THEN 1 ELSE 0 END) AS s3_contact,
        MAX(CASE WHEN event_name = 'booking_initiated'  THEN 1 ELSE 0 END) AS s4_initiated,
        MAX(CASE WHEN event_name = 'booking_confirmed'  THEN 1 ELSE 0 END) AS s5_confirmed
    FROM `accommodation_intelligence.fact_booking_events`
    WHERE event_date BETWEEN '2025-01-01' AND '2025-06-30'
    GROUP BY session_id
)
SELECT
    step_no,
    event_label,
    users,
    LAG(users) OVER (ORDER BY step_no)             AS prev_step_users,
    ROUND(users * 100.0
        / FIRST_VALUE(users) OVER (ORDER BY step_no), 1) AS pct_of_top,
    ROUND(
        100.0 - users * 100.0
        / NULLIF(LAG(users) OVER (ORDER BY step_no), 0), 1
    )                                               AS drop_off_pct
FROM (
    SELECT 1 AS step_no, 'Listing View'      AS event_label, COUNTIF(s1_view=1)      AS users FROM funnel_base
    UNION ALL
    SELECT 2, 'Search Nearby',    COUNTIF(s2_search=1)    FROM funnel_base
    UNION ALL
    SELECT 3, 'Contact Host',     COUNTIF(s3_contact=1)   FROM funnel_base
    UNION ALL
    SELECT 4, 'Booking Initiated',COUNTIF(s4_initiated=1) FROM funnel_base
    UNION ALL
    SELECT 5, 'Booking Confirmed',COUNTIF(s5_confirmed=1) FROM funnel_base
)
ORDER BY step_no;


-- ────────────────────────────────────────────────────────────
-- Q6. TRAFFIC SOURCE ATTRIBUTION — bookings + revenue proxy
--     Which channel drives the most confirmed bookings?
--     revenue_proxy = average price × confirmed bookings
-- ────────────────────────────────────────────────────────────
SELECT
    be.traffic_source,
    be.traffic_medium,
    COUNT(DISTINCT be.session_id)                   AS sessions,
    COUNTIF(be.event_name = 'booking_confirmed')    AS confirmed_bookings,
    ROUND(
        COUNTIF(be.event_name = 'booking_confirmed') * 100.0
        / NULLIF(COUNT(DISTINCT be.session_id), 0), 2
    )                                               AS booking_conv_rate_pct,
    ROUND(
        SUM(CASE WHEN be.event_name = 'booking_confirmed' THEN be.price_zar ELSE 0 END), 2
    )                                               AS revenue_proxy_zar,
    ROUND(
        AVG(CASE WHEN be.event_name = 'booking_confirmed' THEN be.price_zar END), 0
    )                                               AS avg_booking_value_zar
FROM `accommodation_intelligence.fact_booking_events` AS be
WHERE event_date BETWEEN '2025-01-01' AND '2025-06-30'
GROUP BY traffic_source, traffic_medium
ORDER BY confirmed_bookings DESC;


-- ────────────────────────────────────────────────────────────
-- Q7. SA PROVINCE BOOKING ANALYSIS
--     Where in South Africa are bookings actually confirmed?
--     Essential for geo-targeted marketing decisions
-- ────────────────────────────────────────────────────────────
SELECT
    be.province,
    COUNT(DISTINCT be.session_id)                   AS sessions,
    COUNTIF(be.event_name = 'booking_confirmed')    AS confirmed_bookings,
    ROUND(
        COUNTIF(be.event_name = 'booking_confirmed') * 100.0
        / NULLIF(COUNT(DISTINCT be.session_id), 0), 2
    )                                               AS booking_conv_rate_pct,
    ROUND(
        AVG(CASE WHEN be.event_name = 'booking_confirmed' THEN be.price_zar END), 0
    )                                               AS avg_booking_value_zar,
    ROUND(
        SUM(CASE WHEN be.event_name = 'booking_confirmed' THEN be.price_zar ELSE 0 END), 0
    )                                               AS total_revenue_proxy_zar
FROM `accommodation_intelligence.fact_booking_events` AS be
WHERE event_date BETWEEN '2025-01-01' AND '2025-06-30'
GROUP BY province
HAVING sessions > 100
ORDER BY confirmed_bookings DESC;


-- ────────────────────────────────────────────────────────────
-- Q8. DEVICE × PRICE TIER ANALYSIS
--     Do mobile users book cheaper properties?
--     Critical for responsive design and UX investment
-- ────────────────────────────────────────────────────────────
SELECT
    ws.device_category,
    fl.price_tier,
    COUNT(DISTINCT ws.session_id)                   AS sessions,
    ROUND(AVG(ws.engagement_secs), 1)               AS avg_engagement_secs,
    ROUND(AVG(ws.bounced), 3)                       AS bounce_rate,
    COUNTIF(be.event_name = 'booking_confirmed')    AS bookings
FROM `accommodation_intelligence.fact_web_sessions`   AS ws
LEFT JOIN `accommodation_intelligence.fact_booking_events` AS be
    ON ws.session_id = be.session_id
    AND be.event_name = 'booking_confirmed'
LEFT JOIN `accommodation_intelligence.fact_listings`  AS fl
    ON ws.property_id = fl.property_id
    AND fl.scraped_date = '2026-06-27'
WHERE ws.event_date BETWEEN '2025-01-01' AND '2025-06-30'
GROUP BY ws.device_category, fl.price_tier
ORDER BY ws.device_category, bookings DESC;


-- ────────────────────────────────────────────────────────────
-- Q9. POPIA CONSENT MODE AUDIT
--     SA POPIA requires similar consent tracking to GDPR.
--     What percentage of booking events have analytics consent?
--     Non-consented events use modelled measurement.
-- ────────────────────────────────────────────────────────────
SELECT
    analytics_consent,
    event_name,
    COUNT(*)                                        AS events,
    COUNT(DISTINCT session_id)                      AS sessions,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (PARTITION BY event_name), 2)
                                                    AS share_within_event_pct,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2)
                                                    AS share_of_total_pct
FROM `accommodation_intelligence.fact_booking_events`
WHERE event_date BETWEEN '2025-01-01' AND '2025-06-30'
GROUP BY analytics_consent, event_name
ORDER BY event_name, analytics_consent DESC;


-- ────────────────────────────────────────────────────────────
-- Q10. LISTING TYPE CONVERSION RATES
--      Which property type converts best?
--      Self Catering is dominant (67%) — does it also book best?
-- ────────────────────────────────────────────────────────────
WITH listing_sessions AS (
    SELECT
        ws.session_id,
        fl.listing_type,
        fl.price_tier,
        fl.price_zar,
        COUNTIF(be.event_name = 'booking_confirmed') AS converted
    FROM `accommodation_intelligence.fact_web_sessions` AS ws
    LEFT JOIN `accommodation_intelligence.fact_listing_events` AS be
        ON ws.session_id = be.session_id AND be.event_name = 'booking_confirmed'
    LEFT JOIN `accommodation_intelligence.fact_listings` AS fl
        ON ws.property_id = fl.property_id AND fl.scraped_date = '2026-06-27'
    WHERE ws.event_date BETWEEN '2025-01-01' AND '2025-06-30'
    GROUP BY ws.session_id, fl.listing_type, fl.price_tier, fl.price_zar
)
SELECT
    listing_type,
    price_tier,
    COUNT(*)                                        AS sessions,
    SUM(converted)                                  AS bookings,
    ROUND(SUM(converted) * 100.0 / NULLIF(COUNT(*), 0), 2)
                                                    AS conversion_rate_pct,
    ROUND(AVG(price_zar), 0)                        AS avg_price_zar
FROM listing_sessions
WHERE listing_type IS NOT NULL
GROUP BY listing_type, price_tier
ORDER BY conversion_rate_pct DESC;


-- ────────────────────────────────────────────────────────────
-- Q11. ML MODEL ACCURACY — UNDERPRICED PROPERTIES
--      Properties where predicted_price >> actual price
--      may be undervaluing themselves relative to peers.
--      Insight: "Here are 20 properties potentially leaving
--      money on the table."
-- ────────────────────────────────────────────────────────────
SELECT
    mp.property_name,
    mp.listing_type,
    mp.region,
    mp.price_tier,
    mp.price_zar                                    AS actual_price_zar,
    mp.predicted_price_zar,
    mp.price_delta_zar,
    mp.review_count,
    mp.demand_score,
    CASE
        WHEN mp.price_delta_zar > 500
        THEN 'Potentially Underpriced'
        WHEN mp.price_delta_zar < -500
        THEN 'Potentially Overpriced'
        ELSE 'Market-Aligned'
    END                                             AS pricing_signal
FROM `accommodation_intelligence.ml_predictions`  AS mp
WHERE price_delta_zar IS NOT NULL
ORDER BY price_delta_zar DESC
LIMIT 30;


-- ────────────────────────────────────────────────────────────
-- Q12. MONTHLY BOOKING TREND WITH MOVING AVERAGE
--      Detect seasonality in SA accommodation demand
--      (Jan = post-holiday slump, Dec = festive peak)
-- ────────────────────────────────────────────────────────────
WITH monthly AS (
    SELECT
        DATE_TRUNC(event_date, MONTH)               AS month,
        COUNT(DISTINCT session_id)                  AS sessions,
        COUNTIF(event_name = 'booking_confirmed')   AS bookings,
        ROUND(
            COUNTIF(event_name = 'booking_confirmed') * 100.0
            / NULLIF(COUNT(DISTINCT session_id), 0), 2
        )                                           AS conv_rate_pct,
        ROUND(AVG(CASE WHEN event_name='booking_confirmed' THEN price_zar END),0)
                                                    AS avg_booking_value_zar
    FROM `accommodation_intelligence.fact_booking_events`
    WHERE event_date BETWEEN '2025-01-01' AND '2025-06-30'
    GROUP BY month
)
SELECT
    month,
    sessions,
    bookings,
    conv_rate_pct,
    avg_booking_value_zar,
    AVG(bookings) OVER (
        ORDER BY month ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
    )                                               AS bookings_3m_moving_avg
FROM monthly
ORDER BY month;


-- ────────────────────────────────────────────────────────────
-- Q13. GTM TAG HEALTH — MISSING EVENT PARAMETERS
--      Check if required GA4 parameters are present.
--      Missing analytics_consent = POPIA gap.
--      Missing province = geo-targeting broken.
--      (Adapt to GA4 BQ export schema for real implementation)
-- ────────────────────────────────────────────────────────────
SELECT
    event_name,
    COUNT(*)                                        AS total_events,
    COUNTIF(analytics_consent IS NULL)              AS missing_consent,
    COUNTIF(province IS NULL)                       AS missing_province,
    COUNTIF(traffic_source IS NULL)                 AS missing_source,
    COUNTIF(property_id IS NULL)                    AS missing_property_id,
    ROUND(
        COUNTIF(analytics_consent IS NULL) * 100.0
        / NULLIF(COUNT(*), 0), 2
    )                                               AS consent_gap_pct
FROM `accommodation_intelligence.fact_booking_events`
WHERE event_date BETWEEN '2025-01-01' AND '2025-06-30'
GROUP BY event_name
ORDER BY missing_consent DESC;


-- ────────────────────────────────────────────────────────────
-- Q14. TOP PROPERTIES BY DEMAND SCORE + CONVERSION
--      Cross-join ML demand predictions with web session
--      data to surface the truly "high-value" listings.
--      These are candidates for featured/sponsored placement.
-- ────────────────────────────────────────────────────────────
WITH session_bookings AS (
    SELECT
        property_id,
        COUNT(DISTINCT session_id)  AS sessions,
        COUNTIF(event_name = 'booking_confirmed') AS bookings
    FROM `accommodation_intelligence.fact_booking_events`
    WHERE event_date BETWEEN '2025-01-01' AND '2025-06-30'
    GROUP BY property_id
)
SELECT
    dp.property_name,
    dp.listing_type,
    dp.price_zar,
    dp.price_tier,
    dp.review_count,
    dp.demand_score,
    mp.predicted_demand,
    mp.pricing_signal,
    COALESCE(sb.sessions, 0)                        AS platform_sessions,
    COALESCE(sb.bookings, 0)                        AS platform_bookings,
    ROUND(
        COALESCE(sb.bookings, 0) * 100.0
        / NULLIF(COALESCE(sb.sessions, 0), 0), 2
    )                                               AS platform_conv_rate_pct,
    -- Composite rank: demand_score × conversion × review normalised
    ROUND(
        (dp.demand_score * 0.4)
        + (COALESCE(sb.bookings, 0) * 2.0)
        + (LOG(dp.review_count + 1) * 5), 2
    )                                               AS composite_rank_score
FROM `accommodation_intelligence.dim_property` AS dp
LEFT JOIN (
    SELECT property_id,
           pricing_signal,
           predicted_demand
    FROM `accommodation_intelligence.ml_predictions`
) AS mp ON dp.property_id = mp.property_id
LEFT JOIN session_bookings AS sb ON dp.property_id = sb.property_id
WHERE dp.price_zar IS NOT NULL
ORDER BY composite_rank_score DESC
LIMIT 25;
