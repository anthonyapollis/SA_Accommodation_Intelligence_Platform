"""
13_fix_realism.py
1. Differentiate ROAS by channel (Meta 5.2x, Google UAC 4.1x, TikTok 2.8x)
2. Bring AB-001 listing layout uplift from ~49% down to ~18%
"""
import json, re, random
from pathlib import Path
import pandas as pd
import numpy as np
from scipy import stats as scipy_stats

random.seed(7)
np.random.seed(7)

BASE = Path(__file__).parent
DATA = BASE / "data"
NET  = BASE / "netlify_site"

# ─── 1. Channel-differentiated LTV ───────────────────────────────────────────
print("Fixing channel-differentiated LTV / ROAS...")

# Target ROAS per channel (realistic SA travel app benchmarks):
# Meta Ads:   high intent retargeting  -> ROAS ~5.2x, CPI ~R42
# Google UAC: broad app campaigns      -> ROAS ~4.1x, CPI ~R38
# TikTok:     awareness / Gen-Z        -> ROAS ~2.8x, CPI ~R28
# Organic:    no cost                  -> infinite
# Email:      near-zero cost           -> very high
# Direct:     no cost                  -> infinite

CHANNEL_LTV = {
    "Meta Ads":   (np.log(42 * 5.2), 0.35),   # mean LTV ~R218
    "Google UAC": (np.log(38 * 4.1), 0.35),   # mean LTV ~R156
    "TikTok Ads": (np.log(28 * 2.8), 0.35),   # mean LTV ~R78
    "Organic":    (np.log(180),       0.40),
    "Email":      (np.log(160),       0.40),
    "Direct":     (np.log(170),       0.40),
}
CHANNEL_CPI = {
    "Meta Ads":   (42, 6),
    "Google UAC": (38, 5),
    "TikTok Ads": (28, 4),
    "Organic":    (0, 0),
    "Email":      (0, 0),
    "Direct":     (0, 0),
}

af = pd.read_csv(DATA / "appsflyer_installs.csv")
for ch, (mu, sd) in CHANNEL_LTV.items():
    mask = af["channel"] == ch
    af.loc[mask, "ltv_zar"] = np.random.lognormal(mu, sd, size=mask.sum()).round(2)
for ch, (mu, sd) in CHANNEL_CPI.items():
    mask = af["channel"] == ch
    if mu > 0:
        af.loc[mask, "cost_zar"] = np.random.normal(mu, sd, size=mask.sum()).clip(10, 100).round(2)
    else:
        af.loc[mask, "cost_zar"] = 0

af["bookings_30d"] = (np.random.random(len(af)) < 0.04).astype(int)
af.to_csv(DATA / "appsflyer_installs.csv", index=False)

# Recalculate campaigns
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

ch_summary = af.groupby("channel").agg(
    installs=("install_id","count"),
    cost=("cost_zar","sum"),
    ltv=("ltv_zar","sum"),
    bookings=("bookings_30d","sum")
).reset_index()
ch_summary["roas"] = (ch_summary["ltv"] / ch_summary["cost"].replace(0, np.nan)).round(2).fillna(0)
ch_summary["cpi"]  = (ch_summary["cost"] / ch_summary["installs"]).round(2)
ch_summary["conv_pct"] = (ch_summary["bookings"] / ch_summary["installs"] * 100).round(1)

print("\nChannel ROAS (corrected):")
for _, r in ch_summary.sort_values("roas", ascending=False).iterrows():
    print(f"  {r['channel']:<15} CPI=R{r['cpi']:<6.2f} ROAS={r['roas']:.2f}x")

# ─── 2. Fix AB-001: bring conversion rates closer (realistic ~18% uplift) ────
print("\nFixing AB-001 conversion rates for realistic uplift...")

ab_sess = pd.read_csv(DATA / "fact_ab_sessions.csv")
ab001   = ab_sess[ab_sess["test_id"] == "AB-001"].copy()
ab002   = ab_sess[ab_sess["test_id"] == "AB-002"].copy()

# Target: Control A ~3.8%, Variant B ~4.5%  -> uplift ~18%
DEVICE_CONV = {
    "A": {"mobile": 0.036, "desktop": 0.042, "tablet": 0.039},
    "B": {"mobile": 0.043, "desktop": 0.050, "tablet": 0.046},
}
new_conv = []
for _, row in ab001.iterrows():
    rate = DEVICE_CONV[row["variant"]].get(row["device"], 0.040)
    new_conv.append(random.random() < rate)
ab001["converted"] = new_conv
ab001["revenue_zar"] = [round(random.uniform(800, 4500), 2) if c else 0 for c in ab001["converted"]]

# Recombine and save
ab_sess_fixed = pd.concat([ab001, ab002], ignore_index=True)
ab_sess_fixed.to_csv(DATA / "fact_ab_sessions.csv", index=False)

# Verify
a1 = ab001[ab001.variant=="A"]
b1 = ab001[ab001.variant=="B"]
uplift = (b1.converted.mean() - a1.converted.mean()) / a1.converted.mean() * 100
p_pool = (a1.converted.sum() + b1.converted.sum()) / (len(a1) + len(b1))
se     = (p_pool*(1-p_pool)*(1/len(a1)+1/len(b1)))**0.5
z      = (b1.converted.mean() - a1.converted.mean()) / se
p_val  = 2*(1-scipy_stats.norm.cdf(abs(z)))
print(f"  Control A conv: {a1.converted.mean()*100:.2f}%")
print(f"  Variant B conv: {b1.converted.mean()*100:.2f}%")
print(f"  Uplift: {uplift:+.1f}%  p={p_val:.4f}  z={z:.2f}")

# ─── 3. Rebuild AB results and patch ab-testing.html ─────────────────────────
print("\nPatching ab-testing.html with corrected results...")

def to_py(obj):
    if isinstance(obj, dict):  return {k: to_py(v) for k,v in obj.items()}
    if isinstance(obj, list):  return [to_py(i) for i in obj]
    if isinstance(obj, (np.bool_,)):    return bool(obj)
    if isinstance(obj, (np.integer,)):  return int(obj)
    if isinstance(obj, (np.floating,)): return float(obj)
    return obj

# AB-001 result
r1 = {
    "test_id":"AB-001","test_name":"Listing Page Layout",
    "metric":"Booking conversion rate",
    "ctrl_label":"Image-first","var_label":"Price-first + urgency",
    "ctrl_n":int(len(a1)),"var_n":int(len(b1)),
    "ctrl_rate": round(a1.converted.mean()*100,2),
    "var_rate":  round(b1.converted.mean()*100,2),
    "uplift_pct": round(uplift,1),
    "z_score":   round(float(z),3),
    "p_value":   round(float(p_val),4),
    "significant": bool(p_val < 0.05),
    "winner":    "B" if p_val < 0.05 and uplift > 0 else "No winner yet",
    "ctrl_revenue_zar": round(float(a1.revenue_zar.mean()),2),
    "var_revenue_zar":  round(float(b1.revenue_zar.mean()),2),
    "revenue_uplift_pct": round((b1.revenue_zar.mean()-a1.revenue_zar.mean())/max(a1.revenue_zar.mean(),0.01)*100,1),
}

# AB-002 result (unchanged)
ab002_data = ab_sess_fixed[ab_sess_fixed["test_id"]=="AB-002"]
a2 = ab002_data[ab002_data.variant=="A"]
b2 = ab002_data[ab002_data.variant=="B"]
p2_pool = (a2.completed.sum()+b2.completed.sum())/(len(a2)+len(b2))
se2  = (p2_pool*(1-p2_pool)*(1/len(a2)+1/len(b2)))**0.5
z2   = (b2.completed.mean()-a2.completed.mean())/se2
p2   = 2*(1-scipy_stats.norm.cdf(abs(z2)))
up2  = (b2.completed.mean()-a2.completed.mean())/a2.completed.mean()*100
r2 = {
    "test_id":"AB-002","test_name":"Checkout UX",
    "metric":"Checkout completion rate",
    "ctrl_label":"Standard checkout","var_label":"Progress bar + trust badges",
    "ctrl_n":int(len(a2)),"var_n":int(len(b2)),
    "ctrl_rate": round(float(a2.completed.mean()*100),2),
    "var_rate":  round(float(b2.completed.mean()*100),2),
    "uplift_pct": round(float(up2),1),
    "z_score":   round(float(z2),3),
    "p_value":   round(float(p2),4),
    "significant": bool(p2 < 0.05),
    "winner":    "B" if p2 < 0.05 and up2 > 0 else "No winner yet",
    "ctrl_revenue_zar": round(float(a2.revenue_zar.mean()),2),
    "var_revenue_zar":  round(float(b2.revenue_zar.mean()),2),
    "revenue_uplift_pct": round((b2.revenue_zar.mean()-a2.revenue_zar.mean())/max(a2.revenue_zar.mean(),0.01)*100,1),
}

# AB-003 result
ab3 = pd.read_csv(DATA / "fact_ab_app_installs.csv")
a3  = ab3[ab3.variant=="A"]
b3  = ab3[ab3.variant=="B"]
cpi_t, cpi_p = scipy_stats.ttest_ind(a3.cpi_zar, b3.cpi_zar)
cpi_up = (b3.cpi_zar.mean()-a3.cpi_zar.mean())/a3.cpi_zar.mean()*100
r3 = {
    "test_id":"AB-003","test_name":"App Install Creative",
    "metric":"Cost Per Install (ZAR)",
    "ctrl_label":"Generic CTA","var_label":"Price-anchor CTA",
    "ctrl_n":int(len(a3)),"var_n":int(len(b3)),
    "ctrl_rate": round(float(a3.cpi_zar.mean()),2),
    "var_rate":  round(float(b3.cpi_zar.mean()),2),
    "uplift_pct": round(float(cpi_up),1),
    "z_score":   round(float(cpi_t),3),
    "p_value":   round(float(cpi_p),4),
    "significant": bool(cpi_p < 0.05),
    "winner":    "B (lower CPI)" if cpi_p < 0.05 and b3.cpi_zar.mean() < a3.cpi_zar.mean() else "No winner yet",
    "ctrl_revenue_zar": round(float(a3.ltv_zar.mean()),2),
    "var_revenue_zar":  round(float(b3.ltv_zar.mean()),2),
    "revenue_uplift_pct": round((b3.ltv_zar.mean()-a3.ltv_zar.mean())/max(a3.ltv_zar.mean(),0.01)*100,1),
    "ctrl_ret_d30": round(float(a3.retention_d30.mean()*100),1),
    "var_ret_d30":  round(float(b3.retention_d30.mean()*100),1),
}

RESULTS = to_py([r1, r2, r3])
NEW_RET  = to_py({
    "A_d1": round(float(a3.retention_d1.mean()*100),1),
    "A_d7": round(float(a3.retention_d7.mean()*100),1),
    "A_d30":round(float(a3.retention_d30.mean()*100),1),
    "B_d1": round(float(b3.retention_d1.mean()*100),1),
    "B_d7": round(float(b3.retention_d7.mean()*100),1),
    "B_d30":round(float(b3.retention_d30.mean()*100),1),
})

ab_html = (NET/"ab-testing.html").read_text(encoding="utf-8")
ab_html = re.sub(r'const RESULTS\s*=\s*\[.*?\];', f'const RESULTS = {json.dumps(RESULTS)};', ab_html, flags=re.DOTALL)
ab_html = re.sub(r'const RET\s*=\s*\{.*?\};',    f'const RET = {json.dumps(NEW_RET)};',    ab_html, flags=re.DOTALL)
(NET/"ab-testing.html").write_text(ab_html, encoding="utf-8")

# ─── 4. Patch recommendations.html channel data ───────────────────────────────
print("Patching recommendations.html channel data...")

ch_json = to_py(ch_summary.sort_values("roas", ascending=False).to_dict("records"))
rec_html = (NET/"recommendations.html").read_text(encoding="utf-8")
rec_html = re.sub(r'const CH\s*=\s*\[.*?\];', f'const CH = {json.dumps(ch_json)};', rec_html, flags=re.DOTALL)

# Fix REC-001 metric display
top_ch   = ch_summary.sort_values("roas",ascending=False).iloc[0]
rec_html = re.sub(r'"metric":"\d+\.\d+×"', f'"metric":"{top_ch.roas:.2f}x"', rec_html)
(NET/"recommendations.html").write_text(rec_html, encoding="utf-8")

print("\nFinal summary:")
print(f"  AB-001 uplift: {r1['uplift_pct']:+.1f}%  (was +49.5%)")
print(f"  AB-002 uplift: {r2['uplift_pct']:+.1f}%")
print(f"  AB-003 CPI uplift: {r3['uplift_pct']:+.1f}%")
for _, r in ch_summary.sort_values("roas",ascending=False).iterrows():
    if r["roas"] > 0:
        print(f"  {r['channel']:<15} ROAS={r['roas']:.2f}x  CPI=R{r['cpi']:.2f}")
print("\nDone.")
