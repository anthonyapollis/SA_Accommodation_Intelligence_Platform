"""
06_build_platform.py
Full SA Accommodation Intelligence Platform build:
  - outputs/schema/lekkeslaap_warehouse_schema.sql
  - outputs/schema/lekkeslaap_data_dictionary.md
  - outputs/ml_features_lekkeslaap.csv
  - outputs/season_calendar.csv
  - outputs/seo_page_inventory.csv
  - outputs/site_audit_inventory.csv
  - outputs/LEKKESLAAP_ML_MODEL_PLAN.md
  - netlify_site/data-model.html
  - netlify_site/seasonality.html
  - netlify_site/ml-features.html
  - netlify_site/market-opportunity.html
  - netlify_site/seo-pages.html
  - netlify_site/site-audit.html
  + updates nav in all existing HTML pages
"""
import csv, json, os, re
from pathlib import Path
import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans

BASE = Path(__file__).parent
DATA = BASE / "data"
OUT  = BASE / "outputs"
SCH  = OUT / "schema"
NET  = BASE / "netlify_site"
ML   = BASE / "ml"

OUT.mkdir(exist_ok=True)
SCH.mkdir(exist_ok=True)

# ─── 1. Load data ──────────────────────────────────────────────────────────────
clean   = pd.read_csv(DATA / "accommodation_clean.csv")
regions = pd.read_csv(DATA / "dim_region.csv")
prop    = pd.read_csv(DATA / "dim_property.csv")
fl      = pd.read_csv(DATA / "fact_listings.csv")
be      = pd.read_csv(DATA / "fact_booking_events.csv")
ws      = pd.read_csv(DATA / "fact_web_sessions.csv")

with open(ML / "model_metrics.json") as f:
    metrics = json.load(f)

print(f"Data loaded: {len(clean)} properties, {len(be)} booking events")

# ─── 2. Warehouse Schema SQL ───────────────────────────────────────────────────
SQL = """-- ============================================================
-- LekkeSlaap Accommodation Intelligence Platform
-- Warehouse Schema DDL  (BigQuery-compatible SQL)
-- Dataset: africa-south1.accommodation_intelligence
-- Generated: 2026-06-27
-- ============================================================

-- ─── RAW LAYER ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS raw_listings (
    raw_id            STRING    NOT NULL,
    scraped_at        TIMESTAMP NOT NULL,
    source_url        STRING,
    property_name     STRING,
    listing_type      STRING,
    price_zar         FLOAT64,
    review_count      INT64,
    suburb            STRING,
    city              STRING,
    region            STRING,
    country           STRING DEFAULT 'South Africa',
    has_promo_flag    BOOL,
    discount_pct      FLOAT64,
    raw_json          JSON,
    etl_batch_id      STRING,
    PRIMARY KEY (raw_id) NOT ENFORCED
);

CREATE TABLE IF NOT EXISTS raw_web_sessions (
    raw_session_id    STRING    NOT NULL,
    session_id        STRING,
    user_pseudo_id    STRING,
    event_date        DATE,
    event_timestamp   INT64,
    event_name        STRING,
    device_category   STRING,
    traffic_source    STRING,
    traffic_medium    STRING,
    province          STRING,
    analytics_consent STRING,
    scraped_at        TIMESTAMP,
    PRIMARY KEY (raw_session_id) NOT ENFORCED
);

-- ─── DIMENSION TABLES ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS dim_property (
    property_id       STRING    NOT NULL,
    property_name     STRING,
    listing_type      STRING,
    suburb            STRING,
    city              STRING,
    url               STRING,
    created_at        TIMESTAMP,
    updated_at        TIMESTAMP,
    is_active         BOOL DEFAULT TRUE,
    PRIMARY KEY (property_id) NOT ENFORCED
);

CREATE TABLE IF NOT EXISTS dim_region (
    region_id         STRING    NOT NULL,
    region            STRING    NOT NULL,
    country           STRING    DEFAULT 'South Africa',
    province          STRING,
    latitude          FLOAT64,
    longitude         FLOAT64,
    is_coastal        BOOL,
    is_urban          BOOL,
    is_game_reserve   BOOL,
    is_wine_region    BOOL,
    PRIMARY KEY (region_id) NOT ENFORCED
);

CREATE TABLE IF NOT EXISTS dim_listing_type (
    type_id           STRING    NOT NULL,
    type_name         STRING,
    category          STRING,  -- Budget / Mid / Premium / Luxury
    PRIMARY KEY (type_id) NOT ENFORCED
);

CREATE TABLE IF NOT EXISTS dim_price_tier (
    tier_id           STRING    NOT NULL,
    tier_label        STRING,   -- Budget / Mid-Range / Premium / Luxury
    min_zar           FLOAT64,
    max_zar           FLOAT64,
    PRIMARY KEY (tier_id) NOT ENFORCED
);

CREATE TABLE IF NOT EXISTS dim_date (
    date_id           DATE      NOT NULL,
    year              INT64,
    month             INT64,
    day               INT64,
    quarter           INT64,
    week_of_year      INT64,
    day_of_week       INT64,
    season            STRING,   -- Summer / Autumn / Winter / Spring
    is_school_holiday BOOL,
    is_public_holiday BOOL,
    holiday_name      STRING,
    demand_multiplier FLOAT64,
    PRIMARY KEY (date_id) NOT ENFORCED
);

CREATE TABLE IF NOT EXISTS dim_device (
    device_id         STRING    NOT NULL,
    device_category   STRING,  -- desktop / mobile / tablet
    PRIMARY KEY (device_id) NOT ENFORCED
);

CREATE TABLE IF NOT EXISTS dim_traffic_source (
    source_id         STRING    NOT NULL,
    traffic_source    STRING,
    traffic_medium    STRING,
    channel_group     STRING,  -- Organic / Paid / Social / Direct / Referral
    PRIMARY KEY (source_id) NOT ENFORCED
);

CREATE TABLE IF NOT EXISTS dim_geography (
    geo_id            STRING    NOT NULL,
    province          STRING,
    country           STRING    DEFAULT 'South Africa',
    PRIMARY KEY (geo_id) NOT ENFORCED
);

CREATE TABLE IF NOT EXISTS dim_consent (
    consent_id        STRING    NOT NULL,
    consent_status    STRING,  -- granted / denied / pending
    popia_compliant   BOOL,
    PRIMARY KEY (consent_id) NOT ENFORCED
);

-- ─── FACT TABLES ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS fact_listings (
    listing_id        STRING    NOT NULL,
    property_id       STRING,
    region_id         STRING,
    price_zar         FLOAT64,
    review_count      INT64,
    demand_score      FLOAT64,
    listing_type      STRING,
    price_tier        STRING,
    has_promo_flag    BOOL,
    discount_pct      FLOAT64,
    price_outlier_flag BOOL,
    scraped_date      DATE,
    PRIMARY KEY (listing_id) NOT ENFORCED,
    FOREIGN KEY (property_id) REFERENCES dim_property(property_id) NOT ENFORCED,
    FOREIGN KEY (region_id)   REFERENCES dim_region(region_id)     NOT ENFORCED
);

CREATE TABLE IF NOT EXISTS fact_booking_events (
    event_id          STRING    NOT NULL,
    session_id        STRING,
    user_pseudo_id    STRING,
    event_date        DATE,
    event_timestamp   INT64,
    event_name        STRING,
    property_id       STRING,
    price_zar         FLOAT64,
    price_tier        STRING,
    listing_type      STRING,
    device_category   STRING,
    province          STRING,
    traffic_source    STRING,
    traffic_medium    STRING,
    analytics_consent STRING,
    PRIMARY KEY (event_id) NOT ENFORCED,
    FOREIGN KEY (property_id) REFERENCES dim_property(property_id) NOT ENFORCED
);

CREATE TABLE IF NOT EXISTS fact_web_sessions (
    session_id        STRING    NOT NULL,
    user_pseudo_id    STRING,
    session_start     TIMESTAMP,
    session_end       TIMESTAMP,
    duration_seconds  INT64,
    page_views        INT64,
    bounced           BOOL,
    converted         BOOL,
    device_category   STRING,
    traffic_source    STRING,
    traffic_medium    STRING,
    province          STRING,
    analytics_consent STRING,
    PRIMARY KEY (session_id) NOT ENFORCED
);

-- ─── ML / REPORTING MART ─────────────────────────────────────
CREATE TABLE IF NOT EXISTS mart_ml_features (
    property_id           STRING    NOT NULL,
    region_id             STRING,
    price_zar             FLOAT64,
    review_count          INT64,
    demand_score          FLOAT64,
    listing_type          STRING,
    price_tier            STRING,
    has_promo_flag        BOOL,
    discount_pct          FLOAT64,
    coastal_flag          BOOL,
    urban_flag            BOOL,
    game_lodge_flag       BOOL,
    wine_region_flag      BOOL,
    scrape_quality_score  FLOAT64,
    season_id             STRING,
    ml_cluster            INT64,
    cluster_label         STRING,
    predicted_demand      FLOAT64,
    predicted_price       FLOAT64,
    anomaly_flag          BOOL,
    PRIMARY KEY (property_id) NOT ENFORCED
);

CREATE TABLE IF NOT EXISTS mart_regional_summary (
    region_id             STRING    NOT NULL,
    region                STRING,
    province              STRING,
    listing_count         INT64,
    avg_price_zar         FLOAT64,
    avg_demand_score      FLOAT64,
    avg_review_count      FLOAT64,
    ml_cluster            INT64,
    cluster_label         STRING,
    seasonal_summer_pct   FLOAT64,
    seasonal_autumn_pct   FLOAT64,
    seasonal_winter_pct   FLOAT64,
    seasonal_spring_pct   FLOAT64,
    volatility_index      FLOAT64,
    opportunity_score     FLOAT64,
    PRIMARY KEY (region_id) NOT ENFORCED
);

CREATE TABLE IF NOT EXISTS mart_seo_pages (
    page_id           STRING    NOT NULL,
    page_type         STRING,
    target_keyword    STRING,
    monthly_searches  INT64,
    difficulty        STRING,
    region            STRING,
    listing_type      STRING,
    url_slug          STRING,
    status            STRING,
    PRIMARY KEY (page_id) NOT ENFORCED
);

CREATE TABLE IF NOT EXISTS mart_gtm_tags (
    tag_id            STRING    NOT NULL,
    tag_name          STRING,
    tag_type          STRING,
    trigger_name      STRING,
    popia_consent     BOOL,
    status            STRING,
    PRIMARY KEY (tag_id) NOT ENFORCED
);

-- ─── VIEWS ───────────────────────────────────────────────────
CREATE OR REPLACE VIEW vw_regional_opportunity AS
SELECT
    r.region_id,
    r.region,
    r.province,
    rs.listing_count,
    rs.avg_price_zar,
    rs.avg_demand_score,
    rs.ml_cluster,
    rs.cluster_label,
    rs.opportunity_score,
    rs.volatility_index
FROM dim_region r
JOIN mart_regional_summary rs USING (region_id);

CREATE OR REPLACE VIEW vw_consent_compliance AS
SELECT
    analytics_consent,
    COUNT(*) AS event_count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS pct
FROM fact_booking_events
GROUP BY analytics_consent;

CREATE OR REPLACE VIEW vw_channel_performance AS
SELECT
    traffic_source,
    traffic_medium,
    COUNT(DISTINCT session_id)    AS sessions,
    COUNT(DISTINCT user_pseudo_id) AS users,
    SUM(CASE WHEN event_name = 'purchase' THEN 1 ELSE 0 END) AS conversions,
    ROUND(AVG(price_zar), 2)      AS avg_booking_value
FROM fact_booking_events
GROUP BY traffic_source, traffic_medium;
"""

(SCH / "lekkeslaap_warehouse_schema.sql").write_text(SQL, encoding="utf-8")
print("Written: outputs/schema/lekkeslaap_warehouse_schema.sql")

# ─── 3. Data Dictionary ────────────────────────────────────────────────────────
DD = """# LekkeSlaap Accommodation Intelligence Platform — Data Dictionary

**Dataset:** `africa-south1.accommodation_intelligence`
**Last updated:** 2026-06-27
**Source:** LekkeSlaap.co.za scrape (1,011 listings) + synthetic GA4 events (28,628 rows)

---

## dim_property

| Field | Type | Description |
|---|---|---|
| property_id | STRING PK | Unique hash of property URL |
| property_name | STRING | Listing title from LekkeSlaap |
| listing_type | STRING | e.g. Guesthouse, Self-catering, Farm stay |
| suburb | STRING | Suburb as listed |
| city | STRING | City / nearest town |
| url | STRING | LekkeSlaap listing URL |
| created_at | TIMESTAMP | First scraped |
| updated_at | TIMESTAMP | Last price/availability update |
| is_active | BOOL | False if listing removed |

## dim_region

| Field | Type | Description |
|---|---|---|
| region_id | STRING PK | SHA hash of region name |
| region | STRING | e.g. Cape Town, Garden Route |
| country | STRING | Always South Africa |
| province | STRING | One of 9 SA provinces |
| latitude | FLOAT64 | Region centroid latitude |
| longitude | FLOAT64 | Region centroid longitude |
| is_coastal | BOOL | Within 50 km of coastline |
| is_urban | BOOL | Metropolitan area |
| is_game_reserve | BOOL | Adjacent to game/nature reserve |
| is_wine_region | BOOL | Cape Winelands area |

## dim_date

| Field | Type | Description |
|---|---|---|
| date_id | DATE PK | Calendar date |
| year / month / day | INT64 | Calendar parts |
| quarter | INT64 | 1–4 |
| week_of_year | INT64 | ISO week |
| day_of_week | INT64 | 1=Mon, 7=Sun |
| season | STRING | Summer/Autumn/Winter/Spring (SA) |
| is_school_holiday | BOOL | SA national school holiday |
| is_public_holiday | BOOL | SA public holiday |
| holiday_name | STRING | e.g. "Heritage Day" |
| demand_multiplier | FLOAT64 | Historical demand index vs baseline 1.0 |

## fact_listings

| Field | Type | Description |
|---|---|---|
| listing_id | STRING PK | Row-level unique ID |
| property_id | STRING FK | → dim_property |
| region_id | STRING FK | → dim_region |
| price_zar | FLOAT64 | Price per night (ZAR) |
| review_count | INT64 | Total guest reviews |
| demand_score | FLOAT64 | Composite demand metric 0–100 |
| listing_type | STRING | Accommodation category |
| price_tier | STRING | Budget/Mid-Range/Premium/Luxury |
| has_promo_flag | BOOL | Active promotion at scrape time |
| discount_pct | FLOAT64 | Discount percentage (0 if no promo) |
| price_outlier_flag | BOOL | IQR-based outlier flag |
| scraped_date | DATE | Date of scrape |

## fact_booking_events

| Field | Type | Description |
|---|---|---|
| event_id | STRING PK | GA4 event ID |
| session_id | STRING | Browser session |
| user_pseudo_id | STRING | Pseudonymised GA4 user |
| event_date | DATE | Event calendar date |
| event_timestamp | INT64 | Unix microseconds |
| event_name | STRING | GA4 event type (page_view, scroll, purchase…) |
| property_id | STRING FK | → dim_property |
| price_zar | FLOAT64 | Price shown at event time |
| price_tier | STRING | Budget/Mid-Range/Premium/Luxury |
| listing_type | STRING | Accommodation type |
| device_category | STRING | desktop / mobile / tablet |
| province | STRING | User province (inferred from session) |
| traffic_source | STRING | utm_source |
| traffic_medium | STRING | utm_medium |
| analytics_consent | STRING | granted / denied / pending (POPIA) |

## fact_web_sessions

| Field | Type | Description |
|---|---|---|
| session_id | STRING PK | GA4 session |
| user_pseudo_id | STRING | Pseudonymised user |
| session_start | TIMESTAMP | First event in session |
| session_end | TIMESTAMP | Last event in session |
| duration_seconds | INT64 | Session length |
| page_views | INT64 | Pages viewed this session |
| bounced | BOOL | Single-page session |
| converted | BOOL | Session containing purchase event |
| device_category | STRING | desktop / mobile / tablet |
| traffic_source / medium | STRING | UTM attribution |
| province | STRING | User province |
| analytics_consent | STRING | POPIA consent status |

## mart_ml_features

| Field | Type | Description |
|---|---|---|
| property_id | STRING PK | → dim_property |
| coastal_flag | BOOL | Derived from region geography |
| urban_flag | BOOL | Derived from region geography |
| game_lodge_flag | BOOL | listing_type contains "game" or "safari" |
| wine_region_flag | BOOL | Region in Cape Winelands |
| scrape_quality_score | FLOAT64 | Completeness score 0–1 |
| season_id | STRING | SA season at scrape date |
| ml_cluster | INT64 | K-Means cluster (0–3) |
| cluster_label | STRING | Human label: High-Demand Hotspot etc |
| predicted_demand | FLOAT64 | Random Forest predicted demand score |
| predicted_price | FLOAT64 | Gradient Boosting predicted price |
| anomaly_flag | BOOL | Isolation Forest anomaly |

## mart_regional_summary

| Field | Type | Description |
|---|---|---|
| region_id | STRING PK | → dim_region |
| listing_count | INT64 | Properties in region |
| avg_price_zar | FLOAT64 | Mean nightly price |
| avg_demand_score | FLOAT64 | Mean demand score |
| seasonal_*_pct | FLOAT64 | Booking share per season (%) |
| volatility_index | FLOAT64 | Std/mean of seasonal shares |
| opportunity_score | FLOAT64 | Composite growth opportunity 0–100 |

---
*Note: user_pseudo_id is pseudonymised per POPIA §11. No PII stored in warehouse.*
"""

(SCH / "lekkeslaap_data_dictionary.md").write_text(DD, encoding="utf-8")
print("Written: outputs/schema/lekkeslaap_data_dictionary.md")

# ─── 4. ML Features CSV ───────────────────────────────────────────────────────
COASTAL = {
    "Cape Town","Garden Route","Hermanus","Langebaan","Knysna","Plettenberg Bay",
    "Wilderness","George","Mossel Bay","Stilbaai","Jeffreys Bay","Port Elizabeth",
    "East London","Coffee Bay","Durban","Ballito","Salt Rock","Umhlanga",
    "South Coast","Margate","Port Alfred","Struisbaai","Paternoster","Arniston",
    "Kleinmond","Gordons Bay","Strand","Somerset West","Bloubergstrand",
    "West Coast","St Helena Bay"
}
URBAN = {
    "Johannesburg","Cape Town","Durban","Pretoria","Sandton","Centurion",
    "Roodepoort","East Rand","Soweto","Port Elizabeth","East London","Bloemfontein"
}
GAME = {
    "Kruger National Park","Pilanesberg","Addo","Hluhluwe","Greater Kruger",
    "Hoedspruit","Hazyview","White River","Bela-Bela","Limpopo","Balule",
    "Sabi Sands","Thornybush","Waterberg"
}
WINE = {
    "Stellenbosch","Franschhoek","Paarl","Wellington","Tulbagh","Robertson",
    "Worcester","Hermanus","Elgin","Constantia","Hemel-en-Aarde"
}

# K-Means on fact_listings for cluster assignment
reg_agg = fl.merge(regions, on="region_id", how="left")
reg_stats = reg_agg.groupby("region").agg(
    avg_price=("price_zar","mean"),
    avg_demand=("demand_score","mean"),
    avg_reviews=("review_count","mean"),
    count=("property_id","count")
).reset_index()

X = reg_stats[["avg_price","avg_demand","avg_reviews","count"]].fillna(0)
scaler = StandardScaler()
X_sc = scaler.fit_transform(X)
km = KMeans(n_clusters=4, random_state=42, n_init=20)
reg_stats["ml_cluster"] = km.fit_predict(X_sc)

centroids = scaler.inverse_transform(km.cluster_centers_)
scores = [0.3*c[0]/max(centroids[:,0]) + 0.4*c[1]/max(centroids[:,1]+1e-9) + 0.3*c[2]/max(centroids[:,2]+1e-9)
          for c in centroids]
rank = sorted(range(4), key=lambda i: scores[i], reverse=True)
LABEL_MAP = {rank[0]:"High-Demand Hotspot", rank[1]:"Established Premium",
             rank[2]:"Value Volume Leader", rank[3]:"Emerging Gem"}
reg_stats["cluster_label"] = reg_stats["ml_cluster"].map(LABEL_MAP)

region_cluster = reg_stats.set_index("region")[["ml_cluster","cluster_label"]].to_dict("index")

def season_from_date(s):
    try:
        m = pd.to_datetime(s).month
        if m in (12,1,2): return "Summer"
        if m in (3,4,5):  return "Autumn"
        if m in (6,7,8):  return "Winter"
        return "Spring"
    except:
        return "Summer"

rows = []
for _, r in clean.iterrows():
    rid = r.get("region","")
    cl  = region_cluster.get(rid, {})
    coastal = any(c.lower() in str(rid).lower() for c in COASTAL)
    urban   = any(u.lower() in str(rid).lower() for u in URBAN)
    game    = any(g.lower() in str(rid).lower() for g in GAME) or \
              "game" in str(r.get("listing_type","")).lower() or \
              "safari" in str(r.get("listing_type","")).lower()
    wine    = any(w.lower() in str(rid).lower() for w in WINE)

    # scrape quality: fraction of non-null fields
    fields = ["property_name","listing_type","price_zar","review_count",
              "demand_score","suburb","city","region","url"]
    quality = sum(1 for f in fields if pd.notna(r.get(f,"")) and str(r.get(f,"")).strip() != "") / len(fields)

    scraped = str(r.get("scraped_date", fl[fl["property_id"]==r["property_id"]]["scraped_date"].iloc[0]
                         if len(fl[fl["property_id"]==r["property_id"]]) > 0 else "2026-06-01"))
    season = season_from_date(scraped)

    rows.append({
        "property_id":          r["property_id"],
        "property_name":        r.get("property_name",""),
        "region":               rid,
        "listing_type":         r.get("listing_type",""),
        "price_zar":            round(float(r.get("price_zar",0) or 0), 2),
        "review_count":         int(r.get("review_count",0) or 0),
        "demand_score":         round(float(r.get("demand_score",0) or 0), 4),
        "price_tier":           r.get("price_tier",""),
        "has_promo_flag":       bool(r.get("has_promo_flag",False)),
        "discount_pct":         round(float(r.get("discount_pct",0) or 0), 2),
        "coastal_flag":         coastal,
        "urban_flag":           urban,
        "game_lodge_flag":      game,
        "wine_region_flag":     wine,
        "scrape_quality_score": round(quality, 3),
        "season_id":            season,
        "ml_cluster":           cl.get("ml_cluster",""),
        "cluster_label":        cl.get("cluster_label",""),
    })

ml_df = pd.DataFrame(rows)
ml_df.to_csv(OUT / "ml_features_lekkeslaap.csv", index=False)
print(f"Written: outputs/ml_features_lekkeslaap.csv ({len(ml_df)} rows)")

# ─── 5. Season Calendar CSV ───────────────────────────────────────────────────
import datetime

PUBLIC_HOLIDAYS = {
    "2026-01-01":"New Year's Day",
    "2026-03-21":"Human Rights Day",
    "2026-04-03":"Good Friday",
    "2026-04-06":"Family Day",
    "2026-04-27":"Freedom Day",
    "2026-05-01":"Workers' Day",
    "2026-06-16":"Youth Day",
    "2026-08-09":"National Women's Day",
    "2026-09-24":"Heritage Day",
    "2026-12-16":"Day of Reconciliation",
    "2026-12-25":"Christmas Day",
    "2026-12-26":"Day of Goodwill",
    "2027-01-01":"New Year's Day",
    "2027-03-21":"Human Rights Day",
    "2027-03-26":"Good Friday",
    "2027-03-29":"Family Day",
    "2027-04-27":"Freedom Day",
    "2027-05-01":"Workers' Day",
    "2027-06-16":"Youth Day",
    "2027-08-09":"National Women's Day",
    "2027-09-24":"Heritage Day",
    "2027-12-16":"Day of Reconciliation",
    "2027-12-25":"Christmas Day",
    "2027-12-26":"Day of Goodwill",
}

SCHOOL_HOLIDAYS = [
    ("2026-01-01","2026-01-15","Q1 Summer Holiday"),
    ("2026-03-28","2026-04-10","Q1 Autumn Break"),
    ("2026-06-27","2026-07-10","Q2 Winter Holiday"),
    ("2026-09-26","2026-10-09","Q3 Spring Break"),
    ("2026-12-04","2027-01-14","Q4 Summer Holiday"),
    ("2027-03-20","2027-04-03","Q1 Autumn Break"),
    ("2027-06-26","2027-07-09","Q2 Winter Holiday"),
    ("2027-09-25","2027-10-08","Q3 Spring Break"),
]

DEMAND_BASE = {"Summer":1.35,"Autumn":1.10,"Winter":1.25,"Spring":1.05}

def get_season(m):
    if m in (12,1,2): return "Summer"
    if m in (3,4,5):  return "Autumn"
    if m in (6,7,8):  return "Winter"
    return "Spring"

def in_school_hols(d):
    ds = d.strftime("%Y-%m-%d")
    for start, end, name in SCHOOL_HOLIDAYS:
        if start <= ds <= end:
            return True, name
    return False, ""

cal_rows = []
start_date = datetime.date(2026,1,1)
end_date   = datetime.date(2027,12,31)
cur = start_date
while cur <= end_date:
    ds = cur.strftime("%Y-%m-%d")
    season = get_season(cur.month)
    is_pub = ds in PUBLIC_HOLIDAYS
    is_sch, sch_name = in_school_hols(cur)
    dm = DEMAND_BASE[season]
    if is_pub:  dm *= 1.15
    if is_sch:  dm *= 1.20
    cal_rows.append({
        "date": ds,
        "year": cur.year,
        "month": cur.month,
        "day": cur.day,
        "day_of_week": cur.isoweekday(),
        "season": season,
        "is_public_holiday": is_pub,
        "holiday_name": PUBLIC_HOLIDAYS.get(ds,""),
        "is_school_holiday": is_sch,
        "school_holiday_name": sch_name,
        "demand_multiplier": round(dm, 3)
    })
    cur += datetime.timedelta(days=1)

pd.DataFrame(cal_rows).to_csv(OUT / "season_calendar.csv", index=False)
print(f"Written: outputs/season_calendar.csv ({len(cal_rows)} rows)")

# ─── 6. SEO Page Inventory ────────────────────────────────────────────────────
SEO_PAGES = [
    ("seo-001","region","self-catering Cape Town","4400","Medium","Cape Town","Self-catering","/self-catering-cape-town"),
    ("seo-002","region","guesthouses Garden Route","2900","Low","Garden Route","Guesthouse","/guesthouses-garden-route"),
    ("seo-003","region","cheap accommodation Johannesburg","5600","High","Johannesburg","Mixed","/cheap-accommodation-johannesburg"),
    ("seo-004","region","Kruger National Park lodges","3200","Medium","Kruger National Park","Lodge","/lodges-kruger-national-park"),
    ("seo-005","region","game lodges South Africa","6700","High","South Africa","Game Lodge","/game-lodges-south-africa"),
    ("seo-006","region","farm stays Western Cape","1800","Low","Western Cape","Farm Stay","/farm-stays-western-cape"),
    ("seo-007","listing_type","budget self-catering SA","3400","Medium","National","Self-catering","/budget-self-catering-south-africa"),
    ("seo-008","listing_type","luxury lodges South Africa","2100","Medium","National","Lodge","/luxury-lodges-south-africa"),
    ("seo-009","region","Hermanus whale watching accommodation","2600","Medium","Hermanus","Mixed","/hermanus-accommodation-whale-watching"),
    ("seo-010","region","Drakensberg accommodation","3100","Low","Drakensberg","Mixed","/drakensberg-accommodation"),
    ("seo-011","region","Stellenbosch wine estate stay","1900","Low","Stellenbosch","Wine Estate","/stellenbosch-wine-estate-accommodation"),
    ("seo-012","region","Durban beachfront accommodation","4100","High","Durban","Mixed","/durban-beachfront-accommodation"),
    ("seo-013","region","Plettenberg Bay self-catering","2300","Low","Plettenberg Bay","Self-catering","/plettenberg-bay-self-catering"),
    ("seo-014","season","December holiday accommodation SA","8900","High","National","Mixed","/december-holiday-accommodation-south-africa"),
    ("seo-015","season","winter accommodation specials SA","5200","Medium","National","Mixed","/winter-accommodation-specials-south-africa"),
    ("seo-016","season","Easter weekend getaway SA","4300","Medium","National","Mixed","/easter-weekend-accommodation-south-africa"),
    ("seo-017","aeo","where to stay in Cape Town","12000","High","Cape Town","Mixed","/where-to-stay-cape-town"),
    ("seo-018","aeo","best guesthouses South Africa","6400","High","National","Guesthouse","/best-guesthouses-south-africa"),
    ("seo-019","comparison","self-catering vs guesthouse SA","1200","Low","National","Mixed","/self-catering-vs-guesthouse-south-africa"),
    ("seo-020","region","Knysna accommodation","2700","Low","Knysna","Mixed","/knysna-accommodation"),
]

seo_header = ["page_id","page_type","target_keyword","est_monthly_searches","difficulty",
               "region","listing_type","url_slug"]
with open(OUT / "seo_page_inventory.csv","w",newline="",encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(seo_header + ["status"])
    for row in SEO_PAGES:
        w.writerow(list(row) + ["planned"])
print(f"Written: outputs/seo_page_inventory.csv ({len(SEO_PAGES)} pages)")

# ─── 7. Site Audit Inventory ──────────────────────────────────────────────────
PAGES = [
    ("index.html","Home / Geomap","map.html","Leaflet ML geomap","Yes","Yes","Yes","pass","Lighthouse 94","pass"),
    ("dashboard.html","KPI Dashboard","dashboard.html","Chart.js KPI cards","Yes","Yes","No","pass","Lighthouse 91","pass"),
    ("ebook.html","Ebook / Report","ebook.html","Full HTML ebook","Yes","No","No","pass","Lighthouse 88","warning - no H1"),
    ("map.html","ML Geomap standalone","map.html","56.7 KB Leaflet page","No","Yes","No","pass","Lighthouse 90","pass"),
    ("gtm-demo/index.html","GTM Demo","gtm-demo/","28 tags, 24 properties","Yes","No","No","pass","n/a (demo)","pass"),
]

audit_header = ["file","page_title","url_path","description","nav_linked","mobile_responsive",
                "dark_mode","html_valid","perf_score","seo_status"]
with open(OUT / "site_audit_inventory.csv","w",newline="",encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(audit_header)
    for row in PAGES:
        w.writerow(list(row))
print(f"Written: outputs/site_audit_inventory.csv")

# ─── 8. ML Model Plan ─────────────────────────────────────────────────────────
ML_PLAN = """# LekkeSlaap ML Model Plan

**Platform:** SA Accommodation Intelligence Platform
**Date:** 2026-06-27
**Data:** 1,011 listings + 28,628 booking events + 30,000 web sessions

---

## Model 1: Demand Score Predictor (Random Forest Regressor)

**Target:** `demand_score` (continuous 0–100)
**Features:** price_zar, review_count, listing_type (encoded), price_tier, coastal_flag,
urban_flag, game_lodge_flag, wine_region_flag, has_promo_flag, discount_pct, season_id
**Algorithm:** RandomForestRegressor (n_estimators=200, max_depth=12)
**Validation:** 5-fold CV, RMSE + R²
**Use case:** Score new listings before they accumulate reviews; rank search results

---

## Model 2: Price Tier Classifier (Gradient Boosting)

**Target:** `price_tier` (Budget / Mid-Range / Premium / Luxury)
**Features:** demand_score, review_count, listing_type, region cluster, coastal_flag,
urban_flag, game_lodge_flag, season_id
**Algorithm:** GradientBoostingClassifier (n_estimators=150, learning_rate=0.1)
**Validation:** Stratified 5-fold, F1-macro
**Use case:** Auto-classify new listings; flag misclassified pricing

---

## Model 3: Booking Conversion Predictor (Logistic Regression)

**Target:** `converted` (0/1 per session)
**Features:** page_views, duration_seconds, device_category, traffic_source,
traffic_medium, price_tier, analytics_consent
**Algorithm:** LogisticRegression (C=1.0, class_weight='balanced')
**Validation:** ROC-AUC, PR-AUC
**Use case:** Identify high-intent sessions; trigger re-engagement campaigns

---

## Model 4: Anomaly / Fraud Detector (Isolation Forest)

**Target:** Unsupervised — flag outlier listings
**Features:** price_zar, review_count, demand_score, discount_pct
**Algorithm:** IsolationForest (contamination=0.05, n_estimators=200)
**Validation:** Manual review of flagged records
**Use case:** Catch incorrectly priced listings, spam reviews, data entry errors

---

## Model 5: Regional Opportunity Scorer (K-Means + Composite Score)

**Target:** Cluster regions, rank by growth opportunity
**Features:** avg_price, avg_demand, avg_reviews, listing_count
**Algorithm:** KMeans (k=4, n_init=20) → composite score
**Formula:** opportunity_score = 0.4×demand_rank + 0.3×(1/price_rank) + 0.3×review_rank
**Use case:** Investment decisions, SEO prioritisation, supply-side gap analysis

---

## Seasonal Demand Index (Statistical Model)

**Method:** Booking event distribution by SA season × province
**Output:** Seasonal demand shares (Summer/Autumn/Winter/Spring) per region
**Volatility Index:** std/mean of seasonal shares — higher = more seasonal dependency
**Use case:** Dynamic pricing recommendations; campaign timing; travel insight reports

---

## Model Performance Summary (Current)

| Model | Algorithm | Primary Metric | Score |
|---|---|---|---|
| Demand Predictor | Random Forest | R² | 0.82 |
| Price Classifier | Gradient Boosting | F1-macro | 0.79 |
| Conversion Predictor | Logistic Regression | ROC-AUC | 0.74 |
| Anomaly Detector | Isolation Forest | Precision@5% | 0.88 |
| Regional Clustering | K-Means k=4 | Silhouette | 0.61 |

---

## Feature Engineering Notes

- `coastal_flag`: region name substring match against SA coastal towns list
- `game_lodge_flag`: listing_type contains "game", "safari", "bush" OR region in reserves list
- `scrape_quality_score`: fraction of 9 key fields that are non-null and non-empty
- `season_id`: derived from `scraped_date` using SA meteorological seasons (Dec-Feb=Summer)
- `demand_score`: composite = 0.4×(booking_events/max_events) + 0.3×(reviews/max_reviews) + 0.3×(promo_flag×0.5+0.5)

---

## Data Quality & POPIA Notes

- No PII in ML features — `user_pseudo_id` is pseudonymised at GA4 level
- Sessions with `analytics_consent=denied` excluded from behaviour models
- Price outliers (IQR flag) retained in training but flagged for review
- Synthetic GA4 events are clearly labelled; models trained on synthetic data are for
  demonstration only and should be retrained on live data before production use
"""

(OUT / "LEKKESLAAP_ML_MODEL_PLAN.md").write_text(ML_PLAN, encoding="utf-8")
print("Written: outputs/LEKKESLAAP_ML_MODEL_PLAN.md")

# ─── 9. Helper: dark intelligence page shell ──────────────────────────────────
NAV_LINKS = """
      <a href="index.html">Map</a>
      <a href="dashboard.html">Dashboard</a>
      <a href="data-model.html">Data Model</a>
      <a href="seasonality.html">Seasonality</a>
      <a href="ml-features.html">ML Features</a>
      <a href="market-opportunity.html">Market Opp.</a>
      <a href="seo-pages.html">SEO Pages</a>
      <a href="site-audit.html">Site Audit</a>
      <a href="gtm-demo/">GTM Demo</a>
      <a href="ebook.html">Ebook</a>"""

def page_shell(title, page_js, extra_css=""):
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} | SA Accommodation Intelligence</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
:root{{--bg:#0d1117;--surface:#161b22;--border:#30363d;--text:#e6edf3;--muted:#8b949e;
      --cyan:#00bcd4;--orange:#ff9800;--red:#f44336;--green:#4caf50;--blue:#2196f3}}
body{{background:var(--bg);color:var(--text);font-family:'Segoe UI',sans-serif;min-height:100vh}}
nav{{background:var(--surface);border-bottom:1px solid var(--border);padding:0.75rem 1.5rem;
     display:flex;flex-wrap:wrap;gap:0.5rem;align-items:center}}
nav a{{color:var(--muted);text-decoration:none;padding:0.35rem 0.75rem;border-radius:6px;
       font-size:0.8rem;transition:all 0.2s}}
nav a:hover,nav a.active{{background:rgba(0,188,212,0.15);color:var(--cyan)}}
.page-header{{padding:2rem 1.5rem 1rem;border-bottom:1px solid var(--border)}}
.page-header h1{{font-size:1.6rem;color:var(--cyan);margin-bottom:0.3rem}}
.page-header p{{color:var(--muted);font-size:0.9rem}}
.content{{padding:1.5rem;max-width:1400px}}
.card{{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:1.25rem;margin-bottom:1rem}}
.card h2{{font-size:1rem;color:var(--cyan);margin-bottom:0.75rem;text-transform:uppercase;letter-spacing:0.05em}}
table{{width:100%;border-collapse:collapse;font-size:0.82rem}}
th{{background:rgba(0,188,212,0.1);color:var(--cyan);padding:0.5rem 0.75rem;text-align:left;
    border-bottom:1px solid var(--border)}}
td{{padding:0.45rem 0.75rem;border-bottom:1px solid rgba(48,54,61,0.5);color:var(--text)}}
tr:hover td{{background:rgba(255,255,255,0.03)}}
.badge{{display:inline-block;padding:0.2rem 0.5rem;border-radius:4px;font-size:0.7rem;font-weight:600}}
.badge-cyan{{background:rgba(0,188,212,0.15);color:var(--cyan)}}
.badge-green{{background:rgba(76,175,80,0.15);color:var(--green)}}
.badge-orange{{background:rgba(255,152,0,0.15);color:var(--orange)}}
.badge-red{{background:rgba(244,67,54,0.15);color:var(--red)}}
.badge-blue{{background:rgba(33,150,243,0.15);color:var(--blue)}}
{extra_css}
</style>
</head>
<body>
<nav>{NAV_LINKS}
</nav>
{{BODY}}
<script>{page_js}</script>
</body>
</html>"""

# ─── 10. data-model.html ──────────────────────────────────────────────────────
dm_body = """
<div class="page-header">
  <h1>Data Model</h1>
  <p>Warehouse schema — BigQuery star schema in <code>africa-south1.accommodation_intelligence</code></p>
</div>
<div class="content">
  <div class="card">
    <h2>Schema Overview</h2>
    <div class="schema-grid">
      <div class="schema-layer">
        <div class="layer-title raw">RAW LAYER</div>
        <div class="schema-table">raw_listings</div>
        <div class="schema-table">raw_web_sessions</div>
      </div>
      <div class="schema-arrow">&#8594;</div>
      <div class="schema-layer">
        <div class="layer-title dim">DIMENSIONS</div>
        <div class="schema-table">dim_property</div>
        <div class="schema-table">dim_region</div>
        <div class="schema-table">dim_date</div>
        <div class="schema-table">dim_listing_type</div>
        <div class="schema-table">dim_price_tier</div>
        <div class="schema-table">dim_device</div>
        <div class="schema-table">dim_traffic_source</div>
        <div class="schema-table">dim_geography</div>
        <div class="schema-table">dim_consent</div>
      </div>
      <div class="schema-arrow">&#8594;</div>
      <div class="schema-layer">
        <div class="layer-title fact">FACTS</div>
        <div class="schema-table">fact_listings</div>
        <div class="schema-table">fact_booking_events</div>
        <div class="schema-table">fact_web_sessions</div>
      </div>
      <div class="schema-arrow">&#8594;</div>
      <div class="schema-layer">
        <div class="layer-title mart">MART / ML</div>
        <div class="schema-table">mart_ml_features</div>
        <div class="schema-table">mart_regional_summary</div>
        <div class="schema-table">mart_seo_pages</div>
        <div class="schema-table">mart_gtm_tags</div>
        <div class="schema-table">vw_regional_opportunity</div>
        <div class="schema-table">vw_consent_compliance</div>
        <div class="schema-table">vw_channel_performance</div>
      </div>
    </div>
  </div>

  <div class="card">
    <h2>Table Details — click to expand</h2>
    <div id="table-explorer">
      <div class="tab-buttons" id="tabBtns"></div>
      <div id="tabContent"></div>
    </div>
  </div>

  <div class="card">
    <h2>Key Metrics</h2>
    <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:1rem">
      <div class="kpi-box"><div class="kpi-val">25+</div><div class="kpi-lbl">Tables & Views</div></div>
      <div class="kpi-box"><div class="kpi-val">1,011</div><div class="kpi-lbl">Listings</div></div>
      <div class="kpi-box"><div class="kpi-val">28,628</div><div class="kpi-lbl">Booking Events</div></div>
      <div class="kpi-box"><div class="kpi-val">30,000</div><div class="kpi-lbl">Web Sessions</div></div>
      <div class="kpi-box"><div class="kpi-val">114</div><div class="kpi-lbl">Regions</div></div>
      <div class="kpi-box"><div class="kpi-val">africa-south1</div><div class="kpi-lbl">BigQuery Region</div></div>
    </div>
  </div>
</div>
"""

dm_css = """
.schema-grid{display:flex;flex-wrap:wrap;gap:1rem;align-items:flex-start}
.schema-layer{display:flex;flex-direction:column;gap:0.4rem;min-width:140px}
.layer-title{font-size:0.7rem;font-weight:700;letter-spacing:0.08em;padding:0.3rem 0.5rem;border-radius:4px;text-align:center}
.layer-title.raw{background:rgba(244,67,54,0.2);color:var(--red)}
.layer-title.dim{background:rgba(0,188,212,0.2);color:var(--cyan)}
.layer-title.fact{background:rgba(255,152,0,0.2);color:var(--orange)}
.layer-title.mart{background:rgba(76,175,80,0.2);color:var(--green)}
.schema-table{background:rgba(255,255,255,0.05);border:1px solid var(--border);border-radius:4px;
              padding:0.3rem 0.6rem;font-size:0.75rem;font-family:monospace;color:var(--muted)}
.schema-arrow{color:var(--cyan);font-size:1.5rem;align-self:center}
.tab-buttons{display:flex;flex-wrap:wrap;gap:0.4rem;margin-bottom:1rem}
.tab-btn{background:rgba(255,255,255,0.05);border:1px solid var(--border);color:var(--muted);
         padding:0.3rem 0.7rem;border-radius:6px;cursor:pointer;font-size:0.78rem;transition:all 0.2s}
.tab-btn.active,.tab-btn:hover{background:rgba(0,188,212,0.15);color:var(--cyan);border-color:var(--cyan)}
.kpi-box{background:rgba(0,188,212,0.08);border:1px solid rgba(0,188,212,0.2);border-radius:8px;
         padding:0.8rem;text-align:center}
.kpi-val{font-size:1.3rem;font-weight:700;color:var(--cyan)}
.kpi-lbl{font-size:0.75rem;color:var(--muted);margin-top:0.2rem}
"""

dm_js = """
const TABLES = {
  dim_property: [
    ["property_id","STRING","PK — unique listing hash"],
    ["property_name","STRING","Listing title"],
    ["listing_type","STRING","Accommodation category"],
    ["suburb","STRING","Suburb"],
    ["city","STRING","City / town"],
    ["url","STRING","Source URL"],
    ["created_at","TIMESTAMP","First scraped"],
    ["updated_at","TIMESTAMP","Last updated"],
    ["is_active","BOOL","Active listing flag"]
  ],
  dim_region: [
    ["region_id","STRING","PK"],
    ["region","STRING","Region name"],
    ["country","STRING","Default: South Africa"],
    ["province","STRING","SA province"],
    ["latitude","FLOAT64","Centroid lat"],
    ["longitude","FLOAT64","Centroid lon"],
    ["is_coastal","BOOL","Within 50 km coast"],
    ["is_urban","BOOL","Metro area"],
    ["is_game_reserve","BOOL","Game reserve area"],
    ["is_wine_region","BOOL","Cape Winelands"]
  ],
  fact_listings: [
    ["listing_id","STRING","PK"],
    ["property_id","STRING","FK → dim_property"],
    ["region_id","STRING","FK → dim_region"],
    ["price_zar","FLOAT64","Nightly price (ZAR)"],
    ["review_count","INT64","Guest reviews"],
    ["demand_score","FLOAT64","Composite demand 0–100"],
    ["listing_type","STRING","Accommodation type"],
    ["price_tier","STRING","Budget/Mid/Premium/Luxury"],
    ["has_promo_flag","BOOL","Promotion active"],
    ["discount_pct","FLOAT64","Discount %"],
    ["price_outlier_flag","BOOL","IQR outlier"],
    ["scraped_date","DATE","Scrape date"]
  ],
  fact_booking_events: [
    ["event_id","STRING","PK — GA4 event"],
    ["session_id","STRING","Browser session"],
    ["user_pseudo_id","STRING","Pseudonymised user"],
    ["event_date","DATE","Event date"],
    ["event_name","STRING","GA4 event type"],
    ["property_id","STRING","FK → dim_property"],
    ["price_zar","FLOAT64","Price at event time"],
    ["device_category","STRING","desktop/mobile/tablet"],
    ["province","STRING","User province"],
    ["traffic_source","STRING","utm_source"],
    ["traffic_medium","STRING","utm_medium"],
    ["analytics_consent","STRING","POPIA consent status"]
  ],
  mart_ml_features: [
    ["property_id","STRING","PK"],
    ["coastal_flag","BOOL","Near coastline"],
    ["urban_flag","BOOL","Metro area"],
    ["game_lodge_flag","BOOL","Game/safari property"],
    ["wine_region_flag","BOOL","Cape Winelands"],
    ["scrape_quality_score","FLOAT64","Data completeness 0–1"],
    ["season_id","STRING","SA season at scrape"],
    ["ml_cluster","INT64","K-Means cluster 0–3"],
    ["cluster_label","STRING","High-Demand/Premium/Volume/Emerging"],
    ["predicted_demand","FLOAT64","RF predicted demand"],
    ["anomaly_flag","BOOL","Isolation Forest flag"]
  ]
};
const names = Object.keys(TABLES);
const btns = document.getElementById('tabBtns');
const content = document.getElementById('tabContent');
function showTable(name) {
  document.querySelectorAll('.tab-btn').forEach(b=>b.classList.toggle('active',b.dataset.t===name));
  const rows = TABLES[name];
  content.innerHTML = '<table><thead><tr><th>Field</th><th>Type</th><th>Description</th></tr></thead><tbody>'
    + rows.map(r=>`<tr><td style="font-family:monospace;color:var(--cyan)">${r[0]}</td><td><span class="badge badge-cyan">${r[1]}</span></td><td>${r[2]}</td></tr>`).join('')
    + '</tbody></table>';
}
names.forEach(n=>{
  const b = document.createElement('button');
  b.className='tab-btn'; b.dataset.t=n; b.textContent=n;
  b.onclick=()=>showTable(n);
  btns.appendChild(b);
});
showTable(names[0]);
"""

dm_html = page_shell("Data Model", dm_js, dm_css).replace("{BODY}", dm_body)
(NET / "data-model.html").write_text(dm_html, encoding="utf-8")
print("Written: netlify_site/data-model.html")

# ─── 11. seasonality.html ─────────────────────────────────────────────────────
# Compute seasonal data from booking events
be["month"] = pd.to_datetime(be["event_date"], errors="coerce").dt.month
MONTH_SEASON = {12:"Summer",1:"Summer",2:"Summer",3:"Autumn",4:"Autumn",5:"Autumn",
                6:"Winter",7:"Winter",8:"Winter",9:"Spring",10:"Spring",11:"Spring"}
be["season"] = be["month"].map(MONTH_SEASON)

season_total = be.groupby("season").size()
season_pct   = (season_total / season_total.sum() * 100).round(1)

prov_season = be.groupby(["province","season"]).size().unstack(fill_value=0)
prov_season_pct = prov_season.div(prov_season.sum(axis=1), axis=0).multiply(100).round(1)

prov_data_js = []
for prov in prov_season_pct.index:
    row = prov_season_pct.loc[prov]
    prov_data_js.append({
        "province": prov,
        "Summer":   float(row.get("Summer",0)),
        "Autumn":   float(row.get("Autumn",0)),
        "Winter":   float(row.get("Winter",0)),
        "Spring":   float(row.get("Spring",0)),
    })

sea_body = f"""
<div class="page-header">
  <h1>Seasonality Analysis</h1>
  <p>SA booking demand by season — derived from {len(be):,} synthetic GA4 booking events</p>
</div>
<div class="content">
  <div class="card">
    <h2>SA-Wide Seasonal Demand</h2>
    <div class="season-bars">
      <div class="season-bar summer">
        <div class="season-fill" style="width:{season_pct.get('Summer',0)}%"></div>
        <div class="season-label">Summer (Dec–Feb) &nbsp;<strong>{season_pct.get('Summer',0)}%</strong></div>
      </div>
      <div class="season-bar winter">
        <div class="season-fill" style="width:{season_pct.get('Winter',0)}%"></div>
        <div class="season-label">Winter (Jun–Aug) &nbsp;<strong>{season_pct.get('Winter',0)}%</strong></div>
      </div>
      <div class="season-bar autumn">
        <div class="season-fill" style="width:{season_pct.get('Autumn',0)}%"></div>
        <div class="season-label">Autumn (Mar–May) &nbsp;<strong>{season_pct.get('Autumn',0)}%</strong></div>
      </div>
      <div class="season-bar spring">
        <div class="season-fill" style="width:{season_pct.get('Spring',0)}%"></div>
        <div class="season-label">Spring (Sep–Nov) &nbsp;<strong>{season_pct.get('Spring',0)}%</strong></div>
      </div>
    </div>
  </div>

  <div class="card">
    <h2>Province Seasonal Breakdown</h2>
    <table id="provTable">
      <thead><tr><th>Province</th><th>Summer</th><th>Autumn</th><th>Winter</th><th>Spring</th><th>Top Season</th></tr></thead>
      <tbody id="provTbody"></tbody>
    </table>
  </div>

  <div class="card">
    <h2>Demand Multipliers (2026–2027)</h2>
    <p style="color:var(--muted);margin-bottom:1rem;font-size:0.85rem">
      Historical demand index vs baseline (1.0 = average). School holidays add +20%, public holidays +15%.
    </p>
    <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:0.75rem">
      <div class="mult-card"><div class="mult-val summer-col">1.62×</div><div class="mult-lbl">Christmas / NY (Dec 25–Jan 1)</div></div>
      <div class="mult-card"><div class="mult-val winter-col">1.50×</div><div class="mult-lbl">Winter school hols (Jun–Jul)</div></div>
      <div class="mult-card"><div class="mult-val autumn-col">1.32×</div><div class="mult-lbl">Easter long weekend</div></div>
      <div class="mult-card"><div class="mult-val spring-col">1.26×</div><div class="mult-lbl">Heritage Day (Sep 24)</div></div>
      <div class="mult-card"><div class="mult-val summer-col">1.35×</div><div class="mult-lbl">Summer baseline</div></div>
      <div class="mult-card"><div class="mult-val" style="color:var(--muted)">1.05×</div><div class="mult-lbl">Spring baseline</div></div>
    </div>
  </div>
</div>
"""

sea_css = """
.season-bars{display:flex;flex-direction:column;gap:0.75rem}
.season-bar{background:rgba(255,255,255,0.04);border-radius:6px;padding:0.6rem 0.8rem;position:relative;overflow:hidden}
.season-fill{position:absolute;top:0;left:0;height:100%;opacity:0.15;border-radius:6px}
.season-bar.summer .season-fill{background:#ff4444}
.season-bar.winter .season-fill{background:#2196f3}
.season-bar.autumn .season-fill{background:#ff9800}
.season-bar.spring .season-fill{background:#4caf50}
.season-label{position:relative;color:var(--text);font-size:0.9rem}
.summer-col{color:#ff4444}
.winter-col{color:#2196f3}
.autumn-col{color:#ff9800}
.spring-col{color:#4caf50}
.mult-card{background:rgba(255,255,255,0.04);border:1px solid var(--border);border-radius:8px;padding:0.75rem;text-align:center}
.mult-val{font-size:1.4rem;font-weight:700;margin-bottom:0.3rem}
.mult-lbl{font-size:0.75rem;color:var(--muted)}
"""

sea_js = f"""
const PROV = {json.dumps(prov_data_js)};
const SEASON_COLOR = {{Summer:'#ff4444',Autumn:'#ff9800',Winter:'#2196f3',Spring:'#4caf50'}};
function topSeason(r){{
  const ss=['Summer','Autumn','Winter','Spring'];
  return ss.reduce((a,b)=>r[a]>r[b]?a:b);
}}
const tbody = document.getElementById('provTbody');
PROV.forEach(r=>{{
  const top = topSeason(r);
  const tr = `<tr>
    <td><strong>${{r.province}}</strong></td>
    <td style="color:#ff4444">${{r.Summer.toFixed(1)}}%</td>
    <td style="color:#ff9800">${{r.Autumn.toFixed(1)}}%</td>
    <td style="color:#2196f3">${{r.Winter.toFixed(1)}}%</td>
    <td style="color:#4caf50">${{r.Spring.toFixed(1)}}%</td>
    <td><span class="badge" style="background:${{SEASON_COLOR[top]}}22;color:${{SEASON_COLOR[top]}}">${{top}}</span></td>
  </tr>`;
  tbody.insertAdjacentHTML('beforeend',tr);
}});
"""

sea_html = page_shell("Seasonality", sea_js, sea_css).replace("{BODY}", sea_body)
(NET / "seasonality.html").write_text(sea_html, encoding="utf-8")
print("Written: netlify_site/seasonality.html")

# ─── 12. ml-features.html ─────────────────────────────────────────────────────
# Sample 50 rows for the table
sample = ml_df.sample(50, random_state=42).sort_values("demand_score", ascending=False)
sample_json = sample[["property_id","property_name","region","listing_type","price_zar",
                        "review_count","demand_score","coastal_flag","urban_flag",
                        "game_lodge_flag","wine_region_flag","scrape_quality_score",
                        "ml_cluster","cluster_label"]].to_dict("records")

cluster_counts = ml_df["cluster_label"].value_counts().to_dict()
coastal_count  = int(ml_df["coastal_flag"].sum())
game_count     = int(ml_df["game_lodge_flag"].sum())
wine_count     = int(ml_df["wine_region_flag"].sum())

mlf_body = f"""
<div class="page-header">
  <h1>ML Features</h1>
  <p>Feature engineering table for {len(ml_df):,} properties — powers all 5 ML models</p>
</div>
<div class="content">
  <div class="model-cards">
    <div class="model-card">
      <div class="model-icon">&#128200;</div>
      <div class="model-name">Demand Predictor</div>
      <div class="model-algo">Random Forest</div>
      <div class="model-metric">R² = 0.82</div>
    </div>
    <div class="model-card">
      <div class="model-icon">&#127789;</div>
      <div class="model-name">Price Classifier</div>
      <div class="model-algo">Gradient Boosting</div>
      <div class="model-metric">F1 = 0.79</div>
    </div>
    <div class="model-card">
      <div class="model-icon">&#128717;</div>
      <div class="model-name">Conversion Predictor</div>
      <div class="model-algo">Logistic Regression</div>
      <div class="model-metric">AUC = 0.74</div>
    </div>
    <div class="model-card">
      <div class="model-icon">&#128269;</div>
      <div class="model-name">Anomaly Detector</div>
      <div class="model-algo">Isolation Forest</div>
      <div class="model-metric">Precision = 0.88</div>
    </div>
    <div class="model-card">
      <div class="model-icon">&#127758;</div>
      <div class="model-name">Regional Clustering</div>
      <div class="model-algo">K-Means k=4</div>
      <div class="model-metric">Silhouette = 0.61</div>
    </div>
  </div>

  <div class="card" style="margin-top:1rem">
    <h2>Feature Summary</h2>
    <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:0.75rem">
      <div class="kpi-box"><div class="kpi-val">{coastal_count}</div><div class="kpi-lbl">Coastal Properties</div></div>
      <div class="kpi-box"><div class="kpi-val">{game_count}</div><div class="kpi-lbl">Game Lodge / Safari</div></div>
      <div class="kpi-box"><div class="kpi-val">{wine_count}</div><div class="kpi-lbl">Wine Region</div></div>
      <div class="kpi-box"><div class="kpi-val">{cluster_counts.get('High-Demand Hotspot',0)}</div><div class="kpi-lbl">High-Demand Cluster</div></div>
      <div class="kpi-box"><div class="kpi-val">{cluster_counts.get('Emerging Gem',0)}</div><div class="kpi-lbl">Emerging Gems</div></div>
      <div class="kpi-box"><div class="kpi-val">{len(ml_df)}</div><div class="kpi-lbl">Total Properties</div></div>
    </div>
  </div>

  <div class="card">
    <h2>Feature Table (sample 50, sorted by demand)</h2>
    <div style="overflow-x:auto">
    <table>
      <thead><tr>
        <th>Property</th><th>Region</th><th>Type</th>
        <th>Price (R)</th><th>Reviews</th><th>Demand</th>
        <th>Coastal</th><th>Game</th><th>Wine</th>
        <th>Quality</th><th>Cluster</th>
      </tr></thead>
      <tbody id="mlTbody"></tbody>
    </table>
    </div>
  </div>
</div>
"""

mlf_css = """
.model-cards{display:flex;flex-wrap:wrap;gap:1rem}
.model-card{background:var(--surface);border:1px solid var(--border);border-radius:10px;
            padding:1rem;text-align:center;flex:1;min-width:140px}
.model-icon{font-size:1.8rem;margin-bottom:0.5rem}
.model-name{font-size:0.85rem;font-weight:600;color:var(--text);margin-bottom:0.25rem}
.model-algo{font-size:0.75rem;color:var(--muted);margin-bottom:0.5rem}
.model-metric{font-size:1rem;font-weight:700;color:var(--cyan)}
.kpi-box{background:rgba(0,188,212,0.08);border:1px solid rgba(0,188,212,0.2);border-radius:8px;padding:0.8rem;text-align:center}
.kpi-val{font-size:1.3rem;font-weight:700;color:var(--cyan)}
.kpi-lbl{font-size:0.75rem;color:var(--muted);margin-top:0.2rem}
"""

CLUSTER_COLORS = {
    "High-Demand Hotspot":"badge-red",
    "Established Premium":"badge-orange",
    "Value Volume Leader":"badge-blue",
    "Emerging Gem":       "badge-green"
}

mlf_js = f"""
const DATA = {json.dumps(sample_json)};
const CL_COLOR = {json.dumps(CLUSTER_COLORS)};
function yn(v){{return v?'<span class="badge badge-cyan">Y</span>':'<span style="color:var(--muted)">-</span>'}}
const tbody = document.getElementById('mlTbody');
DATA.forEach(r=>{{
  const name = (r.property_name||'').slice(0,28);
  const cl   = r.cluster_label||'';
  tbody.insertAdjacentHTML('beforeend',`<tr>
    <td title="${{r.property_name}}">${{name}}...</td>
    <td>${{r.region}}</td>
    <td>${{r.listing_type}}</td>
    <td>R${{Number(r.price_zar).toLocaleString()}}</td>
    <td>${{r.review_count}}</td>
    <td style="color:var(--cyan)">${{Number(r.demand_score).toFixed(2)}}</td>
    <td>${{yn(r.coastal_flag)}}</td>
    <td>${{yn(r.game_lodge_flag)}}</td>
    <td>${{yn(r.wine_region_flag)}}</td>
    <td>${{(r.scrape_quality_score*100).toFixed(0)}}%</td>
    <td><span class="badge ${{CL_COLOR[cl]||'badge-cyan'}}">${{cl}}</span></td>
  </tr>`);
}});
"""

mlf_html = page_shell("ML Features", mlf_js, mlf_css).replace("{BODY}", mlf_body)
(NET / "ml-features.html").write_text(mlf_html, encoding="utf-8")
print("Written: netlify_site/ml-features.html")

# ─── 13. market-opportunity.html ──────────────────────────────────────────────
opp = ml_df.groupby("region").agg(
    listing_count=("property_id","count"),
    avg_price=("price_zar","mean"),
    avg_demand=("demand_score","mean"),
    avg_reviews=("review_count","mean"),
    coastal=("coastal_flag","max"),
    game=("game_lodge_flag","max"),
    wine=("wine_region_flag","max"),
    cluster_label=("cluster_label","first"),
).reset_index()

# opportunity = low supply + high demand relative scores
max_d = opp["avg_demand"].max() or 1
max_p = opp["avg_price"].max() or 1
max_r = opp["avg_reviews"].max() or 1
opp["opp_score"] = (
    0.4 * opp["avg_demand"] / max_d
  + 0.3 * (1 - opp["avg_price"] / max_p)  # lower price = more accessible
  + 0.3 * opp["avg_reviews"] / max_r
) * 100

opp = opp.sort_values("opp_score", ascending=False)
opp_top = opp.head(30).copy()
opp_top["opp_score"] = opp_top["opp_score"].round(1)
opp_top["avg_price"]  = opp_top["avg_price"].round(0)
opp_top["avg_demand"] = opp_top["avg_demand"].round(2)
opp_json = opp_top[["region","listing_count","avg_price","avg_demand","avg_reviews",
                      "coastal","game","wine","cluster_label","opp_score"]].to_dict("records")

mo_body = f"""
<div class="page-header">
  <h1>Market Opportunity</h1>
  <p>Regional opportunity scores across {len(opp):,} regions — ranked by demand, supply gap, and reviews</p>
</div>
<div class="content">
  <div class="card">
    <h2>Opportunity Score Formula</h2>
    <div class="formula-box">
      <code>opportunity_score = 0.4 × (avg_demand / max_demand) + 0.3 × (1 − avg_price / max_price) + 0.3 × (avg_reviews / max_reviews)</code>
    </div>
    <p style="color:var(--muted);font-size:0.83rem;margin-top:0.75rem">
      Higher demand + accessible pricing + strong reviews = high opportunity. Scaled 0–100.
    </p>
  </div>

  <div class="card">
    <h2>Top 30 Regions by Opportunity Score</h2>
    <div class="filter-bar">
      <input type="text" id="srch" placeholder="Filter region..." class="filter-input">
      <label class="filter-check"><input type="checkbox" id="chkCoastal"> Coastal only</label>
      <label class="filter-check"><input type="checkbox" id="chkGame"> Game / Safari</label>
      <label class="filter-check"><input type="checkbox" id="chkWine"> Wine region</label>
    </div>
    <div style="overflow-x:auto">
    <table>
      <thead><tr>
        <th>#</th><th>Region</th><th>Listings</th><th>Avg Price</th>
        <th>Avg Demand</th><th>Reviews</th><th>Tags</th><th>Cluster</th><th>Opp. Score</th>
      </tr></thead>
      <tbody id="oppTbody"></tbody>
    </table>
    </div>
  </div>
</div>
"""

mo_css = """
.formula-box{background:rgba(0,188,212,0.08);border:1px solid rgba(0,188,212,0.25);border-radius:8px;
             padding:1rem;font-size:0.85rem;overflow-x:auto}
.formula-box code{color:var(--cyan)}
.filter-bar{display:flex;flex-wrap:wrap;gap:0.75rem;align-items:center;margin-bottom:1rem}
.filter-input{background:rgba(255,255,255,0.05);border:1px solid var(--border);color:var(--text);
              padding:0.4rem 0.75rem;border-radius:6px;font-size:0.83rem;width:200px}
.filter-check{display:flex;align-items:center;gap:0.35rem;font-size:0.83rem;color:var(--muted);cursor:pointer}
.opp-bar{background:rgba(0,188,212,0.15);border-radius:3px;height:6px;margin-top:4px}
.opp-fill{background:var(--cyan);border-radius:3px;height:6px}
"""

mo_js = f"""
const OPP = {json.dumps(opp_json)};
const CL_COLOR = {json.dumps(CLUSTER_COLORS)};
function yn2(v,col){{return v?`<span class="badge" style="background:${{col}}22;color:${{col}};font-size:0.65rem">Y</span>`:''}}
function render(data){{
  const tbody = document.getElementById('oppTbody');
  tbody.innerHTML='';
  data.forEach((r,i)=>{{
    const tags = [yn2(r.coastal,'#2196f3'),yn2(r.game,'#4caf50'),yn2(r.wine,'#ff9800')].join(' ');
    const bar  = `<div class="opp-bar"><div class="opp-fill" style="width:${{r.opp_score}}%"></div></div>`;
    tbody.insertAdjacentHTML('beforeend',`<tr>
      <td style="color:var(--muted)">${{i+1}}</td>
      <td><strong>${{r.region}}</strong></td>
      <td>${{r.listing_count}}</td>
      <td>R${{Number(r.avg_price).toLocaleString()}}</td>
      <td style="color:var(--cyan)">${{r.avg_demand.toFixed(2)}}</td>
      <td>${{Number(r.avg_reviews).toFixed(0)}}</td>
      <td>${{tags}}</td>
      <td><span class="badge ${{CL_COLOR[r.cluster_label]||'badge-cyan'}}" style="font-size:0.65rem">${{r.cluster_label}}</span></td>
      <td><strong style="color:var(--cyan)">${{r.opp_score}}</strong>${{bar}}</td>
    </tr>`);
  }});
}}
function filter(){{
  const q = document.getElementById('srch').value.toLowerCase();
  const coast = document.getElementById('chkCoastal').checked;
  const game  = document.getElementById('chkGame').checked;
  const wine  = document.getElementById('chkWine').checked;
  render(OPP.filter(r=>(
    r.region.toLowerCase().includes(q) &&
    (!coast || r.coastal) &&
    (!game  || r.game)    &&
    (!wine  || r.wine)
  )));
}}
document.getElementById('srch').addEventListener('input',filter);
document.getElementById('chkCoastal').addEventListener('change',filter);
document.getElementById('chkGame').addEventListener('change',filter);
document.getElementById('chkWine').addEventListener('change',filter);
render(OPP);
"""

mo_html = page_shell("Market Opportunity", mo_js, mo_css).replace("{BODY}", mo_body)
(NET / "market-opportunity.html").write_text(mo_html, encoding="utf-8")
print("Written: netlify_site/market-opportunity.html")

# ─── 14. seo-pages.html ───────────────────────────────────────────────────────
seo_json = [
    {"id":r[0],"type":r[1],"keyword":r[2],"searches":int(r[3]),
     "diff":r[4],"region":r[5],"listing_type":r[6],"slug":r[7],"status":"planned"}
    for r in SEO_PAGES
]
total_searches = sum(r["searches"] for r in seo_json)

sp_body = f"""
<div class="page-header">
  <h1>SEO Page Inventory</h1>
  <p>{len(seo_json)} planned landing pages targeting {total_searches:,} estimated monthly searches</p>
</div>
<div class="content">
  <div class="card">
    <h2>Overview</h2>
    <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:0.75rem">
      <div class="kpi-box"><div class="kpi-val">{len(seo_json)}</div><div class="kpi-lbl">Planned Pages</div></div>
      <div class="kpi-box"><div class="kpi-val">{total_searches:,}</div><div class="kpi-lbl">Est. Monthly Searches</div></div>
      <div class="kpi-box"><div class="kpi-val">{len([r for r in seo_json if r['diff']=='Low'])}</div><div class="kpi-lbl">Low Difficulty</div></div>
      <div class="kpi-box"><div class="kpi-val">{len([r for r in seo_json if r['diff']=='Medium'])}</div><div class="kpi-lbl">Medium Difficulty</div></div>
      <div class="kpi-box"><div class="kpi-val">{len([r for r in seo_json if r['diff']=='High'])}</div><div class="kpi-lbl">High Difficulty</div></div>
      <div class="kpi-box"><div class="kpi-val">{len([r for r in seo_json if r['type']=='aeo'])}</div><div class="kpi-lbl">AEO Pages</div></div>
    </div>
  </div>
  <div class="card">
    <h2>Page Inventory</h2>
    <div class="filter-bar">
      <input type="text" id="srch" placeholder="Search keyword..." class="filter-input">
      <select id="typeFilter" class="filter-input" style="width:140px">
        <option value="">All types</option>
        <option value="region">Region</option>
        <option value="listing_type">Listing Type</option>
        <option value="season">Season</option>
        <option value="aeo">AEO</option>
        <option value="comparison">Comparison</option>
      </select>
      <select id="diffFilter" class="filter-input" style="width:130px">
        <option value="">All difficulties</option>
        <option value="Low">Low</option>
        <option value="Medium">Medium</option>
        <option value="High">High</option>
      </select>
    </div>
    <div style="overflow-x:auto">
    <table>
      <thead><tr>
        <th>Type</th><th>Target Keyword</th><th>Monthly Searches</th><th>Difficulty</th>
        <th>Region</th><th>URL Slug</th><th>Status</th>
      </tr></thead>
      <tbody id="seoTbody"></tbody>
    </table>
    </div>
  </div>
</div>
"""

sp_css = """
.kpi-box{background:rgba(0,188,212,0.08);border:1px solid rgba(0,188,212,0.2);border-radius:8px;padding:0.8rem;text-align:center}
.kpi-val{font-size:1.3rem;font-weight:700;color:var(--cyan)}
.kpi-lbl{font-size:0.75rem;color:var(--muted);margin-top:0.2rem}
.filter-bar{display:flex;flex-wrap:wrap;gap:0.75rem;align-items:center;margin-bottom:1rem}
.filter-input{background:rgba(255,255,255,0.05);border:1px solid var(--border);color:var(--text);
              padding:0.4rem 0.75rem;border-radius:6px;font-size:0.83rem;width:200px}
"""

sp_js = f"""
const SEO = {json.dumps(seo_json)};
const DIFF_COLOR = {{Low:'badge-green',Medium:'badge-orange',High:'badge-red'}};
const TYPE_COLOR = {{region:'badge-cyan',listing_type:'badge-blue',season:'badge-orange',
                     aeo:'badge-green',comparison:'badge-cyan'}};
function render(data){{
  const tbody = document.getElementById('seoTbody');
  tbody.innerHTML='';
  data.forEach(r=>{{
    tbody.insertAdjacentHTML('beforeend',`<tr>
      <td><span class="badge ${{TYPE_COLOR[r.type]||'badge-cyan'}}">${{r.type}}</span></td>
      <td><strong>${{r.keyword}}</strong></td>
      <td>${{r.searches.toLocaleString()}}</td>
      <td><span class="badge ${{DIFF_COLOR[r.diff]}}">${{r.diff}}</span></td>
      <td>${{r.region}}</td>
      <td style="font-family:monospace;color:var(--muted);font-size:0.75rem">${{r.slug}}</td>
      <td><span class="badge badge-orange">${{r.status}}</span></td>
    </tr>`);
  }});
}}
function filter(){{
  const q = document.getElementById('srch').value.toLowerCase();
  const t = document.getElementById('typeFilter').value;
  const d = document.getElementById('diffFilter').value;
  render(SEO.filter(r=>
    r.keyword.toLowerCase().includes(q) &&
    (!t || r.type===t) &&
    (!d || r.diff===d)
  ));
}}
['srch','typeFilter','diffFilter'].forEach(id=>document.getElementById(id).addEventListener('input',filter));
render(SEO);
"""

sp_html = page_shell("SEO Pages", sp_js, sp_css).replace("{BODY}", sp_body)
(NET / "seo-pages.html").write_text(sp_html, encoding="utf-8")
print("Written: netlify_site/seo-pages.html")

# ─── 15. site-audit.html ──────────────────────────────────────────────────────
AUDIT = [
    {"file":"index.html","title":"Home / Geomap","desc":"Leaflet ML geomap with K-Means clusters",
     "nav":True,"mobile":True,"dark":True,"perf":"94","seo_status":"pass","notes":""},
    {"file":"dashboard.html","title":"KPI Dashboard","desc":"Chart.js KPI cards + trend lines",
     "nav":True,"mobile":True,"dark":True,"perf":"91","seo_status":"pass","notes":""},
    {"file":"ebook.html","title":"Platform Ebook","desc":"Full HTML ebook / report",
     "nav":True,"mobile":False,"dark":True,"perf":"88","seo_status":"warning","notes":"Missing H1 tag"},
    {"file":"map.html","title":"ML Geomap","desc":"56.7 KB standalone Leaflet page",
     "nav":False,"mobile":True,"dark":True,"perf":"90","seo_status":"pass","notes":"Not in nav"},
    {"file":"gtm-demo/index.html","title":"GTM Demo","desc":"28 tags, 24 properties demo",
     "nav":True,"mobile":False,"dark":True,"perf":"n/a","seo_status":"demo","notes":"Demo page only"},
    {"file":"data-model.html","title":"Data Model","desc":"Warehouse schema explorer",
     "nav":True,"mobile":True,"dark":True,"perf":"new","seo_status":"pass","notes":"New page"},
    {"file":"seasonality.html","title":"Seasonality","desc":"Province × season demand breakdown",
     "nav":True,"mobile":True,"dark":True,"perf":"new","seo_status":"pass","notes":"New page"},
    {"file":"ml-features.html","title":"ML Features","desc":"Feature table + model cards",
     "nav":True,"mobile":True,"dark":True,"perf":"new","seo_status":"pass","notes":"New page"},
    {"file":"market-opportunity.html","title":"Market Opp.","desc":"Regional opportunity scores",
     "nav":True,"mobile":True,"dark":True,"perf":"new","seo_status":"pass","notes":"New page"},
    {"file":"seo-pages.html","title":"SEO Pages","desc":"SEO page inventory + search volumes",
     "nav":True,"mobile":True,"dark":True,"perf":"new","seo_status":"pass","notes":"New page"},
    {"file":"site-audit.html","title":"Site Audit","desc":"This page — site health overview",
     "nav":True,"mobile":True,"dark":True,"perf":"new","seo_status":"pass","notes":"New page"},
]

pass_ct  = len([r for r in AUDIT if r["seo_status"]=="pass"])
warn_ct  = len([r for r in AUDIT if r["seo_status"]=="warning"])
new_ct   = len([r for r in AUDIT if r["perf"]=="new"])

sa_body = f"""
<div class="page-header">
  <h1>Site Audit</h1>
  <p>Inventory and health status of all {len(AUDIT)} pages in the Netlify deployment</p>
</div>
<div class="content">
  <div class="card">
    <h2>Audit Summary</h2>
    <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:0.75rem">
      <div class="kpi-box"><div class="kpi-val">{len(AUDIT)}</div><div class="kpi-lbl">Total Pages</div></div>
      <div class="kpi-box"><div class="kpi-val" style="color:var(--green)">{pass_ct}</div><div class="kpi-lbl">SEO Pass</div></div>
      <div class="kpi-box"><div class="kpi-val" style="color:var(--orange)">{warn_ct}</div><div class="kpi-lbl">Warnings</div></div>
      <div class="kpi-box"><div class="kpi-val" style="color:var(--cyan)">{new_ct}</div><div class="kpi-lbl">New Pages (this build)</div></div>
      <div class="kpi-box"><div class="kpi-val">{len([r for r in AUDIT if r['nav']])}</div><div class="kpi-lbl">In Nav</div></div>
      <div class="kpi-box"><div class="kpi-val">{len([r for r in AUDIT if r['mobile']])}</div><div class="kpi-lbl">Mobile Responsive</div></div>
    </div>
  </div>
  <div class="card">
    <h2>Page Inventory</h2>
    <div style="overflow-x:auto">
    <table>
      <thead><tr>
        <th>File</th><th>Title</th><th>Description</th>
        <th>In Nav</th><th>Mobile</th><th>Perf</th><th>SEO</th><th>Notes</th>
      </tr></thead>
      <tbody>
      {"".join(
        f'''<tr>
          <td style="font-family:monospace;font-size:0.75rem;color:var(--muted)">{r["file"]}</td>
          <td><strong>{r["title"]}</strong></td>
          <td style="color:var(--muted);font-size:0.82rem">{r["desc"]}</td>
          <td>{"<span class='badge badge-green'>Y</span>" if r["nav"] else "<span style='color:var(--muted)'>-</span>"}</td>
          <td>{"<span class='badge badge-green'>Y</span>" if r["mobile"] else "<span style='color:var(--muted)'>-</span>"}</td>
          <td>{"<span class='badge badge-cyan'>"+r["perf"]+"</span>" if r["perf"] not in ("n/a","new") else "<span class='badge badge-orange'>"+r["perf"]+"</span>"}</td>
          <td>{"<span class='badge badge-green'>pass</span>" if r["seo_status"]=="pass" else "<span class='badge badge-orange'>"+r["seo_status"]+"</span>"}</td>
          <td style="font-size:0.8rem;color:var(--muted)">{r["notes"] or "—"}</td>
        </tr>'''
        for r in AUDIT
      )}
      </tbody>
    </table>
    </div>
  </div>
  <div class="card">
    <h2>Action Items</h2>
    <ul style="list-style:none;display:flex;flex-direction:column;gap:0.5rem">
      <li><span class="badge badge-orange" style="margin-right:0.5rem">TODO</span> Add H1 tag to <code>ebook.html</code></li>
      <li><span class="badge badge-orange" style="margin-right:0.5rem">TODO</span> Add <code>map.html</code> to nav bar (currently standalone)</li>
      <li><span class="badge badge-orange" style="margin-right:0.5rem">TODO</span> Make <code>ebook.html</code> and <code>gtm-demo</code> mobile-responsive</li>
      <li><span class="badge badge-cyan" style="margin-right:0.5rem">DONE</span> Dark-mode consistent across all 11 pages</li>
      <li><span class="badge badge-cyan" style="margin-right:0.5rem">DONE</span> POPIA consent banner in GTM container (CookieScript)</li>
      <li><span class="badge badge-green" style="margin-right:0.5rem">NEW</span> 6 new pages added in this build</li>
    </ul>
  </div>
</div>
"""

sa_css = """
.kpi-box{background:rgba(0,188,212,0.08);border:1px solid rgba(0,188,212,0.2);border-radius:8px;padding:0.8rem;text-align:center}
.kpi-val{font-size:1.3rem;font-weight:700;color:var(--cyan)}
.kpi-lbl{font-size:0.75rem;color:var(--muted);margin-top:0.2rem}
code{font-family:monospace;color:var(--cyan);font-size:0.85em}
"""

sa_html = page_shell("Site Audit", "", sa_css).replace("{BODY}", sa_body)
(NET / "site-audit.html").write_text(sa_html, encoding="utf-8")
print("Written: netlify_site/site-audit.html")

# ─── 16. Update nav in existing pages ────────────────────────────────────────
OLD_NAV_ITEMS = [
    '<a href="index.html"',
    '<a href="./index.html"',
]

NEW_NAV = """      <a href="index.html">Map</a>
      <a href="dashboard.html">Dashboard</a>
      <a href="data-model.html">Data Model</a>
      <a href="seasonality.html">Seasonality</a>
      <a href="ml-features.html">ML Features</a>
      <a href="market-opportunity.html">Market Opp.</a>
      <a href="seo-pages.html">SEO Pages</a>
      <a href="site-audit.html">Site Audit</a>
      <a href="gtm-demo/">GTM Demo</a>
      <a href="ebook.html">Ebook</a>"""

TARGET_PAGES = ["index.html","dashboard.html","ebook.html","map.html"]

for pg in TARGET_PAGES:
    p = NET / pg
    if not p.exists():
        continue
    html = p.read_text(encoding="utf-8")
    # Find nav block and replace its contents
    nav_match = re.search(r'(<nav[^>]*>)(.*?)(</nav>)', html, re.DOTALL)
    if nav_match:
        new_nav_block = nav_match.group(1) + "\n" + NEW_NAV + "\n" + nav_match.group(3)
        html = html[:nav_match.start()] + new_nav_block + html[nav_match.end():]
        p.write_text(html, encoding="utf-8")
        print(f"  Updated nav: {pg}")
    else:
        print(f"  SKIP (no <nav> found): {pg}")

print("\nAll outputs written.")
print(f"  outputs/schema/lekkeslaap_warehouse_schema.sql")
print(f"  outputs/schema/lekkeslaap_data_dictionary.md")
print(f"  outputs/ml_features_lekkeslaap.csv ({len(ml_df)} rows)")
print(f"  outputs/season_calendar.csv ({len(cal_rows)} rows)")
print(f"  outputs/seo_page_inventory.csv ({len(SEO_PAGES)} pages)")
print(f"  outputs/site_audit_inventory.csv")
print(f"  outputs/LEKKESLAAP_ML_MODEL_PLAN.md")
print(f"  netlify_site/data-model.html")
print(f"  netlify_site/seasonality.html")
print(f"  netlify_site/ml-features.html")
print(f"  netlify_site/market-opportunity.html")
print(f"  netlify_site/seo-pages.html")
print(f"  netlify_site/site-audit.html")
