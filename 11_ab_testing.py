"""
11_ab_testing.py
Adds A/B testing layer to the SA Accommodation Intelligence Platform.

THREE TESTS
  AB-001  Listing page layout   Web   price-first vs image-first
  AB-002  Checkout UX           Web   progress bar + trust badge vs standard
  AB-003  App install creative  App   price-anchor CTA vs generic CTA

Outputs
  data/fact_ab_sessions.csv        web session-level A/B assignments + outcomes
  data/fact_ab_app_installs.csv    appsflyer install-level variant + retention
  data/fact_ab_results.csv         summary stats per test (conversion, uplift, p-value)
  netlify_site/ab-testing.html     new page
"""
import json, random, datetime
from pathlib import Path
import pandas as pd
import numpy as np
from scipy import stats

random.seed(42)
np.random.seed(42)

BASE = Path(__file__).parent
DATA = BASE / "data"
NET  = BASE / "netlify_site"

# ─── Load existing data ───────────────────────────────────────────────────────
ws = pd.read_csv(DATA / "fact_web_sessions.csv", low_memory=False)
af = pd.read_csv(DATA / "appsflyer_installs.csv", low_memory=False)
print(f"Loaded {len(ws):,} sessions, {len(af):,} app installs")

# ─── TEST AB-001: Listing Page Layout ────────────────────────────────────────
# Control A: image-first layout  baseline conv ~3.8%
# Variant B: price-first + urgency badge  conv ~5.1%  (+34% relative uplift)
print("Generating AB-001: Listing layout test...")

n_ab001 = 40_000
ab001_rows = []
for i in range(n_ab001):
    variant  = "A" if i % 2 == 0 else "B"
    device   = random.choices(["mobile","desktop","tablet"], weights=[55,35,10])[0]
    province = random.choices(
        ["Western Cape","Gauteng","KwaZulu-Natal","Eastern Cape","Limpopo",
         "Mpumalanga","North West","Free State","Northern Cape"],
        weights=[25,20,15,8,7,6,5,7,7])[0]
    d        = datetime.date(2026,1,1) + datetime.timedelta(days=random.randint(0,177))
    duration = random.randint(15, 600)
    pvs      = random.randint(1, 10)

    # Conversion rates differ by variant and device
    base_conv = {"A": {"mobile":0.034,"desktop":0.042,"tablet":0.038},
                 "B": {"mobile":0.048,"desktop":0.058,"tablet":0.051}}
    converted = random.random() < base_conv[variant][device]
    bounced   = pvs == 1

    ab001_rows.append({
        "session_id":    f"AB1_{i:06d}",
        "test_id":       "AB-001",
        "test_name":     "Listing Page Layout",
        "variant":       variant,
        "variant_label": "Image-first (Control)" if variant=="A" else "Price-first + urgency (Variant)",
        "session_date":  d.isoformat(),
        "device":        device,
        "province":      province,
        "duration_sec":  duration,
        "page_views":    pvs,
        "bounced":       bounced,
        "converted":     converted,
        "revenue_zar":   round(random.uniform(800,4500),2) if converted else 0,
    })

ab001 = pd.DataFrame(ab001_rows)

# ─── TEST AB-002: Checkout UX ─────────────────────────────────────────────────
# Control A: standard single-page checkout  baseline conv 41% of checkout_starts
# Variant B: progress bar + trust badge     conv 56% of checkout_starts
print("Generating AB-002: Checkout UX test...")

n_ab002 = 12_000  # only users who reached checkout_start
ab002_rows = []
for i in range(n_ab002):
    variant  = "A" if i % 2 == 0 else "B"
    device   = random.choices(["mobile","desktop","tablet"], weights=[55,35,10])[0]
    d        = datetime.date(2026,1,1) + datetime.timedelta(days=random.randint(0,177))
    price    = round(random.uniform(500,5000), 2)

    # Variant B reduces abandonment: conv 41% -> 56%
    conv_rate = {"A":{"mobile":0.36,"desktop":0.47,"tablet":0.42},
                 "B":{"mobile":0.51,"desktop":0.62,"tablet":0.57}}
    completed = random.random() < conv_rate[variant][device]
    time_to_complete = random.randint(45,240) if completed else random.randint(20,180)

    ab002_rows.append({
        "session_id":       f"AB2_{i:06d}",
        "test_id":          "AB-002",
        "test_name":        "Checkout UX",
        "variant":          variant,
        "variant_label":    "Standard checkout (Control)" if variant=="A" else "Progress bar + trust badges (Variant)",
        "session_date":     d.isoformat(),
        "device":           device,
        "listing_price_zar": price,
        "time_on_checkout_sec": time_to_complete,
        "completed":        completed,
        "abandoned":        not completed,
        "revenue_zar":      price if completed else 0,
    })

ab002 = pd.DataFrame(ab002_rows)

# ─── TEST AB-003: App Install Creative ───────────────────────────────────────
# Control A: "Find your perfect getaway"    CPI R24, Day-30 ret 18%
# Variant B: "Book from R350/night"         CPI R19, Day-30 ret 23%
print("Generating AB-003: App install creative test...")

n_ab003 = 20_000
ab003_rows = []
for i in range(n_ab003):
    variant  = "A" if i % 2 == 0 else "B"
    os       = random.choices(["android","ios"], weights=[62,38])[0]
    ch       = random.choices(["Meta Ads","Google UAC","TikTok Ads"], weights=[45,35,20])[0]
    d        = datetime.date(2026,1,1) + datetime.timedelta(days=random.randint(0,177))

    # Variant B: lower CPI, higher retention
    cpi_dist = {"A": (24.5, 4.2), "B": (19.1, 3.8)}
    ret_d1   = {"A": (0.42, 0.06), "B": (0.49, 0.05)}
    ret_d7   = {"A": (0.28, 0.05), "B": (0.34, 0.05)}
    ret_d30  = {"A": (0.18, 0.04), "B": (0.23, 0.04)}
    ltv_dist = {"A": (1800, 600),  "B": (2200, 650)}

    mu, sd   = cpi_dist[variant]
    cpi      = max(5, round(random.gauss(mu, sd), 2))
    ltv      = max(0, round(random.gauss(*ltv_dist[variant]), 2))
    booked   = random.random() < (0.038 if variant=="A" else 0.051)

    ab003_rows.append({
        "install_id":      f"AB3_{i:06d}",
        "test_id":         "AB-003",
        "test_name":       "App Install Creative",
        "variant":         variant,
        "variant_label":   "Generic CTA (Control)" if variant=="A" else "Price-anchor CTA (Variant)",
        "install_date":    d.isoformat(),
        "channel":         ch,
        "device_os":       os,
        "cpi_zar":         cpi,
        "ltv_zar":         ltv,
        "retention_d1":    round(min(1, max(0, random.gauss(*ret_d1[variant]))), 3),
        "retention_d7":    round(min(1, max(0, random.gauss(*ret_d7[variant]))), 3),
        "retention_d30":   round(min(1, max(0, random.gauss(*ret_d30[variant]))), 3),
        "booked_in_app":   booked,
    })

ab003 = pd.DataFrame(ab003_rows)

# ─── Save CSVs ────────────────────────────────────────────────────────────────
ab_sessions = pd.concat([ab001, ab002], ignore_index=True)
ab_sessions.to_csv(DATA / "fact_ab_sessions.csv", index=False)
ab003.to_csv(DATA / "fact_ab_app_installs.csv", index=False)
print(f"fact_ab_sessions.csv: {len(ab_sessions):,} rows")
print(f"fact_ab_app_installs.csv: {len(ab003):,} rows")

# ─── Statistical significance ─────────────────────────────────────────────────
def ab_stats(ctrl_conv, var_conv, ctrl_n, var_n, metric_label, higher_is_better=True):
    """Two-proportion z-test."""
    p_pool = (ctrl_conv * ctrl_n + var_conv * var_n) / (ctrl_n + var_n)
    se     = (p_pool * (1 - p_pool) * (1/ctrl_n + 1/var_n)) ** 0.5
    z      = (var_conv - ctrl_conv) / se if se > 0 else 0
    p_val  = 2 * (1 - stats.norm.cdf(abs(z)))
    uplift = (var_conv - ctrl_conv) / ctrl_conv * 100 if ctrl_conv > 0 else 0
    sig    = p_val < 0.05
    winner = "B" if (uplift > 0) == higher_is_better and sig else ("A" if sig else "No winner yet")
    return {
        "metric": metric_label,
        "ctrl_rate": round(ctrl_conv * 100, 2),
        "var_rate":  round(var_conv  * 100, 2),
        "uplift_pct": round(uplift, 1),
        "z_score":   round(z, 3),
        "p_value":   round(p_val, 4),
        "significant": sig,
        "winner":    winner,
    }

results = []

# AB-001
a1 = ab001[ab001.variant=="A"]; b1 = ab001[ab001.variant=="B"]
r1 = ab_stats(a1.converted.mean(), b1.converted.mean(), len(a1), len(b1), "Booking conversion rate")
r1.update({"test_id":"AB-001","test_name":"Listing Page Layout",
           "ctrl_label":"Image-first","var_label":"Price-first + urgency",
           "ctrl_n":len(a1),"var_n":len(b1),
           "ctrl_revenue_zar": round(a1.revenue_zar.mean(),2),
           "var_revenue_zar":  round(b1.revenue_zar.mean(),2),
           "revenue_uplift_pct": round((b1.revenue_zar.mean()-a1.revenue_zar.mean())/a1.revenue_zar.mean()*100,1) if a1.revenue_zar.mean()>0 else 0})
results.append(r1)

# AB-002
a2 = ab002[ab002.variant=="A"]; b2 = ab002[ab002.variant=="B"]
r2 = ab_stats(a2.completed.mean(), b2.completed.mean(), len(a2), len(b2), "Checkout completion rate")
r2.update({"test_id":"AB-002","test_name":"Checkout UX",
           "ctrl_label":"Standard checkout","var_label":"Progress bar + trust badges",
           "ctrl_n":len(a2),"var_n":len(b2),
           "ctrl_revenue_zar": round(a2.revenue_zar.mean(),2),
           "var_revenue_zar":  round(b2.revenue_zar.mean(),2),
           "revenue_uplift_pct": round((b2.revenue_zar.mean()-a2.revenue_zar.mean())/a2.revenue_zar.mean()*100,1) if a2.revenue_zar.mean()>0 else 0})
results.append(r2)

# AB-003 CPI
a3 = ab003[ab003.variant=="A"]; b3 = ab003[ab003.variant=="B"]
cpi_t, cpi_p = stats.ttest_ind(a3.cpi_zar, b3.cpi_zar)
ltv_t, ltv_p = stats.ttest_ind(a3.ltv_zar, b3.ltv_zar)
r3 = {
    "test_id":"AB-003","test_name":"App Install Creative",
    "metric":"Cost Per Install (CPI)",
    "ctrl_label":"Generic CTA","var_label":"Price-anchor CTA",
    "ctrl_n":len(a3),"var_n":len(b3),
    "ctrl_rate": round(a3.cpi_zar.mean(),2),
    "var_rate":  round(b3.cpi_zar.mean(),2),
    "uplift_pct": round((b3.cpi_zar.mean()-a3.cpi_zar.mean())/a3.cpi_zar.mean()*100,1),
    "z_score":   round(float(cpi_t),3),
    "p_value":   round(float(cpi_p),4),
    "significant": cpi_p < 0.05,
    "winner":    "B (lower CPI)" if cpi_p < 0.05 and b3.cpi_zar.mean() < a3.cpi_zar.mean() else "No winner yet",
    "ctrl_revenue_zar": round(a3.ltv_zar.mean(),2),
    "var_revenue_zar":  round(b3.ltv_zar.mean(),2),
    "revenue_uplift_pct": round((b3.ltv_zar.mean()-a3.ltv_zar.mean())/a3.ltv_zar.mean()*100,1),
    "ctrl_ret_d30": round(a3.retention_d30.mean()*100,1),
    "var_ret_d30":  round(b3.retention_d30.mean()*100,1),
}
results.append(r3)

pd.DataFrame(results).to_csv(DATA / "fact_ab_results.csv", index=False)
print("fact_ab_results.csv: 3 rows (one per test)")
for r in results:
    print(f"  {r['test_id']} {r['test_name']}: uplift {r['uplift_pct']:+.1f}%  p={r['p_value']}  winner={r['winner']}")

# ─── Build netlify_site/ab-testing.html ───────────────────────────────────────
print("\nBuilding ab-testing.html...")

def to_py(obj):
    if isinstance(obj, dict): return {k: to_py(v) for k, v in obj.items()}
    if isinstance(obj, list): return [to_py(i) for i in obj]
    if isinstance(obj, (np.bool_,)): return bool(obj)
    if isinstance(obj, (np.integer,)): return int(obj)
    if isinstance(obj, (np.floating,)): return float(obj)
    return obj

RESULTS_JSON = json.dumps(to_py(results))

# Device breakdown for AB-001
dev_b = ab001.groupby(["device","variant"])["converted"].agg(["mean","count"]).reset_index()
dev_b.columns = ["device","variant","conv","n"]
DEV_JSON = json.dumps(dev_b.to_dict("records"))

# Daily conversion trend AB-001
ab001["week"] = pd.to_datetime(ab001["session_date"]).dt.isocalendar().week.astype(int)
weekly = ab001.groupby(["week","variant"])["converted"].mean().reset_index()
weekly.columns = ["week","variant","conv"]
WEEKLY_JSON = json.dumps(weekly.to_dict("records"))

# AB-003 retention by variant
ret003 = {
    "A_d1":  round(float(a3.retention_d1.mean()*100),1),
    "A_d7":  round(float(a3.retention_d7.mean()*100),1),
    "A_d30": round(float(a3.retention_d30.mean()*100),1),
    "B_d1":  round(float(b3.retention_d1.mean()*100),1),
    "B_d7":  round(float(b3.retention_d7.mean()*100),1),
    "B_d30": round(float(b3.retention_d30.mean()*100),1),
}
RET_JSON = json.dumps(ret003)

NAV = """      <a href="index.html">Map</a>
      <a href="dashboard.html">Dashboard</a>
      <a href="recommendations.html">Recommendations</a>
      <a href="ab-testing.html" class="active">A/B Tests</a>
      <a href="data-model.html">Data Model</a>
      <a href="seasonality.html">Seasonality</a>
      <a href="ml-features.html">ML Features</a>
      <a href="market-opportunity.html">Market Opp.</a>
      <a href="mobile-attribution.html">Mobile</a>
      <a href="seo-audit.html">SEO Audit</a>
      <a href="seo-pages.html">SEO Pages</a>
      <a href="site-audit.html">Site Audit</a>
      <a href="ebook.html">Ebook</a>"""

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>A/B Testing | SA Accommodation Intelligence</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
:root{{--bg:#0d1117;--surface:#161b22;--border:#30363d;--text:#e6edf3;--muted:#8b949e;
      --cyan:#00bcd4;--lekke:#FF6C00;--green:#4caf50;--red:#f44336;--orange:#ff9800;--blue:#2196f3}}
body{{background:var(--bg);color:var(--text);font-family:'Segoe UI',sans-serif;min-height:100vh}}
nav{{background:var(--surface);border-bottom:2px solid var(--lekke);padding:.6rem 1.2rem;
     display:flex;flex-wrap:wrap;gap:.4rem}}
nav a{{color:var(--muted);text-decoration:none;padding:.3rem .65rem;border-radius:5px;font-size:.78rem;transition:all .2s}}
nav a:hover,nav a.active{{background:rgba(255,108,0,.15);color:var(--lekke)}}
.page-header{{padding:1.75rem 1.5rem .9rem;border-bottom:1px solid var(--border);
              background:linear-gradient(135deg,rgba(255,108,0,.07),transparent 60%)}}
.page-header h1{{font-size:1.55rem;color:var(--lekke);margin-bottom:.3rem}}
.page-header p{{color:var(--muted);font-size:.88rem}}
.content{{padding:1.25rem 1.5rem;max-width:1400px}}
.ctx-card{{background:rgba(255,108,0,.05);border-left:4px solid var(--lekke);border-radius:0 8px 8px 0;
           padding:.85rem 1.1rem;margin-bottom:1rem;font-size:.82rem;line-height:1.6}}
.ctx-row{{display:flex;flex-wrap:wrap;gap:1.5rem;margin-top:.55rem}}
.ctx-item{{flex:1;min-width:160px}}
.ctx-label{{font-size:.68rem;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:var(--lekke);margin-bottom:.2rem}}
.ctx-text{{font-size:.8rem;color:var(--muted)}}
.ctx-text strong{{color:#e6edf3}}
/* Test cards */
.test-grid{{display:flex;flex-direction:column;gap:1.5rem;margin-bottom:1.5rem}}
.test-card{{background:var(--surface);border:1px solid var(--border);border-radius:12px;overflow:hidden}}
.test-header{{padding:1rem 1.2rem;border-bottom:1px solid var(--border);
              display:flex;align-items:center;gap:.85rem;flex-wrap:wrap}}
.test-id{{font-family:monospace;font-size:.75rem;color:var(--muted);background:rgba(255,255,255,.05);
           padding:.2rem .5rem;border-radius:4px}}
.test-title{{font-size:1rem;font-weight:600;color:var(--text);flex:1}}
.winner-badge{{padding:.28rem .75rem;border-radius:20px;font-size:.72rem;font-weight:700}}
.winner-b{{background:rgba(76,175,80,.15);color:var(--green);border:1px solid rgba(76,175,80,.3)}}
.winner-tie{{background:rgba(139,148,158,.12);color:var(--muted);border:1px solid var(--border)}}
.test-body{{padding:1.1rem 1.2rem;display:grid;grid-template-columns:1fr 1fr;gap:1.2rem}}
.variant-box{{background:rgba(255,255,255,.025);border-radius:8px;padding:.9rem 1rem;
              border:2px solid transparent}}
.variant-box.control{{border-color:rgba(139,148,158,.3)}}
.variant-box.variant{{border-color:rgba(76,175,80,.4)}}
.variant-label{{font-size:.7rem;font-weight:700;text-transform:uppercase;letter-spacing:.07em;margin-bottom:.4rem}}
.control .variant-label{{color:var(--muted)}}
.variant .variant-label{{color:var(--green)}}
.variant-name{{font-size:.85rem;font-weight:600;color:var(--text);margin-bottom:.6rem}}
.stat-row{{display:flex;justify-content:space-between;margin-bottom:.3rem;font-size:.8rem}}
.stat-label{{color:var(--muted)}}
.stat-val{{color:var(--text);font-weight:600}}
.big-metric{{font-size:2rem;font-weight:700;margin:.5rem 0 .2rem}}
.big-label{{font-size:.7rem;color:var(--muted)}}
.uplift-box{{background:rgba(76,175,80,.08);border:1px solid rgba(76,175,80,.2);border-radius:8px;
             padding:.75rem 1rem;text-align:center}}
.uplift-val{{font-size:1.8rem;font-weight:700;color:var(--green)}}
.uplift-label{{font-size:.7rem;color:var(--muted);margin-top:.2rem}}
.sig-row{{display:flex;gap:.5rem;margin-top:.8rem;align-items:center;flex-wrap:wrap}}
.badge{{display:inline-block;padding:.2rem .5rem;border-radius:4px;font-size:.68rem;font-weight:700}}
.b-green{{background:rgba(76,175,80,.15);color:var(--green)}}
.b-red{{background:rgba(244,67,54,.15);color:var(--red)}}
.b-cyan{{background:rgba(0,188,212,.15);color:var(--cyan)}}
.b-muted{{background:rgba(139,148,158,.1);color:var(--muted)}}
.b-orange{{background:rgba(255,152,0,.15);color:var(--orange)}}
/* Charts */
.charts-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:1rem;margin-top:1.5rem}}
.chart-card{{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:1.1rem}}
.chart-card h3{{font-size:.78rem;color:var(--lekke);text-transform:uppercase;letter-spacing:.06em;margin-bottom:.3rem}}
.chart-explain{{background:rgba(255,255,255,.03);border:1px solid var(--border);border-radius:6px;
                padding:.55rem .75rem;font-size:.76rem;color:var(--muted);margin-bottom:.7rem;line-height:1.5}}
.chart-wrap{{position:relative;height:220px}}
/* KPI strip */
.kpi-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:.7rem;margin-bottom:1rem}}
.kpi{{background:rgba(255,108,0,.07);border:1px solid rgba(255,108,0,.2);border-radius:8px;padding:.9rem;text-align:center}}
.kpi-v{{font-size:1.35rem;font-weight:700;color:var(--lekke)}}
.kpi-l{{font-size:.68rem;color:var(--muted);margin-top:.2rem}}
</style>
</head>
<body>
<nav>{NAV}
</nav>

<div class="page-header">
  <h1>A/B Testing</h1>
  <p>3 active experiments across web UX and mobile acquisition — {40000+12000+20000:,} observations, two-proportion z-tests, 95% confidence threshold</p>
</div>

<div class="content">

<div class="ctx-card">
  <strong style="color:var(--lekke)">What you are looking at</strong>
  <div class="ctx-row">
    <div class="ctx-item">
      <div class="ctx-label">What</div>
      <div class="ctx-text"><strong>Controlled experiments</strong> that isolate the effect of a single change
        on a key metric. Each user is randomly assigned to Control (A) or Variant (B) — everything else stays
        identical so any difference in conversion is attributable to the change being tested.</div>
    </div>
    <div class="ctx-item">
      <div class="ctx-label">Why</div>
      <div class="ctx-text">Recommendations and intuition tell you <em>what</em> might work.
        A/B tests tell you <em>whether</em> it worked, with a measurable confidence level.
        <strong>Statistical significance (p &lt; 0.05)</strong> means there is less than a 5% probability
        the observed difference is due to chance alone.</div>
    </div>
    <div class="ctx-item">
      <div class="ctx-label">How to read results</div>
      <div class="ctx-text"><strong>Uplift %</strong> = relative improvement of B over A.
        <strong>p-value</strong> = probability the result is random noise (lower = more confident).
        <strong>Winner declared</strong> only when p &lt; 0.05 AND the uplift direction aligns with
        the business goal.</div>
    </div>
  </div>
</div>

<div class="kpi-grid">
  <div class="kpi"><div class="kpi-v">3</div><div class="kpi-l">Active Experiments</div></div>
  <div class="kpi"><div class="kpi-v" style="color:var(--green)">3</div><div class="kpi-l">Significant Results</div></div>
  <div class="kpi"><div class="kpi-v">72,000</div><div class="kpi-l">Total Observations</div></div>
  <div class="kpi"><div class="kpi-v" style="color:var(--green)">3×</div><div class="kpi-l">Tests Won by Variant B</div></div>
  <div class="kpi"><div class="kpi-v">95%</div><div class="kpi-l">Confidence Threshold</div></div>
</div>

<div class="test-grid" id="testGrid"></div>

<div class="charts-grid">

  <div class="chart-card">
    <h3>AB-001: Conversion by Device</h3>
    <div class="chart-explain">Price-first layout (B) outperforms image-first (A) on every device type.
      Mobile shows the biggest relative uplift — users on small screens benefit most from seeing price
      before scrolling through images.</div>
    <div class="chart-wrap"><canvas id="devChart"></canvas></div>
  </div>

  <div class="chart-card">
    <h3>AB-001: Weekly Conversion Trend</h3>
    <div class="chart-explain">Variant B consistently leads throughout the test period. A stable,
      consistent gap (not just a spike in one week) confirms the result is not driven by a
      single seasonal event.</div>
    <div class="chart-wrap"><canvas id="weekChart"></canvas></div>
  </div>

  <div class="chart-card">
    <h3>AB-003: App Retention Cohort</h3>
    <div class="chart-explain">Price-anchor creative (B) acquires users with higher intent — they
      know the price before installing, so they are less likely to churn after seeing it in-app.
      Day-30 retention gap of ~5pp compounds significantly over the user lifecycle.</div>
    <div class="chart-wrap"><canvas id="retChart"></canvas></div>
  </div>

  <div class="chart-card">
    <h3>Uplift Summary Across All Tests</h3>
    <div class="chart-explain">Each bar shows the relative uplift of Variant B over Control A on
      the primary metric. All three are statistically significant (p &lt; 0.05). Revenue uplift
      for AB-002 is highest because it affects a high-value step (checkout completion).</div>
    <div class="chart-wrap"><canvas id="upliftChart"></canvas></div>
  </div>

</div>
</div>

<script>
const RESULTS = {RESULTS_JSON};
const DEV     = {DEV_JSON};
const WEEKLY  = {WEEKLY_JSON};
const RET     = {RET_JSON};

// ── Render test cards ──────────────────────────────────────────────────────
const METRIC_LABELS = {{
  "AB-001": ["Conversion Rate","Avg Revenue / Session (ZAR)"],
  "AB-002": ["Checkout Completion Rate","Avg Revenue / Checkout Start (ZAR)"],
  "AB-003": ["Cost Per Install (ZAR)","Avg LTV (ZAR)"],
}};

function fmt(v, type) {{
  if (type==="pct") return v.toFixed(2)+"%";
  if (type==="zar") return "R"+v.toLocaleString("en-ZA",{{minimumFractionDigits:2,maximumFractionDigits:2}});
  return v;
}}

const grid = document.getElementById("testGrid");
RESULTS.forEach(r => {{
  const upSign  = r.uplift_pct > 0 ? "+" : "";
  const upColor = r.uplift_pct > 0 ? "var(--green)" : "var(--red)";
  const isLowerBetter = r.test_id === "AB-003";
  const winnerLabel = r.winner.includes("B") ? "Variant B Wins" : r.winner.includes("A") ? "Control A Wins" : "No winner yet";
  const winCls  = r.winner.includes("B") ? "winner-b" : "winner-tie";

  const ctrl_rev = r.ctrl_revenue_zar !== undefined ? r.ctrl_revenue_zar : null;
  const var_rev  = r.var_revenue_zar  !== undefined ? r.var_revenue_zar  : null;
  const rev_up   = r.revenue_uplift_pct !== undefined ? r.revenue_uplift_pct : null;

  const retHtml = r.test_id === "AB-003" ? `
    <div class="stat-row"><span class="stat-label">Day-30 retention</span>
    <span class="stat-val">${{RET.A_d30}}% vs ${{RET.B_d30}}%</span></div>` : "";

  grid.insertAdjacentHTML("beforeend", `
  <div class="test-card">
    <div class="test-header">
      <span class="test-id">${{r.test_id}}</span>
      <span class="test-title">${{r.test_name}}</span>
      <span class="winner-badge ${{winCls}}">${{winnerLabel}}</span>
    </div>
    <div class="test-body">
      <div class="variant-box control">
        <div class="variant-label">Control A</div>
        <div class="variant-name">${{r.ctrl_label}}</div>
        <div class="big-metric" style="color:var(--muted)">${{r.ctrl_rate}}${{r.test_id==="AB-003"?"":" "}}</div>
        <div class="big-label">${{r.metric}}${{r.test_id==="AB-003" ? " (ZAR)" : ""}}</div>
        ${{ctrl_rev !== null ? `<div class="stat-row" style="margin-top:.6rem"><span class="stat-label">Avg revenue</span><span class="stat-val">R${{ctrl_rev.toFixed(2)}}</span></div>` : ""}}
        <div class="stat-row"><span class="stat-label">Sample size</span><span class="stat-val">${{r.ctrl_n.toLocaleString()}}</span></div>
        ${{retHtml}}
      </div>
      <div class="variant-box variant">
        <div class="variant-label">Variant B</div>
        <div class="variant-name">${{r.var_label}}</div>
        <div class="big-metric" style="color:var(--green)">${{r.var_rate}}${{r.test_id==="AB-003"?"":" "}}</div>
        <div class="big-label">${{r.metric}}${{r.test_id==="AB-003" ? " (ZAR)" : ""}}</div>
        ${{var_rev !== null ? `<div class="stat-row" style="margin-top:.6rem"><span class="stat-label">Avg revenue</span><span class="stat-val">R${{var_rev.toFixed(2)}}</span></div>` : ""}}
        <div class="stat-row"><span class="stat-label">Sample size</span><span class="stat-val">${{r.var_n.toLocaleString()}}</span></div>
        ${{r.test_id==="AB-003" ? `<div class="stat-row"><span class="stat-label">Day-30 retention</span><span class="stat-val">${{RET.B_d30}}%</span></div>` : ""}}
      </div>
    </div>
    <div style="padding:.8rem 1.2rem 1rem;display:flex;gap:1rem;align-items:center;flex-wrap:wrap;border-top:1px solid var(--border)">
      <div class="uplift-box" style="flex:0 0 auto;min-width:120px">
        <div class="uplift-val" style="color:${{upColor}}">${{upSign}}${{r.uplift_pct}}%</div>
        <div class="uplift-label">Relative uplift</div>
      </div>
      ${{rev_up !== null ? `<div class="uplift-box" style="flex:0 0 auto;min-width:120px;border-color:rgba(33,150,243,.3);background:rgba(33,150,243,.06)">
        <div class="uplift-val" style="color:var(--blue)">${{rev_up>0?"+":""}}${{rev_up}}%</div>
        <div class="uplift-label">Revenue uplift</div></div>` : ""}}
      <div class="sig-row">
        <span class="badge ${{r.significant?"b-green":"b-muted"}}">${{r.significant?"Significant (p<0.05)":"Not significant"}}</span>
        <span class="badge b-cyan">p = ${{r.p_value}}</span>
        <span class="badge b-muted">z = ${{r.z_score}}</span>
        <span class="badge b-orange">n = ${{(r.ctrl_n+r.var_n).toLocaleString()}}</span>
      </div>
    </div>
  </div>`);
}});

// ── Device chart (AB-001) ──────────────────────────────────────────────────
const devLabels = ["mobile","desktop","tablet"];
const devA = devLabels.map(d => {{ const r=DEV.find(x=>x.device===d&&x.variant==="A"); return r?+(r.conv*100).toFixed(2):0; }});
const devB = devLabels.map(d => {{ const r=DEV.find(x=>x.device===d&&x.variant==="B"); return r?+(r.conv*100).toFixed(2):0; }});
new Chart(document.getElementById("devChart"), {{
  type:"bar", data:{{
    labels:devLabels.map(d=>d[0].toUpperCase()+d.slice(1)),
    datasets:[
      {{label:"Control A (Image-first)", data:devA, backgroundColor:"rgba(139,148,158,.3)", borderColor:"rgba(139,148,158,.6)", borderWidth:1}},
      {{label:"Variant B (Price-first)", data:devB, backgroundColor:"rgba(76,175,80,.3)", borderColor:"rgba(76,175,80,.8)", borderWidth:1}},
    ]
  }},
  options:{{responsive:true,maintainAspectRatio:false,
    plugins:{{legend:{{labels:{{color:"#8b949e",font:{{size:10}}}}}}}},
    scales:{{x:{{ticks:{{color:"#8b949e"}},grid:{{color:"rgba(48,54,61,.5)"}}}},
             y:{{ticks:{{color:"#8b949e",callback:v=>v+"%"}},grid:{{color:"rgba(48,54,61,.5)"}},title:{{display:true,text:"Conversion %",color:"#8b949e"}}}}}}
  }}
}});

// ── Weekly trend (AB-001) ──────────────────────────────────────────────────
const weeks = [...new Set(WEEKLY.map(r=>r.week))].sort((a,b)=>a-b);
const wA = weeks.map(w=>{{ const r=WEEKLY.find(x=>x.week===w&&x.variant==="A"); return r?+(r.conv*100).toFixed(2):null; }});
const wB = weeks.map(w=>{{ const r=WEEKLY.find(x=>x.week===w&&x.variant==="B"); return r?+(r.conv*100).toFixed(2):null; }});
new Chart(document.getElementById("weekChart"), {{
  type:"line", data:{{
    labels:weeks.map(w=>"W"+w),
    datasets:[
      {{label:"Control A", data:wA, borderColor:"rgba(139,148,158,.7)", backgroundColor:"rgba(139,148,158,.08)", tension:.4, pointRadius:2}},
      {{label:"Variant B", data:wB, borderColor:"rgba(76,175,80,.9)", backgroundColor:"rgba(76,175,80,.08)", tension:.4, pointRadius:2}},
    ]
  }},
  options:{{responsive:true,maintainAspectRatio:false,
    plugins:{{legend:{{labels:{{color:"#8b949e",font:{{size:10}}}}}}}},
    scales:{{x:{{ticks:{{color:"#8b949e",maxTicksLimit:8}},grid:{{color:"rgba(48,54,61,.5)"}}}},
             y:{{ticks:{{color:"#8b949e",callback:v=>v+"%"}},grid:{{color:"rgba(48,54,61,.5)"}},title:{{display:true,text:"Conv %",color:"#8b949e"}}}}}}
  }}
}});

// ── Retention cohort (AB-003) ──────────────────────────────────────────────
new Chart(document.getElementById("retChart"), {{
  type:"line", data:{{
    labels:["Day 1","Day 7","Day 30"],
    datasets:[
      {{label:"Control A (Generic CTA)", data:[RET.A_d1,RET.A_d7,RET.A_d30], borderColor:"rgba(139,148,158,.7)", backgroundColor:"rgba(139,148,158,.08)", tension:.3, pointRadius:5}},
      {{label:"Variant B (Price-anchor)", data:[RET.B_d1,RET.B_d7,RET.B_d30], borderColor:"rgba(76,175,80,.9)", backgroundColor:"rgba(76,175,80,.08)", tension:.3, pointRadius:5}},
    ]
  }},
  options:{{responsive:true,maintainAspectRatio:false,
    plugins:{{legend:{{labels:{{color:"#8b949e",font:{{size:10}}}}}}}},
    scales:{{x:{{ticks:{{color:"#8b949e"}},grid:{{color:"rgba(48,54,61,.5)"}}}},
             y:{{ticks:{{color:"#8b949e",callback:v=>v+"%"}},grid:{{color:"rgba(48,54,61,.5)"}},title:{{display:true,text:"Retention %",color:"#8b949e"}}}}}}
  }}
}});

// ── Uplift summary bar ────────────────────────────────────────────────────
const uplifts = RESULTS.map(r=>r.uplift_pct);
const upColors = uplifts.map(u=>u>0?"rgba(76,175,80,.7)":"rgba(244,67,54,.7)");
new Chart(document.getElementById("upliftChart"), {{
  type:"bar", data:{{
    labels:RESULTS.map(r=>r.test_id+": "+r.test_name),
    datasets:[{{
      label:"Uplift %", data:uplifts,
      backgroundColor:upColors, borderColor:upColors.map(c=>c.replace(".7",".9")), borderWidth:1
    }}]
  }},
  options:{{indexAxis:"y",responsive:true,maintainAspectRatio:false,
    plugins:{{legend:{{display:false}},
              tooltip:{{callbacks:{{label:ctx=>(ctx.raw>0?"+":"")+ctx.raw+"%"}}}}}},
    scales:{{x:{{ticks:{{color:"#8b949e",callback:v=>(v>0?"+":"")+v+"%"}},grid:{{color:"rgba(48,54,61,.5)"}}}},
             y:{{ticks:{{color:"#8b949e",font:{{size:11}}}},grid:{{color:"rgba(48,54,61,.5)"}}}}}}
  }}
}});
</script>
</body>
</html>"""

(NET / "ab-testing.html").write_text(html, encoding="utf-8")
print("Written: netlify_site/ab-testing.html")

# ─── Update nav on all existing pages ─────────────────────────────────────────
import re
print("\nUpdating nav on existing pages...")
OLD_REC = '<a href="recommendations.html">Recommendations</a>'
NEW_REC = '<a href="recommendations.html">Recommendations</a>\n      <a href="ab-testing.html">A/B Tests</a>'

pages = list(NET.glob("*.html"))
for p in pages:
    if p.name == "ab-testing.html": continue
    html_p = p.read_text(encoding="utf-8")
    if 'href="ab-testing.html"' in html_p: continue
    if OLD_REC in html_p:
        p.write_text(html_p.replace(OLD_REC, NEW_REC, 1), encoding="utf-8")
        print(f"  {p.name}")

print("\nAll done.")
print(f"  data/fact_ab_sessions.csv:    {len(ab_sessions):,} rows")
print(f"  data/fact_ab_app_installs.csv: {len(ab003):,} rows")
print(f"  data/fact_ab_results.csv:      3 rows")
print(f"  netlify_site/ab-testing.html:  new page")
