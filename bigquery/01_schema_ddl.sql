-- ============================================================
-- SA Accommodation Intelligence Platform
-- BigQuery Star Schema DDL
-- Dataset: accommodation_intelligence
-- Author : Anthony Apollis | 2026-06-27
--
-- FREE ETL OPTIONS IN BIGQUERY:
--   1. bq load (CLI)       — free CSV/JSON/Parquet load from GCS or local
--   2. Data Transfer Svc   — free for BQ↔BQ, Cloud Storage, GA4 export
--   3. GA4 → BQ export     — free daily auto-export (enable in GA4 admin)
--   4. Scheduled Queries   — free SQL transforms within 1TB/month quota
--   5. Dataform            — free SQL-based ELT inside BQ (dbt-like)
--   6. bq load --autodetect— schema inference is free; only storage billed
--
-- LOAD COMMANDS (run after authenticating with gcloud auth):
--   bq load --autodetect --source_format=CSV \
--     accommodation_intelligence.dim_property \
--     ./data/dim_property.csv
--
--   bq load --autodetect --source_format=CSV \
--     accommodation_intelligence.dim_region \
--     ./data/dim_region.csv
--
--   bq load --autodetect --source_format=CSV \
--     accommodation_intelligence.fact_listings \
--     ./data/fact_listings.csv
--
--   bq load --autodetect --source_format=CSV \
--     accommodation_intelligence.fact_web_sessions \
--     ./data/fact_web_sessions.csv
--
--   bq load --autodetect --source_format=CSV \
--     accommodation_intelligence.fact_booking_events \
--     ./data/fact_booking_events.csv
-- ============================================================

-- ────────────────────────────────────────────────────────────
-- 0. CREATE DATASET
-- ────────────────────────────────────────────────────────────
-- gcloud CLI: bq mk --location=africa-south1 accommodation_intelligence
-- (africa-south1 = Johannesburg — lowest latency for SA users)


-- ────────────────────────────────────────────────────────────
-- 1. DIMENSION: PROPERTY
-- ────────────────────────────────────────────────────────────
CREATE OR REPLACE TABLE `accommodation_intelligence.dim_property` (
    property_id       INT64          NOT NULL OPTIONS(description="LekkeSlaap internal property ID"),
    property_name     STRING         NOT NULL OPTIONS(description="Cleaned display name (promo noise removed)"),
    listing_type      STRING                  OPTIONS(description="Self Catering | Guest House | Lodge | Hotel | B&B | Game Lodge | Resort"),
    price_zar         FLOAT64                 OPTIONS(description="Nightly rate in ZAR (cleaned; NULL if outlier >R20,000)"),
    price_tier        STRING                  OPTIONS(description="Budget(<R700) | Mid-Range(R700–R1199) | Premium(R1200–R2499) | Luxury(R2500+)"),
    review_count      INT64                   OPTIONS(description="Total guest reviews on LekkeSlaap"),
    demand_score      FLOAT64                 OPTIONS(description="Composite score 0–100 (review_count × tier weight, normalised)"),
    url               STRING                  OPTIONS(description="Canonical listing URL on lekkeslaap.co.za"),
    ingested_at       TIMESTAMP               OPTIONS(description="ETL load timestamp (UTC)")
)
PARTITION BY DATE(ingested_at)
CLUSTER BY listing_type, price_tier
OPTIONS (
    description = "Property master dimension — one row per unique LekkeSlaap property"
);


-- ────────────────────────────────────────────────────────────
-- 2. DIMENSION: REGION
-- ────────────────────────────────────────────────────────────
CREATE OR REPLACE TABLE `accommodation_intelligence.dim_region` (
    region_id     INT64   NOT NULL OPTIONS(description="Surrogate key"),
    region        STRING  NOT NULL OPTIONS(description="Region name extracted from LekkeSlaap browse URL"),
    country       STRING           OPTIONS(description="South Africa | Namibia")
)
CLUSTER BY country
OPTIONS (
    description = "Region dimension — SA provinces/regions + Namibia from source_page URL"
);


-- ────────────────────────────────────────────────────────────
-- 3. FACT: PROPERTY LISTINGS (core analytics grain)
-- ────────────────────────────────────────────────────────────
CREATE OR REPLACE TABLE `accommodation_intelligence.fact_listings` (
    property_id       INT64   NOT NULL,
    region_id         INT64            OPTIONS(description="FK → dim_region"),
    price_zar         FLOAT64,
    review_count      INT64,
    demand_score      FLOAT64,
    listing_type      STRING,
    price_tier        STRING,
    has_promo_flag    BOOL             OPTIONS(description="TRUE if listing was scraped with a discount banner (e.g. Flash Deal)"),
    discount_pct      FLOAT64          OPTIONS(description="Discount percentage advertised in the promo banner; NULL if no promo"),
    scraped_date      DATE
)
PARTITION BY scraped_date
CLUSTER BY listing_type, region_id
OPTIONS (
    description = "Fact table — one row per property per scrape date"
);


-- ────────────────────────────────────────────────────────────
-- 4. FACT: WEB SESSIONS (GA4-schema, synthetic)
-- ────────────────────────────────────────────────────────────
CREATE OR REPLACE TABLE `accommodation_intelligence.fact_web_sessions` (
    session_id          STRING  NOT NULL OPTIONS(description="Unique session identifier (UUID prefix)"),
    user_pseudo_id      STRING           OPTIONS(description="GA4 client_id (hashed)"),
    event_date          DATE             OPTIONS(description="Session date"),
    traffic_source      STRING           OPTIONS(description="google | facebook | instagram | direct | email | (other)"),
    traffic_medium      STRING           OPTIONS(description="organic | cpc | social | (none) | email | referral"),
    device_category     STRING           OPTIONS(description="mobile | desktop | tablet"),
    province            STRING           OPTIONS(description="SA province derived from user location (GA4 geo.region equivalent)"),
    property_id         INT64            OPTIONS(description="Property viewed in this session"),
    price_tier_viewed   STRING           OPTIONS(description="Price tier of the property viewed"),
    engagement_secs     INT64            OPTIONS(description="Total engagement time in seconds (GA4: engagement_time_msec/1000)"),
    bounced             INT64            OPTIONS(description="1 = bounced session (<15s or no interaction)"),
    session_engaged     INT64            OPTIONS(description="1 = engaged session (GA4 definition: >10s OR 2+ pages OR conversion)")
)
PARTITION BY event_date
CLUSTER BY traffic_source, device_category, province
OPTIONS (
    description = "GA4-equivalent web session facts — simulated from LekkeSlaap platform model"
);


-- ────────────────────────────────────────────────────────────
-- 5. FACT: BOOKING EVENTS (GA4 ecommerce equivalent)
-- ────────────────────────────────────────────────────────────
CREATE OR REPLACE TABLE `accommodation_intelligence.fact_booking_events` (
    event_id            INT64   NOT NULL OPTIONS(description="Surrogate event key"),
    session_id          STRING           OPTIONS(description="FK → fact_web_sessions"),
    user_pseudo_id      STRING,
    event_date          DATE,
    event_timestamp     INT64            OPTIONS(description="Microseconds since epoch (GA4 format)"),
    event_name          STRING           OPTIONS(description="listing_view | search_nearby | contact_host | booking_initiated | booking_confirmed"),
    property_id         INT64,
    price_zar           FLOAT64,
    price_tier          STRING,
    listing_type        STRING,
    device_category     STRING,
    province            STRING,
    traffic_source      STRING,
    traffic_medium      STRING,
    analytics_consent   STRING           OPTIONS(description="Yes | No — POPIA consent mode (GA4: privacy_info.analytics_storage)")
)
PARTITION BY event_date
CLUSTER BY event_name, traffic_source, province
OPTIONS (
    description = "GA4 booking funnel events — maps to GA4 ecommerce event flow (listing_view=view_item, booking_confirmed=purchase)"
);


-- ────────────────────────────────────────────────────────────
-- 6. ML PREDICTIONS TABLE
-- ────────────────────────────────────────────────────────────
CREATE OR REPLACE TABLE `accommodation_intelligence.ml_predictions` (
    property_id           INT64,
    property_name         STRING,
    listing_type          STRING,
    region                STRING,
    price_zar             FLOAT64          OPTIONS(description="Actual scraped price"),
    predicted_price_zar   FLOAT64          OPTIONS(description="GBR model predicted price"),
    price_delta_zar       FLOAT64          OPTIONS(description="Predicted − Actual (positive = underpriced vs model expectation)"),
    price_tier            STRING           OPTIONS(description="Actual tier label"),
    predicted_tier        STRING           OPTIONS(description="RF classifier predicted tier"),
    demand_score          FLOAT64          OPTIONS(description="Actual demand score"),
    predicted_demand      FLOAT64          OPTIONS(description="GBR predicted demand score"),
    review_count          INT64,
    model_run_date        DATE
)
OPTIONS (
    description = "ML model outputs — price regression + tier classification + demand scoring"
);
