"""
SA Accommodation Intelligence Platform
05_geomap.py — ML-enriched interactive geomap (map.html)

ML features added:
  - K-Means clustering (4 segments) on [price, demand_score, review_count]
  - Seasonal demand indices from booking_events (SA seasons)
  - Price-demand Pearson correlation per region cluster
  - Seasonality volatility index (std/mean across seasons)

Outputs: netlify_site/map.html
"""

import json
import math
import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans

BASE = Path(__file__).parent
DATA = BASE / "data"
OUT  = BASE / "netlify_site" / "map.html"

# SA seasons: Summer=Dec,Jan,Feb | Autumn=Mar,Apr,May | Winter=Jun,Jul,Aug | Spring=Sep,Oct,Nov
MONTH_TO_SEASON = {12:"Summer",1:"Summer",2:"Summer",
                   3:"Autumn",4:"Autumn",5:"Autumn",
                   6:"Winter",7:"Winter",8:"Winter",
                   9:"Spring",10:"Spring",11:"Spring"}
SEASONS = ["Summer","Autumn","Winter","Spring"]

# Region → SA Province mapping
REGION_PROVINCE = {
    "Cape Town":"Western Cape","Garden Route":"Western Cape","Overberg":"Western Cape",
    "Cape Winelands":"Western Cape","Cape Route 62":"Western Cape","Escape From Cape Town":"Western Cape",
    "Stellenbosch":"Western Cape","Franschhoek":"Western Cape","Constantia Cape Town":"Western Cape",
    "Wellington":"Western Cape","Helderberg":"Western Cape","Robertson":"Western Cape",
    "Swartland":"Western Cape","Tulbagh":"Western Cape","Paarl":"Western Cape","Elgin":"Western Cape",
    "Villiersdorp":"Western Cape","Malgas":"Western Cape","West Coast":"Western Cape",
    "Yzerfontein":"Western Cape","St Helena Bay":"Western Cape","Dwarskersbos":"Western Cape",
    "Lamberts Bay":"Western Cape","Jacobs Bay":"Western Cape","Elands Bay":"Western Cape",
    "Velddrif":"Western Cape","Saldanha":"Western Cape","Darling":"Western Cape",
    "Plettenberg Bay":"Western Cape","Mossel Bay":"Western Cape","Wilderness":"Western Cape",
    "Hermanus":"Western Cape","Gansbaai":"Western Cape","Simon S Town":"Western Cape",
    "Betty S Bay":"Western Cape","Pringle Bay":"Western Cape","Fish Hoek":"Western Cape",
    "Kleinmond":"Western Cape","Onrus":"Western Cape","Pearly Beach":"Western Cape",
    "Cederberg":"Western Cape","Clanwilliam":"Western Cape","Vredendal":"Western Cape",
    "Nieuwoudtville":"Western Cape","Vanrhynsdorp":"Western Cape","Paternoster":"Western Cape",
    "Strandfontein West Coast":"Western Cape","Tsitsikamma":"Western Cape",
    "Beaufort West":"Western Cape","Prince Albert":"Western Cape","Barrydale":"Western Cape",
    "Ladismith":"Western Cape","Sutherland":"Northern Cape","Tankwa Karoo":"Northern Cape",
    "Johannesburg":"Gauteng","Pretoria":"Gauteng","Vanderbijlpark":"Gauteng",
    "Hartbeespoort":"Gauteng","Skeerpoort":"Gauteng","Escape From Johannesburg":"Gauteng",
    "Dinokeng Game Reserve":"Gauteng",
    "Durban":"KwaZulu-Natal","Ballito":"KwaZulu-Natal","Umhlanga":"KwaZulu-Natal",
    "Port Edward":"KwaZulu-Natal","Midlands Meander":"KwaZulu-Natal","Hluhluwe":"KwaZulu-Natal",
    "Escape From Durban":"KwaZulu-Natal",
    "Kruger National Park":"Limpopo","Marloth Park":"Limpopo","Hoedspruit":"Limpopo",
    "Thabazimbi":"Limpopo","Mookgopong":"Limpopo","Vaalwater":"Limpopo","Hazyview":"Limpopo",
    "Tzaneen":"Limpopo","Timbavati Private Nature Reserve":"Limpopo",
    "Thornybush Game Reserve":"Limpopo","Sabi Sand Game Reserve":"Limpopo",
    "Balule Nature Reserve":"Limpopo","Magoebaskloof":"Limpopo","Bela Bela":"Limpopo",
    "Panorama Route":"Mpumalanga","Dullstroom":"Mpumalanga",
    "Bojanala":"North West","Pilanesberg National Park":"North West",
    "Namaqualand":"Northern Cape","Kalahari":"Northern Cape","Upington":"Northern Cape",
    "Springbok":"Northern Cape","Kamieskroon":"Northern Cape","Kimberley":"Northern Cape",
    "Graaff Reinet":"Eastern Cape","Nieu Bethesda":"Eastern Cape","Victoria West":"Northern Cape",
    "Willowmore":"Eastern Cape","Middelburg Karoo":"Eastern Cape",
    "Gqeberha Port Elizabeth":"Eastern Cape","Port Alfred":"Eastern Cape","St Francis":"Eastern Cape",
    "Jeffreys Bay":"Eastern Cape","Sarah Baartman District":"Eastern Cape",
    "Addo Elephant Park":"Eastern Cape","Kenton On Sea":"Eastern Cape","Humansdorp":"Eastern Cape",
    "Clarens":"Free State","Gariep Dam":"Free State","Parys":"Free State",
    "Namibia":"Namibia","Homepage":"Western Cape",
}

COORDS = {
    "Namibia":(-22.5594,17.0832),"Cape Town":(-33.9249,18.4241),"Garden Route":(-33.9808,22.4556),
    "Overberg":(-34.3591,19.2368),"Johannesburg":(-26.2041,28.0473),"Cape Winelands":(-33.8878,18.8645),
    "Karoo":(-32.2949,24.5368),"Cape Route 62":(-33.7022,21.6814),"Ballito":(-29.5390,31.2133),
    "Pretoria":(-25.7479,28.2293),"Panorama Route":(-24.8670,30.8015),"Mossel Bay":(-34.1833,22.1453),
    "Gqeberha Port Elizabeth":(-33.9608,25.6022),"Durban":(-29.8587,31.0218),"Umhlanga":(-29.7258,31.0726),
    "Clarens":(-28.5203,28.4284),"Hartbeespoort":(-25.7481,27.9049),"Namaqualand":(-29.6635,17.9264),
    "Kruger National Park":(-24.0028,31.4855),"Bela Bela":(-24.8833,28.3167),
    "Sarah Baartman District":(-33.0000,26.0000),"Escape From Cape Town":(-34.1000,19.0000),
    "Escape From Johannesburg":(-26.5000,28.5000),"Escape From Durban":(-29.5000,30.5000),
    "Jeffreys Bay":(-34.0505,24.9222),"Port Alfred":(-33.5926,26.8901),"Port Edward":(-31.0530,30.2350),
    "Yzerfontein":(-33.3560,18.1583),"St Francis":(-34.1793,24.8468),"Langebaan":(-33.0971,18.0340),
    "Still Bay":(-34.3616,21.4266),"Onrus":(-34.4107,19.1892),"Marloth Park":(-25.0050,31.6667),
    "Hoedspruit":(-24.3667,31.0500),"Thabazimbi":(-24.5889,27.4069),"Mookgopong":(-24.5167,28.7833),
    "Skeerpoort":(-25.7667,27.7167),"Vaalwater":(-24.3000,28.0667),"Hazyview":(-24.9167,31.1000),
    "Tzaneen":(-23.8328,30.1638),"Timbavati Private Nature Reserve":(-24.6000,31.2000),
    "Pilanesberg National Park":(-25.2500,27.0833),"Thornybush Game Reserve":(-24.5000,31.0000),
    "Sabi Sand Game Reserve":(-24.9000,31.5000),"Dinokeng Game Reserve":(-25.5000,28.4000),
    "Balule Nature Reserve":(-24.3000,31.5000),"Addo Elephant Park":(-33.5000,25.8000),
    "Kalahari":(-26.7000,21.5000),"Hluhluwe":(-28.0263,32.2808),"Midlands Meander":(-29.5000,29.9000),
    "Magoebaskloof":(-23.9000,29.9000),"Tsitsikamma":(-34.0000,23.9000),"West Coast":(-33.0000,18.0000),
    "Bojanala":(-25.1000,27.5000),"Stellenbosch":(-33.9321,18.8602),"Franschhoek":(-33.9137,19.1250),
    "Constantia Cape Town":(-34.0187,18.4461),"Wellington":(-33.6443,19.0114),"Helderberg":(-34.0711,18.8420),
    "Robertson":(-33.7949,19.8832),"Vredendal":(-31.6719,18.5014),"Swartland":(-33.5000,18.7000),
    "Tulbagh":(-33.2861,19.1408),"Paarl":(-33.7177,18.9580),"Elgin":(-34.1549,19.0439),
    "Vanderbijlpark":(-26.7019,27.8360),"Kenton On Sea":(-33.6773,26.6769),"Villiersdorp":(-33.9918,19.2936),
    "Dullstroom":(-25.4200,30.1167),"Gariep Dam":(-30.5789,25.5059),"Upington":(-28.4515,21.2561),
    "Malgas":(-34.3576,20.6027),"Parys":(-26.9057,27.4577),"Graaff Reinet":(-32.2522,24.5408),
    "Nieu Bethesda":(-31.8618,24.5545),"Beaufort West":(-32.3595,22.5816),"Prince Albert":(-33.2209,22.0260),
    "Victoria West":(-31.4082,23.1287),"Oudtshoorn":(-33.5875,22.2068),"Sutherland":(-32.4069,20.6592),
    "Willowmore":(-33.2877,23.4922),"Middelburg Karoo":(-31.5014,25.0011),"Barrydale":(-33.9025,20.7436),
    "Ladismith":(-33.4981,21.2592),"Nieuwoudtville":(-31.3814,19.1169),"Tankwa Karoo":(-32.5000,19.5000),
    "Vanrhynsdorp":(-31.6150,18.7378),"Kamieskroon":(-30.1756,17.9439),"Clanwilliam":(-32.1775,18.8924),
    "Springbok":(-29.6635,17.8864),"Cederberg":(-32.5000,19.0000),"Darling":(-33.3750,18.3731),
    "Plettenberg Bay":(-34.0520,23.3681),"Pearly Beach":(-34.6611,19.5094),"Pringle Bay":(-34.3669,18.8278),
    "Simon S Town":(-34.1924,18.4374),"Betty S Bay":(-34.3599,18.9208),"Wilderness":(-33.9960,22.5955),
    "Kleinmond":(-34.3489,19.0472),"Hermanus":(-34.4187,19.2345),"Fish Hoek":(-34.1358,18.4289),
    "Gansbaai":(-34.5787,19.3508),"St Helena Bay":(-32.7503,18.0269),"Strandfontein West Coast":(-31.0000,17.5000),
    "Dwarskersbos":(-32.7033,18.0947),"Lamberts Bay":(-32.0823,18.3044),"Paternoster":(-32.9699,17.8893),
    "Jacobs Bay":(-33.0000,17.9000),"Elands Bay":(-32.3083,18.3419),"Velddrif":(-32.7761,18.1589),
    "Saldanha":(-33.0130,17.9363),"Homepage":(-33.9249,18.4241),"Humansdorp":(-34.0364,24.7669),
    "Kimberley":(-28.7381,24.7653),
}

TIER_COLOR = {
    "Budget":"#4CAF50","Mid-Range":"#2196F3","Premium":"#FF9800","Luxury":"#9C27B0","Unknown":"#9E9E9E",
}

CLUSTER_META = [
    {"name":"High-Demand Hotspot","color":"#FF4444","desc":"High traffic, top demand scores"},
    {"name":"Established Premium","color":"#FF9800","desc":"Strong reviews, premium pricing"},
    {"name":"Value Volume Leader","color":"#2196F3","desc":"High listing count, accessible price"},
    {"name":"Emerging Gem","color":"#4CAF50","desc":"Lower volume, growth potential"},
]


def compute_seasonal(be: pd.DataFrame) -> dict:
    """Province → season → normalised demand index (0–1)."""
    be["month"] = pd.to_datetime(be["event_date"], errors="coerce").dt.month
    be["season"] = be["month"].map(MONTH_TO_SEASON)
    be = be.dropna(subset=["season", "province"])

    prov_season = (
        be.groupby(["province", "season"])
        .size()
        .reset_index(name="cnt")
    )
    result = {}
    for prov, grp in prov_season.groupby("province"):
        total = grp["cnt"].sum()
        row = {}
        for _, r in grp.iterrows():
            row[r["season"]] = round(r["cnt"] / total, 3)
        # fill missing seasons
        for s in SEASONS:
            row.setdefault(s, 0.0)
        result[prov] = row

    # Default equal distribution for provinces not in booking events
    default = {s: 0.25 for s in SEASONS}
    return result, default


def build_ml_markers():
    fl  = pd.read_csv(DATA / "fact_listings.csv")
    dr  = pd.read_csv(DATA / "dim_region.csv")
    be  = pd.read_csv(DATA / "fact_booking_events.csv")

    seasonal_by_prov, default_seasonal = compute_seasonal(be)

    merged = fl.merge(dr, on="region_id")

    stats = (
        merged.groupby("region")
        .agg(
            count       = ("property_id",   "count"),
            avg_price   = ("price_zar",      lambda x: round(x.mean(), 0)),
            avg_demand  = ("demand_score",   lambda x: round(x.mean(), 3)),
            avg_reviews = ("review_count",   lambda x: round(x.mean(), 1)),
            top_tier    = ("price_tier",     lambda x: x.value_counts().index[0] if len(x) else "Unknown"),
            top_type    = ("listing_type",   lambda x: x.value_counts().index[0] if len(x) else ""),
            promo_count = ("has_promo_flag", "sum"),
        )
        .reset_index()
    )

    # ── K-Means clustering ────────────────────────────────────────────────────
    feat_cols = ["avg_price", "avg_demand", "avg_reviews", "count"]
    X_raw = stats[feat_cols].fillna(0).values.astype(float)
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X_raw)

    km = KMeans(n_clusters=4, random_state=42, n_init=20)
    labels = km.fit_predict(X_scaled)
    stats["raw_cluster"] = labels

    # Rank clusters by composite score (price + demand + reviews)
    centroids_orig = scaler.inverse_transform(km.cluster_centers_)
    centroid_df = pd.DataFrame(centroids_orig, columns=feat_cols)
    centroid_df["score"] = (
        centroid_df["avg_price"].rank() * 0.3 +
        centroid_df["avg_demand"].rank() * 0.4 +
        centroid_df["avg_reviews"].rank() * 0.3
    )
    rank_order = centroid_df["score"].rank(ascending=False).astype(int) - 1
    # rank_order maps raw_cluster → named cluster index (0=hotspot, 3=emerging)
    stats["cluster"] = stats["raw_cluster"].map(rank_order.to_dict())

    # ── Pearson r: price vs demand per cluster ────────────────────────────────
    cluster_corr = {}
    for cl in range(4):
        sub = stats[stats["cluster"] == cl]
        if len(sub) > 2:
            r = np.corrcoef(sub["avg_price"].fillna(0), sub["avg_demand"].fillna(0))[0, 1]
            cluster_corr[cl] = round(float(r), 3)
        else:
            cluster_corr[cl] = 0.0

    # ── Seasonality volatility (std/mean across seasons per region) ───────────
    def seasonal_for_region(region):
        prov = REGION_PROVINCE.get(region, "")
        s = seasonal_by_prov.get(prov, default_seasonal)
        vals = [s.get(season, 0.25) for season in SEASONS]
        mean_v = sum(vals) / 4
        vol = (sum((v - mean_v)**2 for v in vals) / 4) ** 0.5 / (mean_v + 1e-9)
        return {season: round(s.get(season, 0.25), 3) for season in SEASONS}, round(vol, 3)

    # ── Assemble markers ──────────────────────────────────────────────────────
    markers = []
    for _, row in stats.iterrows():
        region = row["region"]
        if region not in COORDS:
            continue
        lat, lng = COORDS[region]
        tier    = str(row["top_tier"]) if pd.notna(row["top_tier"]) else "Unknown"
        color   = TIER_COLOR.get(tier, "#9E9E9E")
        avg_p   = int(row["avg_price"]) if pd.notna(row["avg_price"]) else 0
        avg_d   = float(row["avg_demand"]) if pd.notna(row["avg_demand"]) else 0
        cl      = int(row["cluster"]) if pd.notna(row["cluster"]) else 3
        radius  = max(6, min(42, int(math.sqrt(row["count"]) * 3.5)))
        sea, vol = seasonal_for_region(region)

        markers.append({
            "lat":    lat,
            "lng":    lng,
            "region": region,
            "count":  int(row["count"]),
            "avg":    avg_p,
            "demand": avg_d,
            "reviews":float(row["avg_reviews"]) if pd.notna(row["avg_reviews"]) else 0,
            "tier":   tier,
            "type":   str(row["top_type"]),
            "promos": int(row["promo_count"]),
            "color":  color,
            "radius": radius,
            "cluster":cl,
            "seasonal": sea,
            "vol":    vol,
            "province": REGION_PROVINCE.get(region, ""),
        })

    # Global Pearson r (price vs demand)
    all_r = float(np.corrcoef(
        stats["avg_price"].fillna(0),
        stats["avg_demand"].fillna(0)
    )[0, 1])

    # Cluster summary for legend
    cluster_summary = []
    for cl in range(4):
        sub = stats[stats["cluster"] == cl]
        cluster_summary.append({
            "idx":    cl,
            "n":      len(sub),
            "avg_price": int(sub["avg_price"].mean()) if len(sub) else 0,
            "avg_demand": round(float(sub["avg_demand"].mean()), 2) if len(sub) else 0,
            "corr":   cluster_corr.get(cl, 0),
        })

    return markers, cluster_summary, round(all_r, 3)


def generate_html(markers, cluster_summary, global_r):
    total     = sum(m["count"] for m in markers)
    avg_all   = round(sum(m["avg"] * m["count"] for m in markers) / max(total, 1))
    n_regions = len(markers)
    markers_json  = json.dumps(markers, ensure_ascii=False)
    cluster_json  = json.dumps(cluster_summary, ensure_ascii=False)
    meta_json     = json.dumps(CLUSTER_META, ensure_ascii=False)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>SA Accommodation ML Geomap | Intelligence Platform</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
*{{box-sizing:border-box;margin:0;padding:0;}}
body{{font-family:'Segoe UI',Arial,sans-serif;background:#1A1A2E;color:#fff;}}
#top-bar{{background:#16213E;padding:10px 18px;display:flex;align-items:center;gap:14px;border-bottom:2px solid #00BCD4;flex-wrap:wrap;position:sticky;top:0;z-index:900;}}
.logo{{font-size:.85rem;font-weight:700;color:#00BCD4;white-space:nowrap;}}
.logo span{{color:#aab3cc;font-weight:400;}}
.kpi{{text-align:center;padding:3px 12px;border-left:1px solid #2a3a5e;}}
.kpi-n{{font-size:1rem;font-weight:700;color:#00BCD4;}}
.kpi-l{{font-size:.6rem;text-transform:uppercase;letter-spacing:.07em;color:#7a8aa0;}}
.nav-links{{margin-left:auto;display:flex;gap:6px;}}
.nav-links a{{color:#aab3cc;font-size:.72rem;font-weight:600;padding:4px 10px;border-radius:6px;text-decoration:none;background:rgba(255,255,255,.06);}}
.nav-links a:hover{{background:rgba(0,188,212,.15);color:#00BCD4;}}
#map{{width:100%;height:calc(100vh - 58px);}}

/* ── controls panel ───────────────────────────────────────── */
#ctrl-panel{{position:absolute;top:70px;right:12px;z-index:1000;background:#16213E;border:1px solid #2a3a5e;border-radius:10px;padding:10px 14px;min-width:200px;max-width:230px;font-size:.72rem;}}
#ctrl-panel h4{{color:#00BCD4;font-size:.68rem;text-transform:uppercase;letter-spacing:.08em;margin-bottom:8px;}}
.ctrl-section{{margin-bottom:10px;padding-bottom:10px;border-bottom:1px solid #2a3a5e;}}
.ctrl-section:last-child{{border-bottom:none;margin-bottom:0;padding-bottom:0;}}
.ctrl-label{{color:#aab3cc;font-size:.65rem;text-transform:uppercase;letter-spacing:.06em;margin-bottom:5px;}}
.ctrl-row{{display:flex;align-items:center;gap:7px;margin-bottom:4px;color:#ccd2e0;}}
.ctrl-row:last-child{{margin-bottom:0;}}
.ctrl-row input[type=radio]{{accent-color:#00BCD4;}}
.size-note{{font-size:.6rem;color:#5a6a80;margin-top:5px;}}
.season-btn{{display:block;width:100%;text-align:left;background:none;border:1px solid #2a3a5e;border-radius:5px;padding:4px 8px;color:#aab3cc;font-size:.67rem;cursor:pointer;margin-bottom:3px;transition:.15s;}}
.season-btn:hover,.season-btn.active{{background:rgba(0,188,212,.12);border-color:#00BCD4;color:#00BCD4;}}

/* ── ML insights panel ────────────────────────────────────── */
#ml-panel{{position:absolute;bottom:30px;left:12px;z-index:1000;background:#16213E;border:1px solid #2a3a5e;border-radius:10px;padding:12px 14px;min-width:260px;max-width:300px;font-size:.71rem;}}
#ml-panel h4{{color:#00BCD4;font-size:.68rem;text-transform:uppercase;letter-spacing:.08em;margin-bottom:8px;}}
.cluster-row{{display:flex;align-items:center;gap:8px;margin-bottom:6px;}}
.cl-dot{{width:11px;height:11px;border-radius:50%;flex-shrink:0;}}
.cl-info{{flex:1;}}
.cl-name{{font-size:.68rem;font-weight:700;color:#e0e6f0;}}
.cl-sub{{font-size:.6rem;color:#7a8aa0;}}
.cl-stats{{font-size:.6rem;color:#00BCD4;white-space:nowrap;}}
.corr-bar{{display:flex;align-items:center;gap:6px;margin-bottom:4px;}}
.corr-track{{flex:1;height:5px;background:#2a3a5e;border-radius:3px;overflow:hidden;}}
.corr-fill{{height:100%;border-radius:3px;}}
.corr-val{{font-size:.6rem;color:#aab3cc;min-width:34px;text-align:right;}}
.season-heat{{display:grid;grid-template-columns:repeat(4,1fr);gap:4px;margin-top:6px;}}
.sh-cell{{text-align:center;padding:4px 2px;border-radius:4px;font-size:.6rem;}}
.sh-lbl{{color:#7a8aa0;font-size:.58rem;}}

/* ── Leaflet overrides ────────────────────────────────────── */
.leaflet-popup-content-wrapper{{background:#16213E;color:#fff;border:1px solid #00BCD4;border-radius:10px;min-width:220px;}}
.leaflet-popup-tip{{background:#00BCD4;}}
.pop-title{{font-size:.85rem;font-weight:700;color:#00BCD4;margin-bottom:6px;}}
.pop-row{{display:flex;justify-content:space-between;gap:10px;font-size:.72rem;padding:3px 0;border-bottom:1px solid #2a3a5e;}}
.pop-row:last-child{{border-bottom:none;}}
.pop-lbl{{color:#7a8aa0;}}
.pop-val{{color:#fff;font-weight:600;}}
.tier-badge,.cl-badge{{display:inline-block;padding:2px 8px;border-radius:10px;font-size:.62rem;font-weight:700;}}
.sea-mini{{display:grid;grid-template-columns:repeat(4,1fr);gap:3px;margin-top:6px;}}
.sea-bar-wrap{{display:flex;flex-direction:column;align-items:center;gap:2px;}}
.sea-bar-bg{{width:20px;height:40px;background:#2a3a5e;border-radius:3px;display:flex;align-items:flex-end;}}
.sea-bar{{width:100%;border-radius:3px;transition:.3s;}}
.sea-lbl{{font-size:.55rem;color:#7a8aa0;}}

.legend{{background:#16213E;padding:10px 14px;border-radius:8px;border:1px solid #2a3a5e;min-width:140px;}}
.legend h4{{font-size:.68rem;color:#00BCD4;text-transform:uppercase;letter-spacing:.08em;margin-bottom:8px;}}
.leg-row{{display:flex;align-items:center;gap:8px;margin-bottom:5px;font-size:.7rem;color:#aab3cc;}}
.leg-dot{{width:11px;height:11px;border-radius:50%;flex-shrink:0;}}
</style>
</head>
<body>

<div id="top-bar">
  <div class="logo">SA Accommodation <span>Intelligence Platform</span></div>
  <div class="kpi"><div class="kpi-n">{n_regions}</div><div class="kpi-l">Regions</div></div>
  <div class="kpi"><div class="kpi-n">{total:,}</div><div class="kpi-l">Listings</div></div>
  <div class="kpi"><div class="kpi-n">R{avg_all:,}</div><div class="kpi-l">Avg Price/Night</div></div>
  <div class="kpi"><div class="kpi-n">r={global_r}</div><div class="kpi-l">Price↔Demand r</div></div>
  <div class="nav-links">
    <a href="index.html">Home</a>
    <a href="dashboard.html">Dashboard</a>
    <a href="ebook.html">Ebook</a>
    <a href="gtm-demo/">GTM Demo</a>
  </div>
</div>

<div id="map"></div>

<!-- ── Controls ── -->
<div id="ctrl-panel">
  <h4>Map Controls</h4>

  <div class="ctrl-section">
    <div class="ctrl-label">Circle Size Mode</div>
    <div class="ctrl-row"><input type="radio" name="mode" value="count" checked> Listing count</div>
    <div class="ctrl-row"><input type="radio" name="mode" value="price"> Avg price</div>
    <div class="ctrl-row"><input type="radio" name="mode" value="demand"> Demand score</div>
    <div class="size-note">Circle area = relative volume</div>
  </div>

  <div class="ctrl-section">
    <div class="ctrl-label">Colour Mode</div>
    <div class="ctrl-row"><input type="radio" name="cmode" value="tier" checked> Price tier</div>
    <div class="ctrl-row"><input type="radio" name="cmode" value="cluster"> ML cluster</div>
    <div class="ctrl-row"><input type="radio" name="cmode" value="season"> Seasonal heat</div>
  </div>

  <div class="ctrl-section" id="season-btns" style="display:none;">
    <div class="ctrl-label">Season (SA)</div>
    <button class="season-btn active" data-s="Summer">☀️ Summer (Dec–Feb)</button>
    <button class="season-btn" data-s="Autumn">🍂 Autumn (Mar–May)</button>
    <button class="season-btn" data-s="Winter">❄️ Winter (Jun–Aug)</button>
    <button class="season-btn" data-s="Spring">🌸 Spring (Sep–Nov)</button>
  </div>
</div>

<!-- ── ML Insights Panel ── -->
<div id="ml-panel">
  <h4>ML Insights</h4>
  <div id="cluster-legend"></div>
  <div style="margin-top:10px;">
    <div class="ctrl-label" style="margin-bottom:6px;">Price ↔ Demand Correlation by Cluster</div>
    <div id="corr-bars"></div>
  </div>
  <div style="margin-top:10px;">
    <div class="ctrl-label" style="margin-bottom:6px;">Seasonal Demand — SA Average</div>
    <div class="season-heat" id="season-avg"></div>
  </div>
</div>

<script>
const MARKERS = {markers_json};
const CLUSTER_SUMMARY = {cluster_json};
const CLUSTER_META = {meta_json};
const GLOBAL_R = {global_r};

const TIER_COLOR = {{
  "Budget":"#4CAF50","Mid-Range":"#2196F3","Premium":"#FF9800","Luxury":"#9C27B0","Unknown":"#9E9E9E"
}};

const map = L.map('map',{{center:[-29.0,25.0],zoom:6,zoomControl:true}});
L.tileLayer('https://{{s}}.basemaps.cartocdn.com/dark_all/{{z}}/{{x}}/{{y}}{{r}}.png',{{
  attribution:'&copy; OpenStreetMap &copy; CARTO',subdomains:'abcd',maxZoom:19,
}}).addTo(map);

let circles=[], currentMode='count', currentCmode='tier', currentSeason='Summer';

// ── sizing ─────────────────────────────────────────────────────────────────
function radiusFor(m, mode) {{
  if (mode==='price')  return Math.max(6,Math.min(42,Math.sqrt(m.avg/80)*2.5));
  if (mode==='demand') return Math.max(6,Math.min(42,m.demand*6+4));
  return m.radius;
}}

// ── coloring ───────────────────────────────────────────────────────────────
function colorFor(m, cmode, season) {{
  if (cmode==='cluster') return CLUSTER_META[m.cluster]?.color || '#9E9E9E';
  if (cmode==='season') {{
    const idx = m.seasonal[season] || 0.25;
    // heat: low=blue(#2196F3), mid=orange(#FF9800), high=red(#FF1744)
    if (idx > 0.35) return '#FF1744';
    if (idx > 0.28) return '#FF6D00';
    if (idx > 0.22) return '#FF9800';
    if (idx > 0.16) return '#2196F3';
    return '#37474F';
  }}
  return TIER_COLOR[m.tier] || '#9E9E9E';
}}

// ── opacity based on seasonal demand ──────────────────────────────────────
function opacityFor(m, cmode, season) {{
  if (cmode==='season') {{
    const idx = m.seasonal[season] || 0.25;
    return Math.max(0.35, Math.min(0.92, idx * 3.0));
  }}
  return 0.78;
}}

// ── popup content ──────────────────────────────────────────────────────────
function popupHtml(m) {{
  const clMeta = CLUSTER_META[m.cluster] || {{}};
  const tierBg = {{"Budget":"#1B5E20","Mid-Range":"#0D47A1","Premium":"#E65100","Luxury":"#4A148C","Unknown":"#424242"}};
  const bg = tierBg[m.tier]||'#424242';

  const seaBars = ['Summer','Autumn','Winter','Spring'].map(s=>{{
    const v = m.seasonal[s]||0.25;
    const h = Math.round(v*160);
    const col = v>0.35?'#FF1744':v>0.28?'#FF6D00':v>0.22?'#FF9800':'#2196F3';
    return `<div class="sea-bar-wrap">
      <div class="sea-bar-bg"><div class="sea-bar" style="height:${{h}}px;background:${{col}};"></div></div>
      <div class="sea-lbl">${{s.slice(0,3)}}</div>
    </div>`;
  }}).join('');

  return `<div class="pop-title">${{m.region}}</div>
    <div class="pop-row"><span class="pop-lbl">Province</span><span class="pop-val">${{m.province||'—'}}</span></div>
    <div class="pop-row"><span class="pop-lbl">Listings</span><span class="pop-val">${{m.count}}</span></div>
    <div class="pop-row"><span class="pop-lbl">Avg price/night</span><span class="pop-val">R${{m.avg.toLocaleString()}}</span></div>
    <div class="pop-row"><span class="pop-lbl">Demand score</span><span class="pop-val">${{m.demand.toFixed(2)}}</span></div>
    <div class="pop-row"><span class="pop-lbl">Avg reviews</span><span class="pop-val">${{m.reviews.toFixed(0)}}</span></div>
    <div class="pop-row"><span class="pop-lbl">Top type</span><span class="pop-val">${{m.type}}</span></div>
    <div class="pop-row"><span class="pop-lbl">Tier</span><span class="pop-val"><span class="tier-badge" style="background:${{bg}};color:#fff;">${{m.tier}}</span></span></div>
    <div class="pop-row"><span class="pop-lbl">ML Cluster</span><span class="pop-val"><span class="cl-badge" style="background:${{clMeta.color}};color:#fff;">${{clMeta.name||'—'}}</span></span></div>
    <div class="pop-row"><span class="pop-lbl">Seasonality vol.</span><span class="pop-val">${{(m.vol*100).toFixed(0)}}%</span></div>
    <div class="pop-row"><span class="pop-lbl">Promo listings</span><span class="pop-val">${{m.promos}}</span></div>
    <div style="margin-top:8px;font-size:.62rem;color:#7a8aa0;margin-bottom:4px;">Seasonal demand distribution</div>
    <div class="sea-mini">${{seaBars}}</div>`;
}}

// ── draw ───────────────────────────────────────────────────────────────────
function drawMarkers() {{
  circles.forEach(c=>map.removeLayer(c));
  circles=[];
  MARKERS.forEach(m=>{{
    const r  = radiusFor(m, currentMode);
    const fc = colorFor(m, currentCmode, currentSeason);
    const op = opacityFor(m, currentCmode, currentSeason);
    const c = L.circleMarker([m.lat,m.lng],{{
      radius:r, fillColor:fc, color:'rgba(255,255,255,0.5)',
      weight:1, opacity:.9, fillOpacity:op,
    }}).addTo(map);
    c.bindPopup(popupHtml(m),{{maxWidth:280}});
    circles.push(c);
  }});
  updateLegend();
}}

// ── legend ─────────────────────────────────────────────────────────────────
let legendControl = null;
function updateLegend() {{
  if (legendControl) map.removeControl(legendControl);
  legendControl = L.control({{position:'bottomright'}});
  legendControl.onAdd = () => {{
    const d = L.DomUtil.create('div','legend');
    if (currentCmode==='cluster') {{
      d.innerHTML='<h4>ML Cluster</h4>'+CLUSTER_META.map(c=>
        `<div class="leg-row"><div class="leg-dot" style="background:${{c.color}}"></div>${{c.name}}</div>`
      ).join('');
    }} else if (currentCmode==='season') {{
      d.innerHTML=`<h4>Demand Heat</h4>
        <div class="leg-row"><div class="leg-dot" style="background:#FF1744"></div>Very High (>35%)</div>
        <div class="leg-row"><div class="leg-dot" style="background:#FF6D00"></div>High (28–35%)</div>
        <div class="leg-row"><div class="leg-dot" style="background:#FF9800"></div>Medium (22–28%)</div>
        <div class="leg-row"><div class="leg-dot" style="background:#2196F3"></div>Lower (&lt;22%)</div>`;
    }} else {{
      d.innerHTML='<h4>Price Tier</h4>'+[
        ['#4CAF50','Budget'],['#2196F3','Mid-Range'],['#FF9800','Premium'],['#9C27B0','Luxury']
      ].map(([c,n])=>`<div class="leg-row"><div class="leg-dot" style="background:${{c}}"></div>${{n}}</div>`).join('');
    }}
    return d;
  }};
  legendControl.addTo(map);
}}

// ── ML insights panel ──────────────────────────────────────────────────────
function buildMlPanel() {{
  // Cluster legend
  const clLeg = document.getElementById('cluster-legend');
  clLeg.innerHTML = CLUSTER_META.map((c,i)=>{{
    const s = CLUSTER_SUMMARY[i]||{{}};
    return `<div class="cluster-row">
      <div class="cl-dot" style="background:${{c.color}}"></div>
      <div class="cl-info">
        <div class="cl-name">${{c.name}}</div>
        <div class="cl-sub">${{c.desc}}</div>
      </div>
      <div class="cl-stats">${{s.n||0}} regions</div>
    </div>`;
  }}).join('');

  // Correlation bars
  const corrEl = document.getElementById('corr-bars');
  corrEl.innerHTML = CLUSTER_META.map((c,i)=>{{
    const r = CLUSTER_SUMMARY[i]?.corr||0;
    const pct = Math.abs(r)*100;
    const col = r>0?'#00BCD4':'#FF6D00';
    const label = r>0.5?'Strong +':r>0.2?'Moderate +':r<-0.5?'Strong −':r<-0.2?'Moderate −':'Weak';
    return `<div class="corr-bar">
      <div style="font-size:.6rem;color:#aab3cc;min-width:70px;">${{c.name.split(' ').slice(0,2).join(' ')}}</div>
      <div class="corr-track"><div class="corr-fill" style="width:${{pct}}%;background:${{col}};"></div></div>
      <div class="corr-val">${{r>=0?'+':''}}${{r.toFixed(2)}} ${{label}}</div>
    </div>`;
  }}).join('');

  // Season avg across all regions
  const seasons=['Summer','Autumn','Winter','Spring'];
  const avgSea = seasons.map(s=>{{
    const vals = MARKERS.map(m=>m.seasonal[s]||0.25);
    return vals.reduce((a,b)=>a+b,0)/vals.length;
  }});
  const maxSea = Math.max(...avgSea);
  const seaEl = document.getElementById('season-avg');
  seaEl.innerHTML = seasons.map((s,i)=>{{
    const pct = Math.round(avgSea[i]/maxSea*100);
    const col = avgSea[i]>0.28?'#FF4444':avgSea[i]>0.25?'#FF9800':'#2196F3';
    const emojis = ['☀️','🍂','❄️','🌸'];
    return `<div class="sh-cell" style="background:${{col}}22;border:1px solid ${{col}}44;">
      <div style="font-size:.8rem;">${{emojis[i]}}</div>
      <div style="color:${{col}};font-weight:700;font-size:.65rem;">${{(avgSea[i]*100).toFixed(0)}}%</div>
      <div class="sh-lbl">${{s}}</div>
    </div>`;
  }}).join('');
}}

// ── Event listeners ────────────────────────────────────────────────────────
document.querySelectorAll('input[name="mode"]').forEach(r=>{{
  r.addEventListener('change',()=>{{ currentMode=r.value; drawMarkers(); }});
}});
document.querySelectorAll('input[name="cmode"]').forEach(r=>{{
  r.addEventListener('change',()=>{{
    currentCmode=r.value;
    document.getElementById('season-btns').style.display=r.value==='season'?'block':'none';
    drawMarkers();
  }});
}});
document.querySelectorAll('.season-btn').forEach(b=>{{
  b.addEventListener('click',()=>{{
    document.querySelectorAll('.season-btn').forEach(x=>x.classList.remove('active'));
    b.classList.add('active');
    currentSeason=b.dataset.s;
    drawMarkers();
  }});
}});

// ── Init ───────────────────────────────────────────────────────────────────
buildMlPanel();
drawMarkers();
</script>
</body>
</html>"""
    return html


def main():
    print("Building ML geomap...")
    markers, cluster_summary, global_r = build_ml_markers()
    print(f"  {len(markers)} regions | K-Means 4 clusters | global r={global_r}")
    for i, cs in enumerate(cluster_summary):
        print(f"  Cluster {i} ({CLUSTER_META[i]['name']}): {cs['n']} regions, "
              f"avg R{cs['avg_price']}/night, demand {cs['avg_demand']}, corr r={cs['corr']}")
    html = generate_html(markers, cluster_summary, global_r)
    OUT.write_text(html, encoding="utf-8")
    size_kb = round(OUT.stat().st_size / 1024, 1)
    print(f"  Written: {OUT} ({size_kb} KB)")
    print(f"  Open: http://localhost:8781/map.html")


if __name__ == "__main__":
    main()
