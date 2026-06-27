"""
SA Accommodation Intelligence Platform
02_ml_models.py — Machine Learning: Price Prediction, Tier Classification, Demand Scoring

Models:
  1. Price Regression    — predict nightly price from listing type, region, reviews
  2. Tier Classifier     — classify Budget/Mid-Range/Premium/Luxury
  3. Demand Score Model  — predict demand_score (0–100) from listing features

Author: Anthony Apollis | 2026-06-27
"""

import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import seaborn as sns
from sklearn.ensemble import (
    GradientBoostingRegressor,
    RandomForestClassifier,
    GradientBoostingClassifier,
)
from sklearn.linear_model import Ridge
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.metrics import (
    mean_absolute_error,
    r2_score,
    accuracy_score,
    classification_report,
    confusion_matrix,
)
from sklearn.pipeline import Pipeline

warnings.filterwarnings("ignore")

BASE  = Path(__file__).parent
DATA  = BASE / "data"
PLOTS = BASE / "plots"
ML    = BASE / "ml"

# -- COLOUR PALETTE (SA / Google Cloud) ----------------------------------------
PALETTE = {
    "primary"   : "#4285F4",   # Google Blue
    "secondary" : "#0F9D58",   # Google Green
    "accent"    : "#FF6D00",   # SA Orange
    "warning"   : "#F4B400",   # Google Yellow
    "danger"    : "#DB4437",   # Google Red
    "teal"      : "#00BCD4",   # BigQuery Teal
    "purple"    : "#673AB7",   # Analytics Purple
    "bg"        : "#F8F9FA",
    "dark"      : "#1A1A2E",
}
TIER_COLORS = {
    "Budget"    : PALETTE["secondary"],
    "Mid-Range" : PALETTE["primary"],
    "Premium"   : PALETTE["accent"],
    "Luxury"    : PALETTE["warning"],
    "Unknown"   : "#AAAAAA",
}
plt.rcParams.update({
    "figure.facecolor" : PALETTE["bg"],
    "axes.facecolor"   : "white",
    "axes.grid"        : True,
    "grid.alpha"       : 0.3,
    "axes.spines.top"  : False,
    "axes.spines.right": False,
    "font.family"      : "DejaVu Sans",
})

# -- LOAD DATA -----------------------------------------------------------------
print("=" * 60)
print("ML Models — SA Accommodation Intelligence Platform")
print("=" * 60)

df = pd.read_csv(DATA / "accommodation_clean.csv")
print(f"  Loaded: {len(df):,} properties")

# Drop unknowns for model training
df_model = df.dropna(subset=["price_zar"]).copy()
df_model = df_model[df_model["price_tier"] != "Unknown"]
print(f"  Model-ready rows: {len(df_model):,}")

# -- FEATURE ENGINEERING -------------------------------------------------------
le_type   = LabelEncoder()
le_region = LabelEncoder()
le_city   = LabelEncoder()

df_model["listing_type_enc"] = le_type.fit_transform(df_model["listing_type"].fillna("Unknown"))
df_model["region_enc"]       = le_region.fit_transform(df_model["region"].fillna("Unknown"))
df_model["city_enc"]         = le_city.fit_transform(df_model["city"].fillna("Unknown"))
df_model["log_reviews"]      = np.log1p(df_model["review_count"].fillna(0))

FEATURES = ["listing_type_enc", "region_enc", "city_enc", "log_reviews"]
X = df_model[FEATURES].values
y_price = df_model["price_zar"].values
y_tier  = df_model["price_tier"].values
y_demand = df_model["demand_score"].values

y_tier_arr = np.array(y_tier)
idx = np.arange(len(X))
idx_train, idx_test = train_test_split(idx, test_size=0.2, random_state=42, stratify=y_tier_arr)
X_train, X_test           = X[idx_train], X[idx_test]
y_price_train, y_price_test = y_price[idx_train], y_price[idx_test]
y_tier_train, y_tier_test   = y_tier_arr[idx_train], y_tier_arr[idx_test]
y_dem_train, y_dem_test     = y_demand[idx_train], y_demand[idx_test]

print(f"  Train/Test split: {len(X_train):,} / {len(X_test):,}")

metrics = {}

# -- MODEL 1: PRICE REGRESSION (Gradient Boosting) -----------------------------
print("\n" + "-" * 60)
print("MODEL 1 — Price Regression (Gradient Boosting)")
print("-" * 60)

gbr = GradientBoostingRegressor(
    n_estimators=300, max_depth=4, learning_rate=0.05,
    subsample=0.8, min_samples_leaf=5, random_state=42
)
gbr.fit(X_train, y_price_train)
y_pred_price = gbr.predict(X_test)

mae  = mean_absolute_error(y_price_test, y_pred_price)
r2   = r2_score(y_price_test, y_pred_price)
mape = np.mean(np.abs((y_price_test - y_pred_price) / np.maximum(y_price_test, 1))) * 100

print(f"  MAE  : R{mae:.0f} (mean absolute error in ZAR)")
print(f"  R²   : {r2:.4f}")
print(f"  MAPE : {mape:.1f}%")

# Cross-validation
cv_r2 = cross_val_score(gbr, X, np.array(y_price), cv=5, scoring="r2")
print(f"  CV R²: {cv_r2.mean():.4f} ± {cv_r2.std():.4f}")

metrics["price_regression"] = {
    "model": "GradientBoostingRegressor", "mae_zar": round(mae, 2),
    "r2": round(r2, 4), "mape_pct": round(mape, 2),
    "cv_r2_mean": round(cv_r2.mean(), 4), "cv_r2_std": round(cv_r2.std(), 4),
}

# Feature importances — price
feat_imp_price = pd.Series(gbr.feature_importances_, index=["Listing Type","Region","City","Log Reviews"])

# Plot 1: Actual vs Predicted price
fig, axes = plt.subplots(1, 2, figsize=(14, 5))
fig.patch.set_facecolor(PALETTE["bg"])

ax = axes[0]
ax.scatter(y_price_test, y_pred_price, alpha=0.35, color=PALETTE["primary"],
           edgecolors="white", linewidths=0.3, s=40)
lim = max(y_price_test.max(), y_pred_price.max()) * 1.05
ax.plot([0, lim], [0, lim], "--", color=PALETTE["accent"], lw=1.5, label="Perfect prediction")
ax.set_xlabel("Actual Price (ZAR)", fontsize=11)
ax.set_ylabel("Predicted Price (ZAR)", fontsize=11)
ax.set_title(f"Model 1: Price Regression\nR² = {r2:.4f} | MAE = R{mae:.0f}", fontsize=12, fontweight="bold")
ax.legend(fontsize=9)

ax = axes[1]
feat_imp_price.sort_values().plot(kind="barh", ax=ax, color=[PALETTE["teal"],PALETTE["primary"],PALETTE["secondary"],PALETTE["accent"]])
ax.set_title("Feature Importance — Price", fontsize=12, fontweight="bold")
ax.set_xlabel("Importance Score")

plt.tight_layout(pad=2)
plt.savefig(PLOTS / "ml_01_price_regression.png", dpi=150, bbox_inches="tight")
plt.close()
print("  Plot saved: plots/ml_01_price_regression.png")

# -- MODEL 2: TIER CLASSIFIER (Random Forest) ----------------------------------
print("\n" + "-" * 60)
print("MODEL 2 — Price Tier Classifier (Random Forest)")
print("-" * 60)

rf_clf = RandomForestClassifier(
    n_estimators=300, max_depth=8, min_samples_leaf=3,
    class_weight="balanced", random_state=42, n_jobs=-1
)
rf_clf.fit(X_train, y_tier_train)
y_pred_tier = rf_clf.predict(X_test)

acc = accuracy_score(y_tier_test, y_pred_tier)
print(f"  Accuracy : {acc:.4f}")
cv_acc = cross_val_score(rf_clf, X, np.array(y_tier), cv=5, scoring="accuracy")
print(f"  CV Acc   : {cv_acc.mean():.4f} ± {cv_acc.std():.4f}")

labels_order = ["Budget", "Mid-Range", "Premium", "Luxury"]
print("\n  Classification Report:")
report = classification_report(y_tier_test, y_pred_tier, labels=labels_order, output_dict=True)
report_str = classification_report(y_tier_test, y_pred_tier, labels=labels_order)
print(report_str)

metrics["tier_classifier"] = {
    "model": "RandomForestClassifier", "accuracy": round(acc, 4),
    "cv_acc_mean": round(cv_acc.mean(), 4), "cv_acc_std": round(cv_acc.std(), 4),
    "f1_weighted": round(report["weighted avg"]["f1-score"], 4),
}

# Plot 2: Confusion matrix + feature importance
fig, axes = plt.subplots(1, 2, figsize=(14, 5))
fig.patch.set_facecolor(PALETTE["bg"])

ax = axes[0]
cm = confusion_matrix(y_tier_test, y_pred_tier, labels=labels_order)
sns.heatmap(cm, annot=True, fmt="d", ax=ax, cmap="Blues",
            xticklabels=labels_order, yticklabels=labels_order,
            linewidths=0.5, linecolor="#eee")
ax.set_title(f"Model 2: Tier Classifier\nAccuracy = {acc:.4f}", fontsize=12, fontweight="bold")
ax.set_xlabel("Predicted Tier")
ax.set_ylabel("Actual Tier")

ax = axes[1]
feat_imp_tier = pd.Series(rf_clf.feature_importances_, index=["Listing Type","Region","City","Log Reviews"])
feat_imp_tier.sort_values().plot(kind="barh", ax=ax,
    color=[PALETTE["teal"],PALETTE["primary"],PALETTE["secondary"],PALETTE["accent"]])
ax.set_title("Feature Importance — Tier", fontsize=12, fontweight="bold")
ax.set_xlabel("Importance Score")

plt.tight_layout(pad=2)
plt.savefig(PLOTS / "ml_02_tier_classifier.png", dpi=150, bbox_inches="tight")
plt.close()
print("  Plot saved: plots/ml_02_tier_classifier.png")

# -- MODEL 3: DEMAND SCORE REGRESSION (Gradient Boosting) ---------------------
print("\n" + "-" * 60)
print("MODEL 3 — Demand Score Regressor (Gradient Boosting)")
print("-" * 60)

gbr_dem = GradientBoostingRegressor(
    n_estimators=200, max_depth=3, learning_rate=0.08,
    subsample=0.8, random_state=42
)
gbr_dem.fit(X_train, y_dem_train)
y_pred_dem = gbr_dem.predict(X_test)
y_pred_dem = np.clip(y_pred_dem, 0, 100)

mae_dem = mean_absolute_error(y_dem_test, y_pred_dem)
r2_dem  = r2_score(y_dem_test, y_pred_dem)
cv_r2_dem = cross_val_score(gbr_dem, X, np.array(y_demand), cv=5, scoring="r2")
print(f"  MAE  : {mae_dem:.4f} score points")
print(f"  R²   : {r2_dem:.4f}")
print(f"  CV R²: {cv_r2_dem.mean():.4f} ± {cv_r2_dem.std():.4f}")

metrics["demand_model"] = {
    "model": "GradientBoostingRegressor", "mae_score_pts": round(mae_dem, 4),
    "r2": round(r2_dem, 4), "cv_r2_mean": round(cv_r2_dem.mean(), 4),
}

# -- PLOTS 3: EDA Visuals -------------------------------------------------------

# Plot 3: Price distribution by listing type
fig, axes = plt.subplots(2, 2, figsize=(14, 10))
fig.patch.set_facecolor(PALETTE["bg"])
fig.suptitle("SA Accommodation Market Analysis — LekkeSlaap 2026\nEDA Visualisations",
             fontsize=14, fontweight="bold", y=1.01)

ax = axes[0][0]
top_types = df_model["listing_type"].value_counts().head(6).index
df_box = df_model[df_model["listing_type"].isin(top_types)]
order = df_box.groupby("listing_type")["price_zar"].median().sort_values(ascending=False).index
bp = ax.boxplot(
    [df_box[df_box["listing_type"]==t]["price_zar"].values for t in order],
    tick_labels=order, patch_artist=True, notch=False,
    medianprops=dict(color=PALETTE["accent"], lw=2),
    flierprops=dict(marker=".", alpha=0.3, markersize=3),
)
colors = [PALETTE["primary"], PALETTE["secondary"], PALETTE["teal"],
          PALETTE["warning"], PALETTE["accent"], PALETTE["purple"]]
for patch, col in zip(bp["boxes"], colors):
    patch.set_facecolor(col)
    patch.set_alpha(0.7)
ax.set_title("Nightly Price (ZAR) by Listing Type", fontsize=11, fontweight="bold")
ax.set_ylabel("Price (ZAR)")
plt.setp(ax.get_xticklabels(), rotation=25, ha="right", fontsize=8)

ax = axes[0][1]
tier_counts = df_model["price_tier"].value_counts().reindex(labels_order, fill_value=0)
bars = ax.bar(tier_counts.index, tier_counts.values,
              color=[TIER_COLORS.get(t, "#999") for t in tier_counts.index], alpha=0.85)
for bar, val in zip(bars, tier_counts.values):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 3,
            f"{val:,}\n({val/len(df_model)*100:.0f}%)", ha="center", va="bottom", fontsize=9)
ax.set_title("Price Tier Distribution", fontsize=11, fontweight="bold")
ax.set_ylabel("Number of Properties")

ax = axes[1][0]
# Top 12 regions by count
top_regions = df_model["region"].value_counts().head(12)
bars = ax.barh(top_regions.index[::-1], top_regions.values[::-1], color=PALETTE["primary"], alpha=0.8)
for bar, val in zip(bars, top_regions.values[::-1]):
    ax.text(bar.get_width() + 0.3, bar.get_y() + bar.get_height()/2,
            str(val), va="center", fontsize=8)
ax.set_title("Properties by Region (Top 12)", fontsize=11, fontweight="bold")
ax.set_xlabel("Count")

ax = axes[1][1]
# Price vs Review Count scatter
sc = ax.scatter(df_model["review_count"], df_model["price_zar"], alpha=0.25, s=20,
                c=[list(TIER_COLORS.values())[["Budget","Mid-Range","Premium","Luxury"].index(t)
                   if t in ["Budget","Mid-Range","Premium","Luxury"] else 0]
                   for t in df_model["price_tier"]],
                edgecolors="none")
ax.set_xlabel("Number of Reviews")
ax.set_ylabel("Nightly Price (ZAR)")
ax.set_title("Price vs Review Count", fontsize=11, fontweight="bold")
ax.set_xlim(0, df_model["review_count"].quantile(0.98))
ax.set_ylim(0, df_model["price_zar"].quantile(0.97))
patches = [mpatches.Patch(color=TIER_COLORS[t], label=t, alpha=0.8)
           for t in ["Budget","Mid-Range","Premium","Luxury"]]
ax.legend(handles=patches, fontsize=8, loc="upper right")

plt.tight_layout(pad=2.5)
plt.savefig(PLOTS / "eda_01_market_overview.png", dpi=150, bbox_inches="tight")
plt.close()
print("\n  Plot saved: plots/eda_01_market_overview.png")

# Plot 4: GA4 Web Analytics — sessions by traffic source + device
df_sess = pd.read_csv(DATA / "fact_web_sessions.csv")
df_evts = pd.read_csv(DATA / "fact_booking_events.csv")

fig, axes = plt.subplots(2, 2, figsize=(14, 10))
fig.patch.set_facecolor(PALETTE["bg"])
fig.suptitle("GA4 Web Analytics — LekkeSlaap Platform (Jan–Jun 2025)\nSimulated Data",
             fontsize=14, fontweight="bold", y=1.01)

ax = axes[0][0]
src_order = df_sess.groupby("traffic_source").size().sort_values(ascending=False)
bars = ax.bar(src_order.index, src_order.values,
              color=[PALETTE["primary"],PALETTE["teal"],PALETTE["secondary"],
                     PALETTE["accent"],PALETTE["purple"],PALETTE["warning"],PALETTE["danger"]][:len(src_order)],
              alpha=0.85)
for bar, val in zip(bars, src_order.values):
    ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()+50,
            f"{val:,}", ha="center", va="bottom", fontsize=9)
ax.set_title("Sessions by Traffic Source", fontsize=11, fontweight="bold")
ax.set_ylabel("Sessions")
plt.setp(ax.get_xticklabels(), rotation=20, ha="right")

ax = axes[0][1]
dev_counts = df_sess["device_category"].value_counts()
wedge_colors = [PALETTE["primary"], PALETTE["secondary"], PALETTE["accent"]]
wedges, texts, autotexts = ax.pie(dev_counts.values, labels=dev_counts.index,
    autopct="%1.1f%%", colors=wedge_colors, startangle=90,
    textprops={"fontsize":10}, pctdistance=0.75)
for at in autotexts:
    at.set_fontweight("bold")
ax.set_title("Sessions by Device", fontsize=11, fontweight="bold")

ax = axes[1][0]
# Funnel
funnel_steps = ["listing_view","search_nearby","contact_host","booking_initiated","booking_confirmed"]
funnel_counts = [df_evts[df_evts["event_name"]==e].shape[0] for e in funnel_steps]
funnel_labels = ["Listing View","Search Nearby","Contact Host","Booking Init","Confirmed"]
bars = ax.barh(funnel_labels[::-1], funnel_counts[::-1],
               color=[PALETTE["danger"],PALETTE["warning"],PALETTE["accent"],
                      PALETTE["secondary"],PALETTE["primary"]][::-1],
               alpha=0.85)
for bar, val in zip(bars, funnel_counts[::-1]):
    ax.text(bar.get_width()+50, bar.get_y()+bar.get_height()/2,
            f"{val:,}", va="center", fontsize=9)
ax.set_title("Booking Conversion Funnel", fontsize=11, fontweight="bold")
ax.set_xlabel("Events")

ax = axes[1][1]
# POPIA consent
prov_conv = df_evts[df_evts["event_name"]=="booking_confirmed"]["province"].value_counts().head(9)
bars = ax.barh(prov_conv.index[::-1], prov_conv.values[::-1], color=PALETTE["teal"], alpha=0.85)
for bar, val in zip(bars, prov_conv.values[::-1]):
    ax.text(bar.get_width()+2, bar.get_y()+bar.get_height()/2,
            str(val), va="center", fontsize=9)
ax.set_title("Confirmed Bookings by Province", fontsize=11, fontweight="bold")
ax.set_xlabel("Bookings")

plt.tight_layout(pad=2.5)
plt.savefig(PLOTS / "ga4_01_web_analytics.png", dpi=150, bbox_inches="tight")
plt.close()
print("  Plot saved: plots/ga4_01_web_analytics.png")

# Plot 5: ML model performance summary
fig, axes = plt.subplots(1, 3, figsize=(16, 5))
fig.patch.set_facecolor(PALETTE["bg"])
fig.suptitle("ML Model Performance Summary", fontsize=13, fontweight="bold")

# 5a: Price residuals
ax = axes[0]
residuals = y_pred_price - y_price_test
ax.hist(residuals, bins=40, color=PALETTE["primary"], alpha=0.8, edgecolor="white")
ax.axvline(0, color=PALETTE["accent"], lw=2, linestyle="--")
ax.set_title(f"Price Regression Residuals\nR² = {r2:.4f} | MAE = R{mae:.0f}", fontsize=10, fontweight="bold")
ax.set_xlabel("Predicted − Actual (ZAR)")
ax.set_ylabel("Frequency")

# 5b: Tier accuracy bar
ax = axes[1]
tier_acc = {t: accuracy_score(
    [y for y, lbl in zip(y_tier_test, y_tier_test) if lbl == t],
    [p for p, lbl in zip(y_pred_tier, y_tier_test) if lbl == t]
) for t in labels_order if t in y_tier_test}
bars_acc = ax.bar(tier_acc.keys(), tier_acc.values(),
                  color=[TIER_COLORS[t] for t in tier_acc], alpha=0.85)
for bar, val in zip(bars_acc, tier_acc.values()):
    ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()+0.01,
            f"{val:.2f}", ha="center", va="bottom", fontsize=10, fontweight="bold")
ax.set_ylim(0, 1.1)
ax.set_title(f"Tier Classifier Accuracy by Class\nOverall = {acc:.4f}", fontsize=10, fontweight="bold")
ax.set_ylabel("Accuracy")

# 5c: Demand score actual vs predicted
ax = axes[2]
ax.scatter(y_dem_test, y_pred_dem, alpha=0.3, color=PALETTE["secondary"], s=20, edgecolors="none")
lim_d = max(y_dem_test.max(), y_pred_dem.max()) * 1.05
ax.plot([0, lim_d], [0, lim_d], "--", color=PALETTE["accent"], lw=1.5)
ax.set_title(f"Demand Score Regression\nR² = {r2_dem:.4f}", fontsize=10, fontweight="bold")
ax.set_xlabel("Actual Demand Score")
ax.set_ylabel("Predicted Demand Score")

plt.tight_layout(pad=2)
plt.savefig(PLOTS / "ml_03_model_summary.png", dpi=150, bbox_inches="tight")
plt.close()
print("  Plot saved: plots/ml_03_model_summary.png")

# -- SAVE METRICS --------------------------------------------------------------
with open(ML / "model_metrics.json", "w") as f:
    json.dump(metrics, f, indent=2)
print("\n  Metrics saved: ml/model_metrics.json")

# -- PREDICTIONS ON FULL DATASET ------------------------------------------------
df_preds = df.dropna(subset=["price_zar"]).copy()
try:
    df_preds["listing_type_enc"] = le_type.transform(
        df_preds["listing_type"].fillna("Unknown").apply(
            lambda x: x if x in le_type.classes_ else le_type.classes_[0]))
    df_preds["region_enc"] = le_region.transform(
        df_preds["region"].fillna("Unknown").apply(
            lambda x: x if x in le_region.classes_ else le_region.classes_[0]))
    df_preds["city_enc"] = le_city.transform(
        df_preds["city"].fillna("Unknown").apply(
            lambda x: x if x in le_city.classes_ else le_city.classes_[0]))
    df_preds["log_reviews"] = np.log1p(df_preds["review_count"].fillna(0))
    X_all = df_preds[["listing_type_enc","region_enc","city_enc","log_reviews"]].values

    df_preds["predicted_price_zar"] = gbr.predict(X_all).round(0)
    df_preds["predicted_tier"]      = rf_clf.predict(X_all)
    df_preds["predicted_demand"]    = np.clip(gbr_dem.predict(X_all), 0, 100).round(2)
    df_preds["price_delta_zar"]     = (df_preds["predicted_price_zar"] - df_preds["price_zar"]).round(0)

    out_cols = ["property_id","property_name","listing_type","region","price_zar",
                "predicted_price_zar","price_delta_zar","price_tier","predicted_tier",
                "demand_score","predicted_demand","review_count"]
    df_preds[out_cols].to_csv(ML / "ml_predictions.csv", index=False)
    print(f"  Predictions saved: ml/ml_predictions.csv  ({len(df_preds):,} rows)")
except Exception as e:
    print(f"  Prediction export skipped: {e}")

print("\n✅ ML models complete.")
print(f"\n  Model Summary:")
print(f"    Price Regression R²   : {r2:.4f}")
print(f"    Tier Classifier Acc   : {acc:.4f}")
print(f"    Demand Regression R²  : {r2_dem:.4f}")


