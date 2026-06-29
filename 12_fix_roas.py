"""
12_fix_roas.py
Fixes unrealistic ROAS values across all data and pages.

Problem: lognormal(7.5, 0.9) produced avg LTV ~R1,800 with CPI ~R25 = ROAS ~72x
Reality: SA accommodation app ROAS is 3-8x (commission-based LTV ~R120-200)

Fix: regenerate LTV using lognormal(5.1, 0.4) -> avg ~R164, ROAS 3-6x with CPI R25-45
"""
import json, random
from pathlib import Path
import pandas as pd
import numpy as np

random.seed(42)
np.random.seed(42)

BASE = Path(__file__).parent
DATA = BASE / "data"
NET  = BASE / "netlify_site"

# ─── 1. Fix appsflyer_installs.csv LTV values ────────────────────────────────
print("Fixing appsflyer_installs.csv LTV values...")
af = pd.read_csv(DATA / "appsflyer_installs.csv")

# Realistic LTV: commission ~10% on avg R1,800 booking * 0.9 bookings/user lifetime
# = ~R162 avg LTV. lognormal(5.1, 0.4) gives mean ~e^5.1 = R164
af["ltv_zar"] = np.random.lognormal(5.1, 0.4, size=len(af)).round(2)

# Also fix CPI to be realistic: R25-55 for paid channels
paid_mask = ~af["channel"].isin(["Organic", "Direct", "Email"])
af.loc[paid_mask, "cost_zar"] = np.random.uniform(25, 55, size=paid_mask.sum()).round(2)
af.loc[~paid_mask, "cost_zar"] = 0

# Bookings: ~4% of installs lead to a booking
af["bookings_30d"] = (np.random.random(len(af)) < 0.04).astype(int)

af.to_csv(DATA / "appsflyer_installs.csv", index=False)

# ─── 2. Recalculate campaigns with realistic ROAS ────────────────────────────
print("Recalculating appsflyer_campaigns.csv...")
cg = af.groupby(["channel","campaign"]).agg(
    installs=("install_id","count"),
    total_cost_zar=("cost_zar","sum"),
    total_ltv_zar=("ltv_zar","sum"),
    bookings=("bookings_30d","sum")
).reset_index()

cg["cpi_zar"]   = (cg["total_cost_zar"] / cg["installs"]).round(2)
cg["roas"]      = (cg["total_ltv_zar"] / cg["total_cost_zar"].replace(0, np.nan)).round(2).fillna(0)
cg["conv_rate"] = (cg["bookings"] / cg["installs"] * 100).round(1)
cg.to_csv(DATA / "appsflyer_campaigns.csv", index=False)

# Print ROAS summary for verification
print("\nChannel ROAS check:")
ch_summary = af.groupby("channel").agg(
    installs=("install_id","count"),
    cost=("cost_zar","sum"),
    ltv=("ltv_zar","sum")
).reset_index()
ch_summary["roas"] = (ch_summary["ltv"] / ch_summary["cost"].replace(0,np.nan)).round(2).fillna(0)
ch_summary["cpi"]  = (ch_summary["cost"] / ch_summary["installs"]).round(2)
for _, r in ch_summary.sort_values("roas", ascending=False).iterrows():
    print(f"  {r['channel']:<15} CPI=R{r['cpi']:<6.2f} ROAS={r['roas']:.2f}x")

# ─── 3. Fix AB-003 LTV values in fact_ab_app_installs.csv ────────────────────
print("\nFixing fact_ab_app_installs.csv LTV values...")
ab3 = pd.read_csv(DATA / "fact_ab_app_installs.csv")

# A: generic CTA -> lower LTV, B: price-anchor -> higher LTV (realistic)
ltv_a = np.random.lognormal(5.0, 0.4, size=(ab3["variant"]=="A").sum()).round(2)
ltv_b = np.random.lognormal(5.2, 0.4, size=(ab3["variant"]=="B").sum()).round(2)
ab3.loc[ab3["variant"]=="A", "ltv_zar"] = ltv_a
ab3.loc[ab3["variant"]=="B", "ltv_zar"] = ltv_b

# Fix CPI too
cpi_a = np.random.normal(38, 5, size=(ab3["variant"]=="A").sum()).clip(20,65).round(2)
cpi_b = np.random.normal(30, 4, size=(ab3["variant"]=="B").sum()).clip(15,55).round(2)
ab3.loc[ab3["variant"]=="A", "cpi_zar"] = cpi_a
ab3.loc[ab3["variant"]=="B", "cpi_zar"] = cpi_b

ab3.to_csv(DATA / "fact_ab_app_installs.csv", index=False)

a3 = ab3[ab3.variant=="A"]
b3 = ab3[ab3.variant=="B"]
print(f"  Control A: avg CPI=R{a3.cpi_zar.mean():.2f}, avg LTV=R{a3.ltv_zar.mean():.2f}, ROAS={a3.ltv_zar.mean()/a3.cpi_zar.mean():.2f}x")
print(f"  Variant B: avg CPI=R{b3.cpi_zar.mean():.2f}, avg LTV=R{b3.ltv_zar.mean():.2f}, ROAS={b3.ltv_zar.mean()/b3.cpi_zar.mean():.2f}x")

# ─── 4. Rebuild recommendations.html channel table with correct ROAS ─────────
print("\nPatching recommendations.html with corrected ROAS data...")

ch_perf = ch_summary.copy()
ch_perf["roas"]      = ch_perf["roas"].fillna(0)
ch_perf["cpi"]       = ch_perf["cpi"].round(2)
ch_perf["conv_pct"]  = (af.groupby("channel")["bookings_30d"].mean() * 100).round(1).reindex(ch_perf["channel"]).values
ch_perf_json = ch_perf.sort_values("roas", ascending=False).rename(
    columns={"installs":"installs","cost":"total_cost_zar","ltv":"total_ltv_zar"}
).to_dict("records")

# Patch the JS in recommendations.html
rec_path = NET / "recommendations.html"
rec_html = rec_path.read_text(encoding="utf-8")

import re
# Replace the CH_JSON variable
new_ch_json = json.dumps(ch_perf_json)
rec_html = re.sub(r'const CH\s*=\s*\[.*?\];', f'const CH = {new_ch_json};', rec_html, flags=re.DOTALL)

# Also fix REC-001 title which showed ROAS 104x
rec_html = re.sub(
    r'Increase.*?ROAS [\d\.]+.*?is the platform.*?best performer',
    f"Increase Meta Ads budget — highest ROAS channel at {ch_summary[ch_summary.channel=='Meta Ads']['roas'].values[0]:.1f}x",
    rec_html
)
rec_html = re.sub(
    r'R[\d\.]+\.02 in booking revenue for every R1',
    f"R{ch_summary[ch_summary.channel=='Meta Ads']['roas'].values[0]:.2f} in booking revenue for every R1",
    rec_html
)

rec_path.write_text(rec_html, encoding="utf-8")
print("  recommendations.html patched")

# ─── 5. Patch ab-testing.html with corrected AB-003 numbers ──────────────────
print("Patching ab-testing.html with corrected AB-003 numbers...")
from scipy import stats as scipy_stats

ab_path = NET / "ab-testing.html"
ab_html = ab_path.read_text(encoding="utf-8")

cpi_t, cpi_p = scipy_stats.ttest_ind(a3.cpi_zar, b3.cpi_zar)
cpi_uplift   = round((b3.cpi_zar.mean() - a3.cpi_zar.mean()) / a3.cpi_zar.mean() * 100, 1)
ret_A_d30    = round(float(a3.retention_d30.mean()*100), 1)
ret_B_d30    = round(float(b3.retention_d30.mean()*100), 1)

new_ret = json.dumps({
    "A_d1": round(float(a3.retention_d1.mean()*100),1),
    "A_d7": round(float(a3.retention_d7.mean()*100),1),
    "A_d30": ret_A_d30,
    "B_d1": round(float(b3.retention_d1.mean()*100),1),
    "B_d7": round(float(b3.retention_d7.mean()*100),1),
    "B_d30": ret_B_d30,
})
ab_html = re.sub(r'const RET\s*=\s*\{.*?\};', f'const RET = {new_ret};', ab_html, flags=re.DOTALL)
ab_path.write_text(ab_html, encoding="utf-8")
print("  ab-testing.html patched")

print("\nAll ROAS values corrected. Summary:")
print(f"  Meta Ads ROAS:   {ch_summary[ch_summary.channel=='Meta Ads']['roas'].values[0]:.2f}x  (was ~104x)")
print(f"  Google UAC ROAS: {ch_summary[ch_summary.channel=='google_ads']['roas'].values[0]:.2f}x")
print(f"  TikTok ROAS:     {ch_summary[ch_summary.channel=='tiktok_ads']['roas'].values[0]:.2f}x")
print(f"  AB-003 CPI uplift: {cpi_uplift:+.1f}%  (was -22%)")
print(f"  AB-003 Day-30 retention: A={ret_A_d30}% vs B={ret_B_d30}%")
