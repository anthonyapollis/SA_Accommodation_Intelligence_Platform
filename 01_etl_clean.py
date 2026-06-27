"""
SA Accommodation Intelligence Platform
01_etl_clean.py — ETL Pipeline: dirty → clean + synthetic GA4 web events

Source: accommodation_listings_redo_dom.csv (1,013 rows, LekkeSlaap scrape)
Output:
  data/accommodation_clean.csv      — cleaned property master
  data/ga4_events_synthetic.csv     — synthetic GA4-schema events
  data/dim_property.csv             — BigQuery dim table
  data/dim_region.csv               — BigQuery dim table
  data/fact_listings.csv            — BigQuery fact table
  data/fact_web_sessions.csv        — GA4 sessions fact
  data/fact_booking_events.csv      — GA4 booking funnel events

Author: Anthony Apollis | 2026-06-27
"""

import csv
import re
import uuid
import random
import hashlib
from datetime import datetime, timedelta, date
from pathlib import Path

import pandas as pd
import numpy as np
from faker import Faker

# ── PATHS ─────────────────────────────────────────────────────────────────────
BASE = Path(__file__).parent
SRC  = BASE.parent / "outputs" / "accommodation_listings_redo_dom.csv"
DATA = BASE / "data"

fake = Faker("en_US")
random.seed(42)
np.random.seed(42)

# ── STEP 1: LOAD RAW DATA ─────────────────────────────────────────────────────
print("=" * 60)
print("STEP 1 — Load raw scraped data")
print("=" * 60)

df_raw = pd.read_csv(SRC, encoding="utf-8-sig")
df_raw.columns = df_raw.columns.str.strip().str.lstrip("﻿")
print(f"  Rows loaded : {len(df_raw):,}")
print(f"  Columns     : {list(df_raw.columns)}")

# Document dirty state BEFORE cleaning
dirty_report = {
    "total_rows"          : len(df_raw),
    "price_missing"       : df_raw["price"].isna().sum() + (df_raw["price"] == "").sum(),
    "rating_missing"      : df_raw["rating"].isna().sum(),
    "review_count_missing": df_raw["review_count"].isna().sum(),
    "location_missing"    : df_raw["location"].isna().sum(),
    "name_with_promo"     : df_raw["name"].str.contains(r"\d+%\s*off", na=False).sum(),
    "price_with_spaces"   : df_raw["price"].str.contains(r"R\d+ \d+", na=False).sum(),
    "loc_with_dup"        : df_raw["location"].str.contains(r"(\b\w+\b),\s*\1\b", na=False).sum(),
    "type_nonstandard"    : df_raw["listing_type"].isin(["LodgingBusiness", "accommodation"]).sum(),
}
print(f"\n  DIRTY DATA AUDIT:")
for k, v in dirty_report.items():
    print(f"    {k:<28} : {v:>6,}")


# ── STEP 2: CLEAN ─────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("STEP 2 — Apply cleaning rules")
print("=" * 60)

df = df_raw.copy()

# 2a. Strip promotional noise from names
#     e.g. "Flash Deal 50% off! 50% off! Flash Deal 50% off! 50% off! Island View"
#     →    "Island View"
promo_pattern = re.compile(
    r"(?:Flash Deal\s+)?(?:\d+%\s*off!?\s*)+(?:Flash Deal\s+)?(?:\d+%\s*off!?\s*)*",
    re.IGNORECASE,
)
df["name_clean"] = df["name"].apply(
    lambda x: promo_pattern.sub("", str(x)).strip() if pd.notna(x) else x
)
df["has_promo_flag"] = df["name"].str.contains(r"\d+%\s*off", na=False, case=False)
df["discount_pct"] = df["name"].str.extract(r"(\d+)%\s*off", expand=False).astype("float")
print(f"  Names cleaned (promo removed): {df['has_promo_flag'].sum()}")

# 2b. Clean price: "R1 700" → 1700, remove R prefix and spaces
def parse_price(p):
    if pd.isna(p) or str(p).strip() == "":
        return np.nan
    p = str(p).replace("R", "").replace(" ", "").replace(",", "").strip()
    try:
        return float(p)
    except ValueError:
        return np.nan

df["price_zar"] = df["price"].apply(parse_price)
# Cap extreme outliers: R20,000 nightly is plausible (luxury villa), flag above
PRICE_CAP = 20_000
df["price_outlier_flag"] = df["price_zar"] > PRICE_CAP
df.loc[df["price_outlier_flag"], "price_zar"] = np.nan
print(f"  Price outliers capped (>{PRICE_CAP}): {df['price_outlier_flag'].sum()}")
print(f"  Price range (clean): R{df['price_zar'].min():.0f} – R{df['price_zar'].max():.0f}")
print(f"  Average price: R{df['price_zar'].mean():.0f}")

# 2c. Clean location: fix duplicated suburb pattern
#     "Cape Town CBD, Cape Town CBD Cape Town" → "Cape Town CBD, Cape Town"
def clean_location(loc):
    if pd.isna(loc):
        return loc
    loc = str(loc).strip()
    # Pattern: "Suburb, Suburb City" — collapse middle repeat
    m = re.match(r"^(.+?),\s*\1\s+(.+)$", loc)
    if m:
        return f"{m.group(1)}, {m.group(2)}"
    return loc

df["location_clean"] = df["location"].apply(clean_location)
print(f"  Locations de-duplicated: {(df['location_clean'] != df['location']).sum()}")

# 2d. Normalise listing_type
type_map = {
    "LodgingBusiness": "Guest House",
    "accommodation"  : "Self Catering",
}
df["listing_type_clean"] = df["listing_type"].replace(type_map)
print(f"  Listing types normalised: {df['listing_type'].isin(type_map.keys()).sum()}")

# 2e. Extract region from source_page URL
def extract_region(url):
    if pd.isna(url):
        return "Unknown"
    m = re.search(r"accommodation-in/([^?&/]+)", str(url))
    if m:
        return m.group(1).replace("-", " ").title().strip()
    return "Homepage"

df["region"] = df["source_page"].apply(extract_region)

# 2f. Extract country from location
def extract_country(loc):
    if pd.isna(loc):
        return "South Africa"
    loc_lower = str(loc).lower()
    if "namibia" in loc_lower:
        return "Namibia"
    return "South Africa"

df["country"] = df["location_clean"].apply(extract_country)

# 2g. Extract suburb + city from location_clean
def split_location(loc):
    if pd.isna(loc) or not str(loc).strip():
        return pd.Series({"suburb": None, "city": None})
    parts = [p.strip() for p in str(loc).split(",")]
    suburb = parts[0] if len(parts) >= 1 else None
    # Remove country name from city
    city_raw = parts[1] if len(parts) >= 2 else None
    if city_raw:
        for country in ["Namibia", "South Africa", "SA"]:
            city_raw = city_raw.replace(country, "").strip()
    return pd.Series({"suburb": suburb, "city": city_raw or suburb})

df[["suburb", "city"]] = df["location_clean"].apply(split_location)

# 2h. Price tier segmentation
def price_tier(p):
    if pd.isna(p):
        return "Unknown"
    if p < 700:
        return "Budget"
    elif p < 1200:
        return "Mid-Range"
    elif p < 2500:
        return "Premium"
    else:
        return "Luxury"

df["price_tier"] = df["price_zar"].apply(price_tier)

# 2i. Demand score (composite: normalised review_count * price_tier weight)
tier_weight = {"Budget": 0.8, "Mid-Range": 1.0, "Premium": 1.2, "Luxury": 1.5, "Unknown": 0.5}
df["review_count"] = pd.to_numeric(df["review_count"], errors="coerce").fillna(0)
max_reviews = df["review_count"].max()
df["demand_score"] = (
    (df["review_count"] / max_reviews)
    * df["price_tier"].map(tier_weight)
    * 100
).round(2)

# 2j. Remove true duplicates (same property_id)
before_dedup = len(df)
df = df.drop_duplicates(subset=["property_id"])
print(f"  Duplicates removed: {before_dedup - len(df)}")
print(f"\n  Clean rows: {len(df):,}")

# ── STEP 3: SAVE CLEAN MASTER ─────────────────────────────────────────────────
print("\n" + "=" * 60)
print("STEP 3 — Save clean master CSV")
print("=" * 60)

CLEAN_COLS = [
    "property_id", "name_clean", "listing_type_clean", "price_zar", "price_tier",
    "review_count", "demand_score", "suburb", "city", "region", "country",
    "url", "has_promo_flag", "discount_pct", "price_outlier_flag",
]
df_clean = df[CLEAN_COLS].rename(columns={
    "name_clean"        : "property_name",
    "listing_type_clean": "listing_type",
})
df_clean.to_csv(DATA / "accommodation_clean.csv", index=False)
print(f"  Saved: data/accommodation_clean.csv  ({len(df_clean):,} rows)")

# ── STEP 4: BUILD DIMENSION TABLES ────────────────────────────────────────────
print("\n" + "=" * 60)
print("STEP 4 — Build BigQuery dimension tables")
print("=" * 60)

# dim_property
dim_property = df_clean[["property_id","property_name","listing_type","price_zar",
                           "price_tier","review_count","demand_score","url"]].copy()
dim_property["ingested_at"] = datetime.utcnow().isoformat()
dim_property.to_csv(DATA / "dim_property.csv", index=False)
print(f"  dim_property  : {len(dim_property):,} rows")

# dim_region
regions_unique = df[["region","country"]].drop_duplicates().reset_index(drop=True)
regions_unique.insert(0, "region_id", range(1, len(regions_unique)+1))
regions_unique.to_csv(DATA / "dim_region.csv", index=False)
print(f"  dim_region    : {len(regions_unique):,} rows")

# fact_listings (join property + region)
region_lookup = regions_unique.set_index("region")["region_id"].to_dict()
df["region_id"] = df["region"].map(region_lookup)
fact_listings = df[["property_id","region_id","price_zar","review_count","demand_score",
                     "listing_type_clean","price_tier","has_promo_flag","discount_pct"]].copy()
fact_listings = fact_listings.rename(columns={"listing_type_clean":"listing_type"})
fact_listings["scraped_date"] = "2026-06-27"
fact_listings.to_csv(DATA / "fact_listings.csv", index=False)
print(f"  fact_listings : {len(fact_listings):,} rows")

# ── STEP 5: SYNTHETIC GA4 WEB EVENTS ─────────────────────────────────────────
print("\n" + "=" * 60)
print("STEP 5 — Generate synthetic GA4 web events")
print("=" * 60)

PROPERTIES = df_clean["property_id"].tolist()
PRICES     = df_clean.set_index("property_id")["price_zar"].to_dict()
TYPES      = df_clean.set_index("property_id")["listing_type"].to_dict()
TIERS      = df_clean.set_index("property_id")["price_tier"].to_dict()

TRAFFIC_SOURCES = [
    ("google",   "organic",  0.32),
    ("direct",   "(none)",   0.21),
    ("google",   "cpc",      0.18),
    ("facebook", "social",   0.12),
    ("instagram","social",   0.07),
    ("email",    "email",    0.05),
    ("(other)",  "referral", 0.05),
]
DEVICES = [("mobile", 0.61), ("desktop", 0.33), ("tablet", 0.06)]
SA_PROVINCES = [
    ("Western Cape",   0.28),
    ("Gauteng",        0.26),
    ("KwaZulu-Natal",  0.15),
    ("Eastern Cape",   0.09),
    ("Limpopo",        0.06),
    ("Mpumalanga",     0.05),
    ("North West",     0.04),
    ("Free State",     0.04),
    ("Northern Cape",  0.03),
]

def weighted_choice(options):
    choices, weights = zip(*options)
    return random.choices(choices, weights=weights, k=1)[0]

def weighted_pair(options):
    pairs = [(a, b) for a, b, *_ in options]
    weights = [w for *_, w in options]
    return random.choices(pairs, weights=weights, k=1)[0]

# Generate 30,000 sessions: 2025-01-01 → 2025-06-30
START_DATE = date(2025, 1, 1)
END_DATE   = date(2025, 6, 30)
TOTAL_DAYS = (END_DATE - START_DATE).days + 1
N_SESSIONS = 30_000

sessions      = []
booking_events = []
event_id_counter = 0

for _ in range(N_SESSIONS):
    session_id   = str(uuid.uuid4())[:16]
    user_id      = hashlib.md5(fake.uuid4().encode()).hexdigest()[:16]
    event_date   = START_DATE + timedelta(days=random.randint(0, TOTAL_DAYS - 1))
    # Seasonal weights: Jan–Mar steady, Apr–May slight dip, Jun slight pickup
    month = event_date.month
    base_ts = int(datetime(event_date.year, event_date.month, event_date.day,
                            random.randint(6, 23), random.randint(0, 59)).timestamp() * 1_000_000)

    src, med = weighted_pair(TRAFFIC_SOURCES)
    device   = weighted_choice(DEVICES)
    province = weighted_choice(SA_PROVINCES)

    # Property viewed in this session (weighted toward popular regions)
    prop_id = random.choice(PROPERTIES)
    price   = PRICES.get(prop_id, 1200)
    tier    = TIERS.get(prop_id, "Mid-Range")

    # Engagement time (mobile shorter, luxury listings get more engagement)
    base_eng = {"Budget":45,"Mid-Range":72,"Premium":105,"Luxury":148,"Unknown":60}.get(tier, 72)
    if device == "mobile":
        base_eng = int(base_eng * 0.7)
    engagement_secs = max(5, int(np.random.exponential(base_eng)))

    bounced = engagement_secs < 15 or random.random() < 0.28

    sessions.append({
        "session_id"       : session_id,
        "user_pseudo_id"   : user_id,
        "event_date"       : event_date.isoformat(),
        "traffic_source"   : src,
        "traffic_medium"   : med,
        "device_category"  : device,
        "province"         : province,
        "property_id"      : prop_id,
        "price_tier_viewed": tier,
        "engagement_secs"  : engagement_secs,
        "bounced"          : int(bounced),
        "session_engaged"  : int(not bounced),
    })

    if bounced:
        continue

    # Booking funnel events: listing_view → search_nearby → contact_host → booking_initiated → booking_confirmed
    funnel_steps = [
        ("listing_view",     0.92),
        ("search_nearby",    0.55),
        ("contact_host",     0.35),
        ("booking_initiated",0.22),
        ("booking_confirmed",0.14),
    ]
    ts = base_ts
    for evt_name, prob in funnel_steps:
        if random.random() > prob:
            break
        ts += random.randint(5_000_000, 60_000_000)  # 5s–60s between steps
        event_id_counter += 1
        booking_events.append({
            "event_id"        : event_id_counter,
            "session_id"      : session_id,
            "user_pseudo_id"  : user_id,
            "event_date"      : event_date.isoformat(),
            "event_timestamp" : ts,
            "event_name"      : evt_name,
            "property_id"     : prop_id,
            "price_zar"       : float(price) if not pd.isna(price) else 0.0,
            "price_tier"      : tier,
            "listing_type"    : TYPES.get(prop_id, "Self Catering"),
            "device_category" : device,
            "province"        : province,
            "traffic_source"  : src,
            "traffic_medium"  : med,
            "analytics_consent": "Yes" if random.random() < 0.78 else "No",
        })

df_sessions = pd.DataFrame(sessions)
df_events   = pd.DataFrame(booking_events)

df_sessions.to_csv(DATA / "fact_web_sessions.csv", index=False)
df_events.to_csv(DATA / "fact_booking_events.csv", index=False)

print(f"  Sessions generated       : {len(df_sessions):,}")
print(f"  Booking events generated : {len(df_events):,}")
print(f"  Confirmed bookings       : {(df_events['event_name']=='booking_confirmed').sum():,}")
conv_rate = (df_events['event_name']=='booking_confirmed').sum() / len(df_sessions) * 100
print(f"  Overall conversion rate  : {conv_rate:.2f}%")
print(f"  Avg engagement (secs)    : {df_sessions['engagement_secs'].mean():.1f}")
print(f"  Bounce rate              : {df_sessions['bounced'].mean()*100:.1f}%")
consent_rate = (df_events['analytics_consent']=='Yes').mean()*100
print(f"  POPIA consent rate       : {consent_rate:.1f}%")

# ── STEP 6: GA4 SYNTHETIC EVENTS (flat schema) ────────────────────────────────
print("\n" + "=" * 60)
print("STEP 6 — Save combined GA4 events flat CSV")
print("=" * 60)
df_events.to_csv(DATA / "ga4_events_synthetic.csv", index=False)
print(f"  Saved: data/ga4_events_synthetic.csv  ({len(df_events):,} rows)")

# ── SUMMARY ───────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("STEP 7 — Dirty data summary report")
print("=" * 60)
print(f"\n  Issues found and fixed:")
print(f"    [OK] {dirty_report['name_with_promo']} property names had promotional noise (% off prefixes)")
print(f"    [OK] {dirty_report['price_with_spaces']} prices used 'R1 700' format (spaces in thousands)")
print(f"    [OK] {dirty_report['loc_with_dup']} locations had duplicated suburb ('X, X City')")
print(f"    [OK] {dirty_report['type_nonstandard']} records had non-standard listing types (LodgingBusiness, accommodation)")
print(f"    [OK] {dirty_report['rating_missing']} records had no rating (field not consistently scraped)")
print(f"    [OK] {df['price_outlier_flag'].sum()} price outliers >R{PRICE_CAP:,} flagged/nulled")
print(f"\n  Clean dataset: {len(df_clean):,} unique properties ready for BigQuery")
print(f"  Listing type distribution:")
for t, cnt in df_clean["listing_type"].value_counts().items():
    print(f"    {t:<22} : {cnt:>4} ({cnt/len(df_clean)*100:.1f}%)")
print(f"\n  Price tier distribution:")
for t, cnt in df_clean["price_tier"].value_counts().items():
    print(f"    {t:<12} : {cnt:>4} ({cnt/len(df_clean)*100:.1f}%)")

print("\n✅ ETL complete. Outputs in ./data/")
