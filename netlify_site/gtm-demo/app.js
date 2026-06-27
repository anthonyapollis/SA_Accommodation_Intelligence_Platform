const cfg = window.LEKKESLAAP_GTM_CONFIG || { currency:"ZAR" };
const catalog = window.LEKKESLAAP_CATALOG;
const products = catalog?.products || [];
const displayProducts = products.slice(0, 24);

let selectedProperty = products[0];
let cart = [selectedProperty];
let eventCount = 0;

const gtmStatus   = document.querySelector("#gtmStatus");
const grid        = document.querySelector("#productGrid");
const log         = document.querySelector("#eventLog");
const noscript    = document.querySelector("#gtm-noscript");
const catalogSrc  = document.querySelector("#catalogSource");
const statsEl     = document.querySelector("#catalog");
const filterBtns  = document.querySelector("#filterButtons");
const productCnt  = document.querySelector("#productCount");
const funnelEl    = document.querySelector("#funnelProgress");

function formatMoney(v) {
  return new Intl.NumberFormat("en-ZA",{style:"currency",currency:"ZAR",maximumFractionDigits:0}).format(v);
}

function gaItem(p) {
  return {
    item_id:        p.item_id,
    item_name:      p.item_name,
    item_category:  p.item_category,
    item_category2: p.item_category2,
    item_list_id:   "lekkeslaap_search_results",
    item_list_name: "LekkeSlaap search results",
    price:          p.price,
    price_tier:     p.price_tier,
    quantity:       p.quantity,
    index:          p.index,
  };
}

function pushEvent(eventName, payload={}) {
  const e = {
    event:        eventName,
    event_id:     `lks_${Date.now()}_${eventCount}`,
    page_type:    "search_results",
    page_path:    window.location.pathname + window.location.hash,
    site:         "lekkeslaap.co.za",
    user: {
      login_status:       "guest",
      popia_consent:      "granted",
      consent_analytics:  "granted",
      consent_ads:        "denied",
    },
    ...payload,
  };
  window.dataLayer.push(e);
  eventCount++;
  renderLog(e);
}

function renderLog(e) {
  const entry = JSON.stringify(e, null, 2);
  log.textContent = `[${new Date().toLocaleTimeString()}] ${entry}\n\n` + log.textContent;
}

function renderProducts() {
  grid.innerHTML = displayProducts.map(p => `
    <article class="product-card">
      <img src="${p.image}" alt="${p.item_name}" loading="lazy">
      ${p.has_promo ? `<div class="promo-banner">${p.discount_pct}% OFF — Flash Deal</div>` : ""}
      <div class="product-body">
        <div class="meta">
          <span>${p.item_category}</span>
          <span class="stars">&#9733; ${(4 + Math.random()*0.9).toFixed(1)}</span>
        </div>
        <h3>${p.item_name}</h3>
        <div class="meta"><span>${p.item_category2}</span><span>${p.review_count} reviews</span></div>
        <div class="price-row">
          <strong>${formatMoney(p.price)}<small style="font-size:11px;font-weight:400">/night</small></strong>
          <span class="tier-pill">${p.price_tier}</span>
        </div>
        <div class="card-actions">
          <button type="button" data-action="select" data-sku="${p.item_id}">View</button>
          <button class="primary" type="button" data-action="wishlist" data-sku="${p.item_id}">&#9829; Save</button>
        </div>
      </div>
    </article>
  `).join("");
}

function renderStats() {
  if (!catalog) return;
  catalogSrc.textContent = `${catalog.total_properties.toLocaleString()} properties · ${catalog.total_regions} regions · LekkeSlaap.co.za`;
  productCnt.textContent = `${displayProducts.length} shown from ${catalog.total_properties.toLocaleString()} listings`;
  statsEl.innerHTML = `
    <article class="stat-tile"><span>Total listings</span><strong>${catalog.total_properties.toLocaleString()}</strong></article>
    <article class="stat-tile"><span>Regions</span><strong>${catalog.total_regions}</strong></article>
    <article class="stat-tile"><span>Avg price/night</span><strong>${formatMoney(catalog.price_summary.average)}</strong></article>
    <article class="stat-tile"><span>GTM tags</span><strong>28</strong></article>
  `;
}

function renderFilters() {
  const typeButtons = (catalog?.top_types||[]).slice(0,4).map(([t,n])=>
    `<button type="button" data-action="filter" data-filter="type:${t}">${t} (${n})</button>`).join("");
  const regionButtons = (catalog?.top_regions||[]).slice(0,3).map(([r,n])=>
    `<button type="button" data-action="filter" data-filter="region:${r}">${r} (${n})</button>`).join("");
  filterBtns.innerHTML = typeButtons + regionButtons +
    `<button type="button" data-action="filter" data-filter="tier:Budget">Budget stays</button>
     <button type="button" data-action="filter" data-filter="availability:open">Available now</button>`;
}

function cartValue() {
  return cart.reduce((s,p)=>s+p.price*p.quantity, 0);
}

function handleProductAction(action, sku) {
  const p = products.find(x=>x.item_id===sku);
  if (!p) return;
  selectedProperty = p;

  if (action==="select") {
    pushEvent("select_item", {
      ecommerce:{ item_list_id:"lekkeslaap_search_results", item_list_name:"Search results", items:[gaItem(p)] }
    });
    pushEvent("view_item", {
      page_type:"property_detail",
      ecommerce:{ currency:"ZAR", value:p.price, items:[gaItem(p)] }
    });
  }
  if (action==="wishlist") {
    pushEvent("wishlist_add", {
      property_id: p.item_id,
      property_name: p.item_name,
      price_tier: p.price_tier,
      region: p.item_category2,
    });
  }
}

function handleGlobalAction(action, target) {
  if (action==="search") {
    pushEvent("search", { search_term:"Cape Town", check_in:"2026-07-12", check_out:"2026-07-15", guests:2 });
  }
  if (action==="filter") {
    pushEvent("filter_apply", { filter:target.dataset.filter, item_list_id:"lekkeslaap_search_results" });
  }
  if (action==="date-check") {
    pushEvent("date_availability_check", {
      property_id: selectedProperty?.item_id,
      check_in:"2026-07-12", check_out:"2026-07-15", guests:2,
    });
  }
  if (action==="map-view") {
    pushEvent("map_view_toggle", { view:"map", region:"Cape Town" });
  }
  if (action==="contact-host") {
    pushEvent("contact_host", {
      property_id: selectedProperty?.item_id,
      property_name: selectedProperty?.item_name,
      contact_method:"enquiry_form",
    });
  }
  if (action==="phone-reveal") {
    pushEvent("phone_number_reveal", {
      property_id: selectedProperty?.item_id,
      region: selectedProperty?.item_category2,
    });
  }
  if (action==="begin-checkout") {
    cart=[selectedProperty];
    pushEvent("begin_checkout", {
      ecommerce:{ currency:"ZAR", value:cartValue(), items:cart.map(gaItem) }
    });
  }
  if (action==="payment") {
    pushEvent("add_payment_info", {
      ecommerce:{ currency:"ZAR", value:cartValue(), payment_type:"credit_card", items:cart.map(gaItem) }
    });
  }
  if (action==="purchase") {
    const txId = `LKS-${new Date().toISOString().slice(0,10).replace(/-/g,"")}-${Math.floor(Math.random()*9000+1000)}`;
    pushEvent("purchase", {
      transaction_id: txId,
      affiliation:"LekkeSlaap.co.za",
      ecommerce:{
        transaction_id: txId, currency:"ZAR", value:cartValue(),
        tax: +(cartValue()*0.15).toFixed(2), shipping:0,
        items: cart.map(gaItem),
      }
    });
  }
  if (action==="share") {
    pushEvent("share", { method:"whatsapp", content_type:"property", item_id:selectedProperty?.item_id });
  }
  if (action==="login") {
    pushEvent("login", {
      method:"email",
      user:{ login_status:"logged_in", popia_consent:"granted", consent_analytics:"granted", consent_ads:"granted" }
    });
  }
  if (action==="consent") {
    pushEvent("consent_update", {
      analytics_storage:"granted", ad_storage:"denied", functionality_storage:"granted",
      popia_version:"2026-01", purpose:"accommodation_platform",
    });
  }
  if (action==="scroll") {
    pushEvent("scroll_depth", { percent:75, page_type:"search_results" });
  }
  if (action==="clear-log") { log.textContent=""; }
}

function initGtm() {
  const id = cfg.gtmId||"GTM-XXXXXXX";
  gtmStatus.textContent = id==="GTM-XXXXXXX" ? "Demo mode — add GTM ID to config.js" : id;
  if (noscript && id!=="GTM-XXXXXXX") {
    noscript.src=`https://www.googletagmanager.com/ns.html?id=${id}`;
  }
}

document.addEventListener("click", e=>{
  const btn = e.target.closest("button");
  if (!btn) return;
  const action = btn.dataset.action;
  if (!action) return;
  if (action==="select"||action==="wishlist") { handleProductAction(action, btn.dataset.sku); return; }
  handleGlobalAction(action, btn);
});

renderStats();
renderFilters();
renderProducts();
initGtm();

pushEvent("page_view", { page_title:document.title, page_location:window.location.href });
pushEvent("view_item_list", {
  ecommerce:{ item_list_id:"lekkeslaap_search_results", item_list_name:"LekkeSlaap search results", items:displayProducts.map(gaItem) }
});
