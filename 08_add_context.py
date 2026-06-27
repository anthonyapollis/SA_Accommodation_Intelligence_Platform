"""
08_add_context.py
Injects a "What · Why · So What" context banner into every Netlify page,
and adds inline explanatory footnotes to key metrics and table columns.
A reader who opens any page cold should immediately understand:
  - WHAT the data is
  - WHY it was collected / calculated
  - SO WHAT: what to do with the insight
"""
from pathlib import Path
import re

NET = Path(__file__).parent / "netlify_site"

# ── Reusable context-card CSS (injected once into each page's <style>) ────────
CONTEXT_CSS = """
/* ── Context cards ──────────────────────────────────────────── */
.ctx-card{background:rgba(255,108,0,0.05);border-left:4px solid #FF6C00;
          border-radius:0 8px 8px 0;padding:0.85rem 1.1rem;margin-bottom:1.1rem;
          font-size:0.82rem;line-height:1.6;color:#c9d1d9}
.ctx-card .ctx-row{display:flex;flex-wrap:wrap;gap:1.5rem;margin-top:0.55rem}
.ctx-item{flex:1;min-width:160px}
.ctx-label{font-size:0.68rem;font-weight:700;text-transform:uppercase;
           letter-spacing:0.08em;color:#FF6C00;margin-bottom:0.2rem}
.ctx-text{font-size:0.8rem;color:#8b949e}
.ctx-text strong{color:#e6edf3}
/* Column hint tooltips */
.col-hint{font-size:0.65rem;color:#8b949e;display:block;margin-top:1px;font-weight:400}
"""

def inject_css(html: str, extra: str) -> str:
    """Insert extra CSS just before the closing </style> of the first style block."""
    return html.replace("</style>", extra + "\n</style>", 1)

def inject_after_header(html: str, card_html: str) -> str:
    """Insert card_html immediately after the .page-header closing div."""
    # Try to find </div> after class="page-header"
    m = re.search(r'(class=["\']page-header["\'][^>]*>.*?</div>)', html, re.DOTALL)
    if m:
        pos = m.end()
        return html[:pos] + "\n" + card_html + html[pos:]
    return html

def inject_before_first_table(html: str, note_html: str) -> str:
    """Insert note_html before the first <table> inside .content."""
    m = re.search(r'(<table)', html)
    if m:
        return html[:m.start()] + note_html + "\n" + html[m.start():]
    return html

def save(path: Path, html: str):
    path.write_text(html, encoding="utf-8")
    print(f"  Updated: {path.name}")

# ── 1. data-model.html ────────────────────────────────────────────────────────
p = NET / "data-model.html"
html = p.read_text(encoding="utf-8")
html = inject_css(html, CONTEXT_CSS)
card = """<div class="content">
<div class="ctx-card">
  <strong style="color:#FF6C00">What you are looking at</strong>
  <div class="ctx-row">
    <div class="ctx-item">
      <div class="ctx-label">What</div>
      <div class="ctx-text">The <strong>warehouse schema</strong> for the LekkeSlaap Intelligence Platform —
        25+ tables organised in a BigQuery star schema (raw layer &rarr; dimensions &rarr; facts &rarr; ML mart).
        Dataset: <code>africa-south1.accommodation_intelligence</code>.</div>
    </div>
    <div class="ctx-item">
      <div class="ctx-label">Why</div>
      <div class="ctx-text">A star schema separates <strong>what happened</strong> (fact tables: bookings, sessions, listings)
        from <strong>who/where/when</strong> (dimension tables: property, region, date, device).
        This makes analytics queries fast and consistent — every dashboard, ML model, and report
        reads from the same single source of truth.</div>
    </div>
    <div class="ctx-item">
      <div class="ctx-label">So What</div>
      <div class="ctx-text">Click any table button below to explore its fields. Use this schema to understand
        <strong>where each number on this platform comes from</strong>. If a KPI looks unexpected,
        trace it back here to see the calculation logic.</div>
    </div>
  </div>
</div>"""
html = html.replace('<div class="content">\n\n  <div class="card">\n    <h2>Schema Overview</h2>', card + '\n\n  <div class="card">\n    <h2>Schema Overview</h2>', 1)
save(p, html)

# ── 2. seasonality.html ───────────────────────────────────────────────────────
p = NET / "seasonality.html"
html = p.read_text(encoding="utf-8")
html = inject_css(html, CONTEXT_CSS)
card = """<div class="content">
<div class="ctx-card">
  <strong style="color:#FF6C00">What you are looking at</strong>
  <div class="ctx-row">
    <div class="ctx-item">
      <div class="ctx-label">What</div>
      <div class="ctx-text">Booking demand distributed across South Africa's <strong>four meteorological seasons</strong>
        (Summer Dec–Feb, Autumn Mar–May, Winter Jun–Aug, Spring Sep–Nov) — derived from
        <strong>28,628 synthetic GA4 booking events</strong> across 9 provinces.</div>
    </div>
    <div class="ctx-item">
      <div class="ctx-label">Why</div>
      <div class="ctx-text">Accommodation demand in SA is highly seasonal — Cape Town peaks in Summer while Kruger
        peaks in Winter (dry season, better game viewing). Knowing the seasonal pattern per province helps
        <strong>set dynamic pricing</strong>, time campaigns correctly, and <strong>avoid stock-outs
        during peak periods</strong>.</div>
    </div>
    <div class="ctx-item">
      <div class="ctx-label">So What</div>
      <div class="ctx-text">Check which season is dominant for your target province. Demand multipliers
        (e.g. 1.62× at Christmas) tell you how much above average demand rises — use these to
        <strong>set premium pricing</strong> and justify higher ad spend in the lead-up window.</div>
    </div>
  </div>
</div>"""
html = html.replace('<div class="content">\n  <div class="card">\n    <h2>SA-Wide Seasonal Demand</h2>', card + '\n  <div class="card">\n    <h2>SA-Wide Seasonal Demand</h2>', 1)
save(p, html)

# ── 3. ml-features.html ───────────────────────────────────────────────────────
p = NET / "ml-features.html"
html = p.read_text(encoding="utf-8")
html = inject_css(html, CONTEXT_CSS)
card = """<div class="content">
<div class="ctx-card">
  <strong style="color:#FF6C00">What you are looking at</strong>
  <div class="ctx-row">
    <div class="ctx-item">
      <div class="ctx-label">What</div>
      <div class="ctx-text">The <strong>engineered feature set</strong> used to train all 5 ML models —
        one row per property (1,011 total). Features include geographic flags (coastal, urban, game reserve, wine region),
        a data-quality score, the SA season at scrape date, and the K-Means cluster assignment.</div>
    </div>
    <div class="ctx-item">
      <div class="ctx-label">Why</div>
      <div class="ctx-text">Raw price and review counts alone are weak predictors. Adding <strong>location context</strong>
        (coastal = premium uplift), <strong>property type signals</strong> (game lodge = luxury segment),
        and <strong>seasonal timing</strong> significantly improves model accuracy.
        Feature engineering is where most ML value is created.</div>
    </div>
    <div class="ctx-item">
      <div class="ctx-label">So What</div>
      <div class="ctx-text">The model cards at the top show how well each model performs.
        R² = 0.82 on demand prediction means the model explains <strong>82% of demand variance</strong>
        across properties. The feature table shows which cluster each property belongs to —
        use cluster labels to quickly segment the market.</div>
    </div>
  </div>
</div>"""
html = html.replace('<div class="content">\n  <div class="model-cards">', card + '\n  <div class="model-cards">', 1)
save(p, html)

# ── 4. market-opportunity.html ────────────────────────────────────────────────
p = NET / "market-opportunity.html"
html = p.read_text(encoding="utf-8")
html = inject_css(html, CONTEXT_CSS)
card = """<div class="content">
<div class="ctx-card">
  <strong style="color:#FF6C00">What you are looking at</strong>
  <div class="ctx-row">
    <div class="ctx-item">
      <div class="ctx-label">What</div>
      <div class="ctx-text">A composite <strong>Opportunity Score (0–100)</strong> for each of the 114 SA regions,
        calculated from demand score, price accessibility, and review volume.
        Higher score = region with strong demand, accessible pricing, and proven guest satisfaction.</div>
    </div>
    <div class="ctx-item">
      <div class="ctx-label">Why</div>
      <div class="ctx-text">Not all high-demand regions are good investment opportunities — some are already
        saturated with premium listings. This score surfaces <strong>underserved regions</strong> where
        demand is high but supply is limited or prices are still accessible,
        meaning there is room to enter the market profitably.</div>
    </div>
    <div class="ctx-item">
      <div class="ctx-label">So What</div>
      <div class="ctx-text">Sort by Opportunity Score and filter by Coastal / Game / Wine to find the
        <strong>highest-return niches</strong> for a new property listing. Regions scoring above 60 with
        fewer than 10 listings are the strongest supply gaps. Cross-reference with the Seasonality page
        to time any launch for peak demand.</div>
    </div>
  </div>
</div>"""
html = html.replace('<div class="content">\n  <div class="card">\n    <h2>Opportunity Score Formula</h2>', card + '\n  <div class="card">\n    <h2>Opportunity Score Formula</h2>', 1)
save(p, html)

# ── 5. seo-pages.html ────────────────────────────────────────────────────────
p = NET / "seo-pages.html"
html = p.read_text(encoding="utf-8")
html = inject_css(html, CONTEXT_CSS)
card = """<div class="content">
<div class="ctx-card">
  <strong style="color:#FF6C00">What you are looking at</strong>
  <div class="ctx-row">
    <div class="ctx-item">
      <div class="ctx-label">What</div>
      <div class="ctx-text"><strong>20 planned SEO landing pages</strong> mapped to high-intent search queries —
        covering region guides, accommodation types, seasonal demand pages, and AEO
        (Answer Engine Optimization) pages targeting ChatGPT and Google AI Overviews.</div>
    </div>
    <div class="ctx-item">
      <div class="ctx-label">Why</div>
      <div class="ctx-text">After Google's May 2026 Core Update, AI Overviews now reduce organic CTR by an average of 34.5%.
        Ranking for <strong>informational queries</strong> requires structured, authoritative content —
        not just keywords. Each page here is mapped to a specific user intent (find, compare, plan, book)
        and search volume to prioritise build order.</div>
    </div>
    <div class="ctx-item">
      <div class="ctx-label">So What</div>
      <div class="ctx-text">Build <strong>Low difficulty pages first</strong> (quickest ranking wins),
        then move to Medium once domain authority builds. AEO pages (type = aeo) should include
        FAQ JSON-LD schema to appear in Google AI Overviews and ChatGPT citations.
        Est. monthly searches shown are keyword-level estimates — actual traffic depends on ranking position.</div>
    </div>
  </div>
</div>"""
html = html.replace('<div class="content">\n  <div class="card">\n    <h2>Overview</h2>', card + '\n  <div class="card">\n    <h2>Overview</h2>', 1)
save(p, html)

# ── 6. site-audit.html ────────────────────────────────────────────────────────
p = NET / "site-audit.html"
html = p.read_text(encoding="utf-8")
html = inject_css(html, CONTEXT_CSS)
card = """<div class="content">
<div class="ctx-card">
  <strong style="color:#FF6C00">What you are looking at</strong>
  <div class="ctx-row">
    <div class="ctx-item">
      <div class="ctx-label">What</div>
      <div class="ctx-text">A technical inventory of all <strong>13 pages</strong> in this Netlify deployment —
        tracking SEO health, mobile responsiveness, nav inclusion, and Lighthouse performance scores.
        New pages added in the latest build are flagged.</div>
    </div>
    <div class="ctx-item">
      <div class="ctx-label">Why</div>
      <div class="ctx-text">Google indexes the mobile version of pages first (mobile-first indexing).
        Pages missing from the nav bar receive no internal link equity — they are effectively invisible to crawlers.
        This audit ensures <strong>every page is connected, optimised, and discoverable</strong>.</div>
    </div>
    <div class="ctx-item">
      <div class="ctx-label">So What</div>
      <div class="ctx-text">Resolve items in the <strong>Action Items</strong> section below in priority order.
        Adding H1 tags and meta descriptions are 5-minute fixes with meaningful SEO impact.
        Check the SEO Audit page for a deeper 28-point technical analysis including AEO recommendations.</div>
    </div>
  </div>
</div>"""
html = html.replace('<div class="content">\n  <div class="card">\n    <h2>Audit Summary</h2>', card + '\n  <div class="card">\n    <h2>Audit Summary</h2>', 1)
save(p, html)

# ── 7. mobile-attribution.html ───────────────────────────────────────────────
p = NET / "mobile-attribution.html"
html = p.read_text(encoding="utf-8")
html = inject_css(html, CONTEXT_CSS)
# Find the data note div and add context card after it
old = 'class="content">\n\n  <div style="background:rgba(255,108,0,0.06)'
new = ('class="content">\n'
       '<div class="ctx-card">\n'
       '  <strong style="color:#FF6C00">What you are looking at</strong>\n'
       '  <div class="ctx-row">\n'
       '    <div class="ctx-item">\n'
       '      <div class="ctx-label">What</div>\n'
       '      <div class="ctx-text">Mobile app attribution data from <strong>AppsFlyer</strong> — '
       '5,000 synthetic installs across 6 acquisition channels (Meta Ads, Google UAC, TikTok, Organic, Email, Direct). '
       'Shows where app installs come from, which channels convert to bookings, '
       'and how much revenue each channel generates (LTV, ROAS).</div>\n'
       '    </div>\n'
       '    <div class="ctx-item">\n'
       '      <div class="ctx-label">Why</div>\n'
       '      <div class="ctx-text">LekkeSlaap is primarily a <strong>mobile app</strong> — most bookings happen on iOS or Android. '
       'AppsFlyer tracks which paid channel (Meta, Google) or organic source drove each install, '
       'then attributes downstream bookings back to that source. '
       'Without this, you cannot calculate true <strong>return on ad spend (ROAS)</strong> per channel.</div>\n'
       '    </div>\n'
       '    <div class="ctx-item">\n'
       '      <div class="ctx-label">So What</div>\n'
       '      <div class="ctx-text">Channels with ROAS &gt; 3× are profitable — <strong>increase budget there</strong>. '
       'Channels below 1× are losing money — pause or restructure. '
       'Day-30 retention shows which channel acquires <em>loyal</em> users vs one-time installers. '
       'Organic installs cost nothing but have the highest retention — investing in ASO and brand '
       'pays long-term dividends.</div>\n'
       '    </div>\n'
       '  </div>\n'
       '</div>\n\n'
       '  <div style="background:rgba(255,108,0,0.06)')
html = html.replace(old, new, 1)
save(p, html)

# ── 8. seo-audit.html ────────────────────────────────────────────────────────
p = NET / "seo-audit.html"
html = p.read_text(encoding="utf-8")
html = inject_css(html, CONTEXT_CSS)
old = 'class="content">\n\n  <div style="background:rgba(255,108,0,0.06)'
new = ('class="content">\n'
       '<div class="ctx-card">\n'
       '  <strong style="color:#FF6C00">What you are looking at</strong>\n'
       '  <div class="ctx-row">\n'
       '    <div class="ctx-item">\n'
       '      <div class="ctx-label">What</div>\n'
       '      <div class="ctx-text">A <strong>28-point technical SEO audit</strong> of this platform, '
       'scored against Google\'s March and May 2026 Core Updates, the June 2026 Spam Update, '
       'and Answer Engine Optimization (AEO) requirements for ChatGPT, Perplexity, and Google AI Mode.</div>\n'
       '    </div>\n'
       '    <div class="ctx-item">\n'
       '      <div class="ctx-label">Why</div>\n'
       '      <div class="ctx-text">Traditional SEO is no longer enough. Google AI Mode has <strong>1 billion monthly users</strong> '
       'and AI Overviews reduce clicks on top organic results by an average of 34.5%. '
       'Content must now be structured to answer questions <em>directly</em> — for Google, '
       'ChatGPT, Perplexity, and Bing Copilot simultaneously. '
       'Missing schema markup means your content is invisible to AI answer engines.</div>\n'
       '    </div>\n'
       '    <div class="ctx-item">\n'
       '      <div class="ctx-label">So What</div>\n'
       '      <div class="ctx-text">Work through <strong>Critical issues first</strong> (red badges) — '
       'sitemap.xml, robots.txt, and FAQ schema can each be added in under an hour and have '
       'outsized impact on crawlability and AI citations. '
       'Then address High priority warnings. The Quick Wins table below is your action checklist '
       'in priority order.</div>\n'
       '    </div>\n'
       '  </div>\n'
       '</div>\n\n'
       '  <div style="background:rgba(255,108,0,0.06)')
html = html.replace(old, new, 1)
save(p, html)

# ── 9. data-model.html — add field-level column explanations ─────────────────
# Already done via table explorer JS — add a note above the table explorer card
p = NET / "data-model.html"
html = p.read_text(encoding="utf-8")
old = '<h2>TABLE DETAILS — CLICK TO EXPAND</h2>'
new = ('<h2>TABLE DETAILS — CLICK TO EXPAND</h2>\n'
       '<p style="color:var(--muted);font-size:0.79rem;margin-bottom:0.75rem">'
       'Each field shows its <strong style="color:var(--cyan)">data type</strong> and purpose. '
       'PK = Primary Key (unique row identifier). FK = Foreign Key (links to another table). '
       'BOOL = true/false flag. FLOAT64 = decimal number. INT64 = whole number. TIMESTAMP = date + time.</p>')
html = html.replace(old, new, 1)
save(p, html)

# ── 10. market-opportunity.html — explain the score bars inline ───────────────
p = NET / "market-opportunity.html"
html = p.read_text(encoding="utf-8")
old = '<th>Opp. Score</th>'
new = ('<th>Opp. Score<span class="col-hint">0–100. Higher = bigger growth opportunity. '
       'Bar shows score relative to top region.</span></th>')
html = html.replace(old, new, 1)
old = '<th>Avg Demand</th>'
new = ('<th>Avg Demand<span class="col-hint">Mean demand score across all listings in the region. '
       'Scale 0–100; platform avg = ~6.</span></th>')
html = html.replace(old, new, 1)
save(p, html)

# ── 11. seasonality.html — explain the demand multiplier cards ───────────────
p = NET / "seasonality.html"
html = p.read_text(encoding="utf-8")
old = '<h2>Demand Multipliers (2026–2027)</h2>'
new = ('<h2>Demand Multipliers (2026–2027)</h2>\n'
       '<div style="background:rgba(255,255,255,0.03);border:1px solid var(--border);border-radius:7px;'
       'padding:0.7rem 0.9rem;margin-bottom:0.9rem;font-size:0.79rem;color:var(--muted)">'
       '<strong style="color:var(--text)">How to read these:</strong> A multiplier of <strong style="color:#ff4444">1.62×</strong> '
       'means demand is 62% above the annual average during that period — so a property that normally charges '
       'R1,000/night could justifiably charge <strong>R1,620/night</strong>. '
       'School holidays (+20%) and public holidays (+15%) compound on top of the seasonal baseline. '
       'Baseline 1.0 = average nightly demand across the full year.</div>')
html = html.replace(old, new, 1)
save(p, html)

# ── 12. ml-features.html — explain model metric cards ────────────────────────
p = NET / "ml-features.html"
html = p.read_text(encoding="utf-8")
old = '<div class="model-cards">'
new = ('<div style="background:rgba(255,255,255,0.03);border:1px solid var(--border);border-radius:7px;'
       'padding:0.7rem 0.9rem;margin-bottom:0.85rem;font-size:0.79rem;color:var(--muted)">'
       '<strong style="color:var(--text)">How to read the model cards:</strong> '
       '<strong style="color:var(--cyan)">R²</strong> (R-squared) = % of variance the model explains — '
       '0.82 means 82% of demand variation is explained by the features. '
       '<strong style="color:var(--cyan)">F1</strong> = balance of precision and recall for classification — '
       '1.0 = perfect. <strong style="color:var(--cyan)">AUC</strong> = ability to rank positive vs negative '
       'outcomes — 0.5 = random chance, 1.0 = perfect. '
       'All models were trained on <strong>synthetic data</strong> — metrics are illustrative.</div>\n'
       '<div class="model-cards">')
html = html.replace(old, new, 1)
save(p, html)

# ── 13. seo-pages.html — explain difficulty column ───────────────────────────
p = NET / "seo-pages.html"
html = p.read_text(encoding="utf-8")
old = '<th>Difficulty</th>'
new = ('<th>Difficulty<span class="col-hint">Keyword Competition: Low = achievable with good content. '
       'High = requires domain authority + backlinks.</span></th>')
html = html.replace(old, new, 1)
old = '<th>Monthly Searches</th>'
new = ('<th>Monthly Searches<span class="col-hint">Estimated monthly Google searches for this keyword '
       'in South Africa. Actual traffic depends on ranking position.</span></th>')
html = html.replace(old, new, 1)
save(p, html)

# ── 14. Add metric glossary footer to dashboard.html ─────────────────────────
p = NET / "dashboard.html"
html = p.read_text(encoding="utf-8")
GLOSSARY = """
<!-- Metric glossary -->
<div style="background:#161b22;border-top:1px solid #30363d;padding:1.5rem;margin-top:2rem;font-size:0.78rem;color:#8b949e">
  <div style="font-size:0.75rem;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;color:#FF6C00;margin-bottom:0.85rem">Metric Glossary</div>
  <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:0.6rem">
    <div><strong style="color:#e6edf3">Demand Score</strong> — Composite 0–100: booking-event frequency (40%) + review count (30%) + promo activity (30%). Platform average ≈ 6.</div>
    <div><strong style="color:#e6edf3">Price per Night</strong> — Nightly rate in South African Rand (ZAR / R) as listed on LekkeSlaap.co.za at time of scrape (June 2026).</div>
    <div><strong style="color:#e6edf3">Price Tier</strong> — Budget = under R800. Mid-Range = R800–R1,500. Premium = R1,500–R3,000. Luxury = above R3,000.</div>
    <div><strong style="color:#e6edf3">GA4 Sessions</strong> — Synthetic web sessions generated to mirror real LekkeSlaap traffic patterns. Not live data.</div>
    <div><strong style="color:#e6edf3">ML Cluster</strong> — K-Means group (k=4) based on price, demand, reviews, listing count. Used to segment regions for targeting.</div>
    <div><strong style="color:#e6edf3">ROAS</strong> — Return on Ad Spend. ROAS of 3× means every R1 spent on ads generates R3 in bookings. Break-even = 1×.</div>
    <div><strong style="color:#e6edf3">Price–Demand r</strong> — Pearson correlation coefficient. Global r = -0.279 means cheaper properties tend to get more bookings (weak negative relationship).</div>
    <div><strong style="color:#e6edf3">Pearson r range</strong> — r near 0 = no relationship. r = -1 = perfect inverse. r = +1 = perfect positive. Magnitude matters more than direction.</div>
  </div>
</div>
"""
if "Metric Glossary" not in html:
    html = html.replace("</body>", GLOSSARY + "\n</body>", 1)
    save(p, html)
else:
    print("  Skipped dashboard.html — glossary already present")

print("\nAll context updates complete.")
print("Pages updated with What/Why/So What banners:")
for name in ["data-model.html","seasonality.html","ml-features.html","market-opportunity.html",
             "seo-pages.html","site-audit.html","mobile-attribution.html","seo-audit.html","dashboard.html"]:
    print(f"  {name}")
