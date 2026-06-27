"""
SA Accommodation Intelligence Platform
04_bq_upload.py — Load all CSVs into BigQuery

Auth options (choose one):
  A) Service Account key JSON  — recommended for scripts
  B) Application Default Creds — gcloud auth application-default login
  C) Sandbox API key           — via google.oauth2.credentials (browser token)

How to get a service account key (30 seconds in the console):
  1. BigQuery console → left rail → IAM & Admin → Service Accounts
  2. Create service account → BigQuery Admin role
  3. Keys tab → Add Key → JSON → download
  4. Set KEY_FILE path below

Author: Anthony Apollis | 2026-06-27
"""

import os
import sys
from pathlib import Path

from google.cloud import bigquery
from google.oauth2 import service_account

# ── CONFIGURATION ─────────────────────────────────────────────────────────────
PROJECT_ID = "uploadingnewdata"          # your GCP project ID (visible in BQ console header)
DATASET_ID = "accommodation_intelligence"
LOCATION   = "africa-south1"             # Johannesburg — lowest latency for SA

# Path to service account JSON key — leave empty to use Application Default Creds
KEY_FILE   = ""   # e.g. r"C:\Users\Anthony\Downloads\uploadingnewdata-key.json"

BASE = Path(__file__).parent
DATA = BASE / "data"
ML   = BASE / "ml"

# ── AUTHENTICATE ──────────────────────────────────────────────────────────────
def get_client() -> bigquery.Client:
    if KEY_FILE and Path(KEY_FILE).exists():
        creds = service_account.Credentials.from_service_account_file(
            KEY_FILE,
            scopes=["https://www.googleapis.com/auth/bigquery"],
        )
        return bigquery.Client(project=PROJECT_ID, credentials=creds, location=LOCATION)
    else:
        # Falls back to Application Default Credentials
        # (works if user ran: gcloud auth application-default login)
        print("  No KEY_FILE set — using Application Default Credentials")
        return bigquery.Client(project=PROJECT_ID, location=LOCATION)


# ── TABLE DEFINITIONS ─────────────────────────────────────────────────────────
TABLES = [
    {
        "file"   : DATA / "dim_property.csv",
        "table"  : "dim_property",
        "schema" : [
            bigquery.SchemaField("property_id",   "INTEGER"),
            bigquery.SchemaField("property_name", "STRING"),
            bigquery.SchemaField("listing_type",  "STRING"),
            bigquery.SchemaField("price_zar",     "FLOAT"),
            bigquery.SchemaField("price_tier",    "STRING"),
            bigquery.SchemaField("review_count",  "INTEGER"),
            bigquery.SchemaField("demand_score",  "FLOAT"),
            bigquery.SchemaField("url",           "STRING"),
            bigquery.SchemaField("ingested_at",   "TIMESTAMP"),
        ],
        "partition": None,
        "cluster" : ["listing_type", "price_tier"],
    },
    {
        "file"   : DATA / "dim_region.csv",
        "table"  : "dim_region",
        "schema" : [
            bigquery.SchemaField("region_id", "INTEGER"),
            bigquery.SchemaField("region",    "STRING"),
            bigquery.SchemaField("country",   "STRING"),
        ],
        "partition": None,
        "cluster" : ["country"],
    },
    {
        "file"   : DATA / "fact_listings.csv",
        "table"  : "fact_listings",
        "schema" : [
            bigquery.SchemaField("property_id",    "INTEGER"),
            bigquery.SchemaField("region_id",      "INTEGER"),
            bigquery.SchemaField("price_zar",      "FLOAT"),
            bigquery.SchemaField("review_count",   "INTEGER"),
            bigquery.SchemaField("demand_score",   "FLOAT"),
            bigquery.SchemaField("listing_type",   "STRING"),
            bigquery.SchemaField("price_tier",     "STRING"),
            bigquery.SchemaField("has_promo_flag", "BOOLEAN"),
            bigquery.SchemaField("discount_pct",   "FLOAT"),
            bigquery.SchemaField("scraped_date",   "DATE"),
        ],
        "partition": bigquery.TimePartitioning(field="scraped_date"),
        "cluster" : ["listing_type", "region_id"],
    },
    {
        "file"   : DATA / "fact_web_sessions.csv",
        "table"  : "fact_web_sessions",
        "schema" : [
            bigquery.SchemaField("session_id",        "STRING"),
            bigquery.SchemaField("user_pseudo_id",    "STRING"),
            bigquery.SchemaField("event_date",        "DATE"),
            bigquery.SchemaField("traffic_source",    "STRING"),
            bigquery.SchemaField("traffic_medium",    "STRING"),
            bigquery.SchemaField("device_category",   "STRING"),
            bigquery.SchemaField("province",          "STRING"),
            bigquery.SchemaField("property_id",       "INTEGER"),
            bigquery.SchemaField("price_tier_viewed", "STRING"),
            bigquery.SchemaField("engagement_secs",   "INTEGER"),
            bigquery.SchemaField("bounced",           "INTEGER"),
            bigquery.SchemaField("session_engaged",   "INTEGER"),
        ],
        "partition": bigquery.TimePartitioning(field="event_date"),
        "cluster" : ["traffic_source", "device_category", "province"],
    },
    {
        "file"   : DATA / "fact_booking_events.csv",
        "table"  : "fact_booking_events",
        "schema" : [
            bigquery.SchemaField("event_id",          "INTEGER"),
            bigquery.SchemaField("session_id",        "STRING"),
            bigquery.SchemaField("user_pseudo_id",    "STRING"),
            bigquery.SchemaField("event_date",        "DATE"),
            bigquery.SchemaField("event_timestamp",   "INTEGER"),
            bigquery.SchemaField("event_name",        "STRING"),
            bigquery.SchemaField("property_id",       "INTEGER"),
            bigquery.SchemaField("price_zar",         "FLOAT"),
            bigquery.SchemaField("price_tier",        "STRING"),
            bigquery.SchemaField("listing_type",      "STRING"),
            bigquery.SchemaField("device_category",   "STRING"),
            bigquery.SchemaField("province",          "STRING"),
            bigquery.SchemaField("traffic_source",    "STRING"),
            bigquery.SchemaField("traffic_medium",    "STRING"),
            bigquery.SchemaField("analytics_consent", "STRING"),
        ],
        "partition": bigquery.TimePartitioning(field="event_date"),
        "cluster" : ["event_name", "traffic_source", "province"],
    },
    {
        "file"   : ML / "ml_predictions.csv",
        "table"  : "ml_predictions",
        "schema" : [
            bigquery.SchemaField("property_id",         "INTEGER"),
            bigquery.SchemaField("property_name",       "STRING"),
            bigquery.SchemaField("listing_type",        "STRING"),
            bigquery.SchemaField("region",              "STRING"),
            bigquery.SchemaField("price_zar",           "FLOAT"),
            bigquery.SchemaField("predicted_price_zar", "FLOAT"),
            bigquery.SchemaField("price_delta_zar",     "FLOAT"),
            bigquery.SchemaField("price_tier",          "STRING"),
            bigquery.SchemaField("predicted_tier",      "STRING"),
            bigquery.SchemaField("demand_score",        "FLOAT"),
            bigquery.SchemaField("predicted_demand",    "FLOAT"),
            bigquery.SchemaField("review_count",        "INTEGER"),
        ],
        "partition": None,
        "cluster" : None,
    },
]

# ── HELPERS ───────────────────────────────────────────────────────────────────
def ensure_dataset(client: bigquery.Client):
    dataset_ref = f"{PROJECT_ID}.{DATASET_ID}"
    try:
        client.get_dataset(dataset_ref)
        print(f"  Dataset {DATASET_ID} already exists")
    except Exception:
        ds = bigquery.Dataset(dataset_ref)
        ds.location = LOCATION
        ds.description = "SA Accommodation Intelligence Platform — LekkeSlaap analysis 2026"
        client.create_dataset(ds, exists_ok=True)
        print(f"  Dataset created: {dataset_ref} ({LOCATION})")


def load_table(client: bigquery.Client, cfg: dict) -> None:
    table_id = f"{PROJECT_ID}.{DATASET_ID}.{cfg['table']}"
    file_path = cfg["file"]

    if not file_path.exists():
        print(f"  SKIP {cfg['table']} — file not found: {file_path}")
        return

    job_config = bigquery.LoadJobConfig(
        schema=cfg["schema"],
        skip_leading_rows=1,
        source_format=bigquery.SourceFormat.CSV,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        allow_quoted_newlines=True,
        null_marker="",
    )
    if cfg.get("partition"):
        job_config.time_partitioning = cfg["partition"]
    if cfg.get("cluster"):
        job_config.clustering_fields = cfg["cluster"]

    file_size_kb = file_path.stat().st_size // 1024
    print(f"  Loading {cfg['table']} ({file_size_kb:,} KB) ...", end="", flush=True)

    with open(file_path, "rb") as f:
        job = client.load_table_from_file(f, table_id, job_config=job_config)

    job.result()   # wait for completion

    table = client.get_table(table_id)
    print(f"  {table.num_rows:,} rows loaded")


# ── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    print("=" * 60)
    print("BigQuery Upload — SA Accommodation Intelligence Platform")
    print("=" * 60)
    print(f"\n  Project  : {PROJECT_ID}")
    print(f"  Dataset  : {DATASET_ID}")
    print(f"  Location : {LOCATION}")
    print(f"  Tables   : {len(TABLES)}\n")

    try:
        client = get_client()
        print(f"  Auth     : OK ({client.project})\n")
    except Exception as e:
        print(f"\n  AUTH FAILED: {str(e).split(chr(10))[0]}")
        print("\n  To fix:")
        print("  Option A: Set KEY_FILE to your service account JSON path")
        print("  Option B: Install gcloud CLI and run:")
        print("            gcloud auth application-default login")
        print("  Option C: Use BigQuery Console to upload CSVs manually (see guide below)\n")
        _print_manual_guide()
        sys.exit(1)

    ensure_dataset(client)
    print()

    failed = []
    for cfg in TABLES:
        try:
            load_table(client, cfg)
        except Exception as e:
            failed.append((cfg["table"], str(e)))
            print(f"  ERROR: {e}")

    print(f"\n{'='*60}")
    if not failed:
        print(f"  All {len(TABLES)} tables loaded successfully!")
        print(f"  View in BigQuery console:")
        print(f"  https://console.cloud.google.com/bigquery?project={PROJECT_ID}")
        print(f"\n  Try this query to verify:")
        print(f"""
    SELECT listing_type, price_tier, COUNT(*) AS listings, ROUND(AVG(price_zar),0) AS avg_price
    FROM `{PROJECT_ID}.{DATASET_ID}.fact_listings`
    GROUP BY 1,2 ORDER BY listings DESC;
        """)
    else:
        print(f"  {len(TABLES)-len(failed)} tables OK, {len(failed)} failed:")
        for name, err in failed:
            print(f"    {name}: {err}")


def _print_manual_guide():
    print("""
  MANUAL UPLOAD GUIDE (BigQuery Console):
  ─────────────────────────────────────────────────────────
  1. Go to: https://console.cloud.google.com/bigquery
  2. Click your project (UploadingNewdata) → +CREATE DATASET
     Dataset ID: accommodation_intelligence
     Location  : africa-south1 (Johannesburg)

  3. For each CSV file, click the dataset → +CREATE TABLE:
     Source         : Upload
     File           : (select CSV from data/ folder)
     Table name     : (see table names below)
     Schema         : Auto detect
     Header rows    : 1

  Files to upload:
     data/dim_property.csv        → dim_property
     data/dim_region.csv          → dim_region
     data/fact_listings.csv       → fact_listings
     data/fact_web_sessions.csv   → fact_web_sessions
     data/fact_booking_events.csv → fact_booking_events
     ml/ml_predictions.csv        → ml_predictions
  ─────────────────────────────────────────────────────────
    """)


if __name__ == "__main__":
    main()
