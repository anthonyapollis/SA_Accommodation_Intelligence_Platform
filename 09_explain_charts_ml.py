"""
09_explain_charts_ml.py
Adds inline explanations to charts and ML model cards so a cold reader
knows exactly what they are looking at, how to read it, and what it means.
Targets: dashboard.html, ml-features.html, mobile-attribution.html, seo-audit.html
"""
from pathlib import Path
import re

NET = Path(__file__).parent / "netlify_site"

def save(p, html):
    p.write_text(html, encoding="utf-8")
    print(f"  Updated: {p.name}")

# ─────────────────────────────────────────────────────────────────────────────
# Helper: wrap a section heading with an inline explanation blurb
# ─────────────────────────────────────────────────────────────────────────────
CHART_NOTE_CSS = """
.chart-explain{background:rgba(255,255,255,0.03);border:1px solid #30363d;
               border-radius:6px;padding:0.6rem 0.85rem;margin-bottom:0.75rem;
               font-size:0.78rem;color:#8b949e;line-height:1.55}
.chart-explain strong{color:#e6edf3}
.chart-explain .how{display:inline-block;background:rgba(255,108,0,0.12);
                    color:#FF6C00;border-radius:3px;padding:0.1rem 0.35rem;
                    font-size:0.68rem;font-weight:700;margin-right:0.35rem}
"""

# ─────────────────────────────────────────────────────────────────────────────
# 1. dashboard.html  — explain every chart section
# ─────────────────────────────────────────────────────────────────────────────
p = NET / "dashboard.html"
html = p.read_text(encoding="utf-8")
html = html.replace("</style>", CHART_NOTE_CSS + "\n</style>", 1)

DASH_EXPLANATIONS = {
    "Price Distribution": (
        "This <strong>histogram</strong> shows how nightly prices are spread across all 1,011 listings. "
        "The x-axis is price in ZAR (R), y-axis is the number of listings at that price. "
        "<span class='how'>How to read it</span>"
        "A right-skewed distribution (long tail to the right) means most listings are affordable "
        "but a small number of luxury properties pull the average up. "
        "The median (R1,380) is a better 'typical price' than the mean (R2,002) because of these outliers."
    ),
    "Listings by Type": (
        "This <strong>bar chart</strong> counts how many listings exist per accommodation category "
        "(Self-catering, Guesthouse, Lodge, etc.). "
        "<span class='how'>How to read it</span>"
        "Taller bars = more supply in that category. "
        "A dominant category with high demand signals a mature, competitive segment. "
        "A small category with high demand signals a <strong>supply gap and opportunity</strong>."
    ),
    "Demand by Region": (
        "This <strong>horizontal bar chart</strong> ranks the top regions by average Demand Score (0–100). "
        "Demand Score = booking-event frequency (40%) + review count (30%) + promo activity (30%). "
        "<span class='how'>How to read it</span>"
        "Regions near the top have the most engaged, booking-intent visitors on the platform. "
        "A high demand + low listing count = underserved market. "
        "A high demand + high listing count = competitive, well-served market."
    ),
    "GA4 Traffic Sources": (
        "This <strong>doughnut/pie chart</strong> shows the proportion of web sessions driven by each "
        "acquisition channel — Organic Search, Direct, Social, Paid, Email, Referral. "
        "<span class='how'>How to read it</span>"
        "A large Organic slice means strong SEO — visitors find the site without paid spend. "
        "A large Direct slice means strong brand awareness. "
        "Heavy reliance on Paid without Organic is a risk: if ads stop, traffic disappears."
    ),
    "ML Model Performance": (
        "This <strong>grouped bar chart</strong> compares model performance metrics side by side. "
        "<span class='how'>How to read it</span>"
        "<strong>R²</strong> (regression): 1.0 = perfect, 0 = no better than guessing the mean. "
        "<strong>F1</strong> (classification): 1.0 = perfect recall and precision. "
        "<strong>AUC</strong> (binary): 0.5 = random chance, 1.0 = perfect ranking. "
        "All models trained on synthetic data — treat metrics as directional, not production benchmarks."
    ),
    "Price vs Demand": (
        "This <strong>scatter plot</strong> plots each region as a dot — x-axis = average nightly price, "
        "y-axis = average demand score. Colour = ML cluster. "
        "<span class='how'>How to read it</span>"
        "Dots in the <strong>top-left</strong> (low price, high demand) are the best-value, highest-demand regions. "
        "Dots in the <strong>bottom-right</strong> (high price, low demand) are expensive and under-performing. "
        "The downward trend line (global r = -0.279) confirms cheaper regions generally get more bookings."
    ),
    "Seasonal Demand": (
        "This <strong>line or area chart</strong> shows how booking demand varies by month across the year. "
        "<span class='how'>How to read it</span>"
        "Peaks align with South African school holidays and public holidays. "
        "Summer (Dec–Feb) peak = beach and Garden Route. Winter (Jun–Aug) secondary peak = Kruger game viewing season. "
        "Troughs = shoulder seasons where <strong>discounts attract price-sensitive travellers</strong>."
    ),
}

for heading, note in DASH_EXPLANATIONS.items():
    # Find the section heading and inject note after it
    pattern = f'<h2>{heading}</h2>'
    replacement = (f'<h2>{heading}</h2>\n'
                   f'<div class="chart-explain">{note}</div>')
    if pattern in html:
        html = html.replace(pattern, replacement, 1)

save(p, html)

# ─────────────────────────────────────────────────────────────────────────────
# 2. ml-features.html  — explain each model card in detail, add cluster explainer
# ─────────────────────────────────────────────────────────────────────────────
p = NET / "ml-features.html"
html = p.read_text(encoding="utf-8")
html = html.replace("</style>", CHART_NOTE_CSS + "\n</style>", 1)

# Add a cluster explainer card before the feature table
CLUSTER_EXPLAINER = """<div class="chart-explain" style="margin-top:0.5rem">
  <strong>How to read the K-Means Cluster labels:</strong><br>
  Clusters were found by grouping all 114 regions using K-Means (k=4) on four features:
  average nightly price, average demand score, average review count, and listing count.
  The algorithm finds natural groupings — these labels are descriptive names assigned after
  inspecting the centroid values of each group.<br><br>
  <strong style="color:#f44336">High-Demand Hotspot</strong> — 7 regions. Cheapest avg price (R1,297) but highest demand (24.04).
  These are volume-driven, budget-accessible destinations where supply cannot keep up with demand.
  Cape Town suburbs, popular Garden Route towns.<br>
  <strong style="color:#ff9800">Established Premium</strong> — 19 regions. Mid-price (R1,651), strong reviews, steady demand.
  These markets are healthy and consistent year-round. Safe investment destinations.<br>
  <strong style="color:#2196f3">Value Volume Leader</strong> — 83 regions (the majority). Higher avg price (R1,851) but mid demand.
  Wide variety; many mid-market properties. Price sensitivity is real in this cluster.<br>
  <strong style="color:#4caf50">Emerging Gem</strong> — 5 ultra-premium regions (avg R9,754). Very low listing count, very low demand.
  These are niche luxury destinations. High barrier to entry but low competition.
</div>"""

if "How to read the K-Means Cluster labels" not in html:
    old = '<h2>Feature Table (sample 50, sorted by demand)</h2>'
    html = html.replace(old, '<h2>Feature Table (sample 50, sorted by demand)</h2>\n' + CLUSTER_EXPLAINER, 1)

# Add column explanations row to the feature table header
old_thead = ('<thead><tr>\n        <th>Property</th><th>Region</th><th>Type</th>\n'
             '        <th>Price (R)</th><th>Reviews</th><th>Demand</th>\n'
             '        <th>Coastal</th><th>Game</th><th>Wine</th>\n'
             '        <th>Quality</th><th>Cluster</th>\n      </tr></thead>')
new_thead = ('<thead><tr>\n'
             '        <th>Property</th>\n'
             '        <th>Region</th>\n'
             '        <th>Type<span class="col-hint">Accommodation category from LekkeSlaap listing</span></th>\n'
             '        <th>Price (R)<span class="col-hint">Nightly rate in South African Rand (ZAR) at scrape date</span></th>\n'
             '        <th>Reviews<span class="col-hint">Total cumulative guest reviews</span></th>\n'
             '        <th>Demand<span class="col-hint">Composite 0-100. Higher = more in-demand than average</span></th>\n'
             '        <th>Coastal<span class="col-hint">Within 50km of coastline</span></th>\n'
             '        <th>Game<span class="col-hint">Game reserve / safari listing or region</span></th>\n'
             '        <th>Wine<span class="col-hint">Cape Winelands region</span></th>\n'
             '        <th>Quality<span class="col-hint">Data completeness 0-1. 1.0 = all key fields present</span></th>\n'
             '        <th>Cluster<span class="col-hint">K-Means market segment. See explainer above.</span></th>\n'
             '      </tr></thead>')
if old_thead in html:
    html = html.replace(old_thead, new_thead, 1)

save(p, html)

# ─────────────────────────────────────────────────────────────────────────────
# 3. mobile-attribution.html  — explain ROAS, CPI, cohort retention
# ─────────────────────────────────────────────────────────────────────────────
p = NET / "mobile-attribution.html"
html = p.read_text(encoding="utf-8")
html = html.replace("</style>", CHART_NOTE_CSS + "\n</style>", 1)

# Explain channel performance table
old = '<h2>Channel Performance</h2>'
new = ('<h2>Channel Performance</h2>\n'
       '<div class="chart-explain">'
       'This table shows <strong>how each acquisition channel performs from install to booking</strong>. '
       '<span class="how">Key metrics</span>'
       '<strong>CPI (Cost Per Install)</strong> = total spend ÷ installs — lower is better. '
       '<strong>Conv %</strong> = % of installs that completed a booking within 30 days — higher is better. '
       '<strong>LTV</strong> = total booking revenue attributable to installs from this channel. '
       '<strong>ROAS</strong> = LTV ÷ cost — ROAS of 3× means R3 earned per R1 spent. '
       'ROAS below 1× = losing money. Organic shows R0 cost because it is unpaid — '
       'its "cost" is brand investment and SEO effort, not direct ad spend.'
       '</div>')
html = html.replace(old, new, 1)

# Explain cohort retention
old = '<h2>Cohort Retention by Channel</h2>'
new = ('<h2>Cohort Retention by Channel</h2>\n'
       '<div class="chart-explain">'
       '<strong>Cohort retention</strong> measures what % of users who installed the app are still active '
       'after Day 1, Day 7, and Day 30. '
       '<span class="how">How to read it</span>'
       'Day-1 retention = % who returned the day after installing. Day-30 = loyal users. '
       'A channel with high installs but low Day-30 retention is acquiring <strong>low-quality users</strong> '
       'who try the app once and leave — high CPI for little long-term value. '
       'Organic users typically have the highest retention because they sought the app out intentionally.'
       '</div>')
html = html.replace(old, new, 1)

save(p, html)

# ─────────────────────────────────────────────────────────────────────────────
# 4. seo-audit.html  — explain the score column and category tabs
# ─────────────────────────────────────────────────────────────────────────────
p = NET / "seo-audit.html"
html = p.read_text(encoding="utf-8")
html = html.replace("</style>", CHART_NOTE_CSS + "\n</style>", 1)

old = '<h2>Full Audit by Category</h2>'
new = ('<h2>Full Audit by Category</h2>\n'
       '<div class="chart-explain">'
       'Each row is a single SEO or AEO check. '
       '<span class="how">How to read scores</span>'
       '<strong>Score 80–100</strong> (green) = passing well. '
       '<strong>Score 50–79</strong> (amber) = partial issue, improve when possible. '
       '<strong>Score 0–49</strong> (red) = failing — fix before publishing to production. '
       'Click a <strong>category tab</strong> to filter by: Core Web Vitals (page speed), '
       'Technical SEO (crawlability), On-Page SEO (content structure), '
       'AEO / AI Mode (answer engine readiness for ChatGPT/Perplexity), '
       'Content Quality (E-E-A-T), Core Update compliance, and Performance. '
       '<strong>Priority column</strong>: Critical = fix immediately; High = fix this sprint; '
       'Medium = next iteration; Low = nice to have.'
       '</div>')
html = html.replace(old, new, 1)

save(p, html)

# ─────────────────────────────────────────────────────────────────────────────
# 5. market-opportunity.html  — explain the opportunity bar chart
# ─────────────────────────────────────────────────────────────────────────────
p = NET / "market-opportunity.html"
html = p.read_text(encoding="utf-8")
html = html.replace("</style>", CHART_NOTE_CSS + "\n</style>", 1)

old = '<h2>Top 30 Regions by Opportunity Score</h2>'
new = ('<h2>Top 30 Regions by Opportunity Score</h2>\n'
       '<div class="chart-explain">'
       'The <strong>mini bar under each score</strong> visualises the score relative to the top-ranked region. '
       '<span class="how">How to use this table</span>'
       'Regions with a <strong>high score + few listings</strong> are the most interesting: '
       'demand exists but supply has not caught up yet — ideal for a new property or investment. '
       'Use the <strong>filters</strong> to narrow by geography type (Coastal, Game, Wine). '
       'The <strong>Tags column</strong> shows geographic flags — a blue Y means coastal, green Y means game reserve, orange Y means wine region. '
       'Cross-reference the top regions with the <strong>Seasonality page</strong> to understand '
       'which season drives that demand, then time your listing or campaign accordingly.'
       '</div>')
html = html.replace(old, new, 1)

save(p, html)

# ─────────────────────────────────────────────────────────────────────────────
# 6. seasonality.html  — explain the province table
# ─────────────────────────────────────────────────────────────────────────────
p = NET / "seasonality.html"
html = p.read_text(encoding="utf-8")
html = html.replace("</style>", CHART_NOTE_CSS + "\n</style>", 1)

old = '<h2>Province Seasonal Breakdown</h2>'
new = ('<h2>Province Seasonal Breakdown</h2>\n'
       '<div class="chart-explain">'
       'Each row shows what <strong>% of that province\'s annual bookings</strong> fall in each season. '
       'The four columns sum to 100% per row. '
       '<span class="how">How to read it</span>'
       'A province with 45% Summer and 15% Winter is <strong>highly seasonal</strong> — pricing and '
       'stock management must account for a very quiet winter period. '
       'A province with relatively even splits (28/26/24/22) is <strong>year-round</strong> — '
       'more stable revenue but less premium pricing power in peak season. '
       'The <strong>Top Season</strong> column highlights where each province\'s single biggest '
       'demand window falls — use this to prioritise campaign budgets.'
       '</div>')
html = html.replace(old, new, 1)

save(p, html)

# ─────────────────────────────────────────────────────────────────────────────
# 7. data-model.html  — add ERD relationship explanation
# ─────────────────────────────────────────────────────────────────────────────
p = NET / "data-model.html"
html = p.read_text(encoding="utf-8")
html = html.replace("</style>", CHART_NOTE_CSS + "\n</style>", 1)

old = '<h2>SCHEMA OVERVIEW</h2>'
new = ('<h2>SCHEMA OVERVIEW</h2>\n'
       '<div class="chart-explain" style="margin-bottom:0.75rem">'
       '<strong>How to read this diagram:</strong> Data flows left to right through four layers. '
       '<strong>RAW</strong> = exactly as scraped from LekkeSlaap and GA4 — messy, unvalidated. '
       '<strong>DIMENSIONS</strong> = lookup tables describing <em>who, what, where, when</em> '
       '(property details, region geography, calendar dates, device types). '
       '<strong>FACTS</strong> = event tables recording <em>what happened</em> '
       '(a listing was scraped, a booking event fired, a web session occurred). '
       'Facts link to dimensions via Foreign Keys (FK). '
       '<strong>MART / ML</strong> = pre-aggregated tables and ML outputs ready for dashboards — '
       'these are what the charts on this platform read from. '
       'Never query raw tables for reporting; always use mart_ or vw_ views.'
       '</div>')
html = html.replace(old, new, 1)

save(p, html)

print("\nDone. Chart + ML explanations added to:")
for name in ["dashboard.html","ml-features.html","mobile-attribution.html",
             "seo-audit.html","market-opportunity.html","seasonality.html","data-model.html"]:
    print(f"  {name}")
