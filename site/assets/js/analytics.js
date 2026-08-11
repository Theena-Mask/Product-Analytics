/* ==========================================================================
   Solstice Outdoor Co. — analytics.js
   The ONLY file that talks to the dataLayer. Every page includes this
   before its own inline script. Change SOLSTICE_GTM_CONTAINER_ID to your
   real GTM-W48BV4SP before publishing.
   ========================================================================== */

const SOLSTICE_GTM_CONTAINER_ID = "GTM-W48BV4SP"; // <-- replace with your real container ID

window.dataLayer = window.dataLayer || [];

/* --------------------------------------------------------------------------
   Product catalog — shared across every page, $68–$148, matches the
   AOV ~$140 / 1–2 items per order profile used in the interview prep numbers.
   -------------------------------------------------------------------------- */
const SOLSTICE_CATALOG = [
  { id: "SOL-001", name: "Ridgeline Trail Shell",      category: "Jackets",  price: 148.00 },
  { id: "SOL-002", name: "Switchback Softshell",        category: "Jackets",  price: 129.00 },
  { id: "SOL-003", name: "Basecamp Down Vest",          category: "Jackets",  price: 118.00 },
  { id: "SOL-004", name: "Traverse Hiking Boot",        category: "Footwear", price: 142.00 },
  { id: "SOL-005", name: "Lowline Trail Runner",        category: "Footwear", price: 98.00  },
  { id: "SOL-006", name: "Alpine Wool Beanie",          category: "Accessories", price: 28.00 },
  { id: "SOL-007", name: "Contour 32L Daypack",         category: "Packs",    price: 112.00 },
  { id: "SOL-008", name: "Summit 65L Expedition Pack",  category: "Packs",    price: 148.00 },
  { id: "SOL-009", name: "Driftline Merino Tee",        category: "Base Layers", price: 68.00 },
  { id: "SOL-010", name: "Thermalayer Base Set",        category: "Base Layers", price: 84.00 },
];

function solsticeGetProduct(id) {
  return SOLSTICE_CATALOG.find((p) => p.id === id) || SOLSTICE_CATALOG[0];
}

/* --------------------------------------------------------------------------
   UTM capture — persisted across the whole session (sessionStorage), not
   just the landing page, so attribution survives multi-page browsing.
   -------------------------------------------------------------------------- */
function solsticeCaptureUtm() {
  const params = new URLSearchParams(window.location.search);
  const keys = ["utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content"];
  const incoming = {};
  let hasNew = false;
  keys.forEach((k) => {
    if (params.has(k)) {
      incoming[k] = params.get(k);
      hasNew = true;
    }
  });
  if (hasNew) {
    sessionStorage.setItem("solstice_utm", JSON.stringify(incoming));
  }
  return JSON.parse(sessionStorage.getItem("solstice_utm") || "{}");
}

/* --------------------------------------------------------------------------
   Lead scoring — running total in localStorage, weights match the GTM
   Lookup Table: view_item=2, add_to_cart=10, begin_checkout=20,
   purchase=50, contact_form_submit=15, generate_lead itself carries the
   score rather than re-adding it.
   -------------------------------------------------------------------------- */
const SOLSTICE_LEAD_WEIGHTS = {
  view_item: 2,
  add_to_cart: 10,
  begin_checkout: 20,
  purchase: 50,
  contact_form_submit: 15,
};

function solsticeAddLeadScore(eventName) {
  const weight = SOLSTICE_LEAD_WEIGHTS[eventName] || 0;
  if (!weight) return solsticeGetLeadScore();
  const current = solsticeGetLeadScore();
  const next = current + weight;
  localStorage.setItem("solstice_lead_score", String(next));
  return next;
}
function solsticeGetLeadScore() {
  return parseInt(localStorage.getItem("solstice_lead_score") || "0", 10);
}

/* --------------------------------------------------------------------------
   Cart — plain localStorage array of { id, name, price, qty }.
   -------------------------------------------------------------------------- */
function solsticeGetCart() {
  return JSON.parse(localStorage.getItem("solstice_cart") || "[]");
}
function solsticeSetCart(cart) {
  localStorage.setItem("solstice_cart", JSON.stringify(cart));
}
function solsticeAddToCart(productId, qty = 1) {
  const product = solsticeGetProduct(productId);
  const cart = solsticeGetCart();
  const existing = cart.find((i) => i.id === productId);
  if (existing) {
    existing.qty += qty;
  } else {
    cart.push({ id: product.id, name: product.name, price: product.price, qty });
  }
  solsticeSetCart(cart);
  return cart;
}
function solsticeClearCart() {
  localStorage.removeItem("solstice_cart");
}
function solsticeCartValue(cart) {
  return cart.reduce((sum, i) => sum + i.price * i.qty, 0);
}

/* --------------------------------------------------------------------------
   Ecommerce push — GA4 reads the `ecommerce` object straight off the
   dataLayer (sendEcommerceData: true pattern), rather than mapping each
   field as a separate GTM variable.
   -------------------------------------------------------------------------- */
function solsticePushEcommerce(eventName, ecommerceObj) {
  // GA4 best practice: clear the previous ecommerce object first so nested
  // objects don't merge across events.
  window.dataLayer.push({ ecommerce: null });
  window.dataLayer.push({
    event: eventName,
    ecommerce: ecommerceObj,
  });
}

function solsticeItemsFromCart(cart) {
  return cart.map((i) => ({
    item_id: i.id,
    item_name: i.name,
    price: i.price,
    quantity: i.qty,
  }));
}

/* --------------------------------------------------------------------------
   Consent Mode v2 — plain localStorage + a simple two-button banner.
   Default state (denied) is handled entirely inside GTM by the
   "Consent - Set Defaults (Denied)" tag on the Consent Initialization
   trigger, which always fires before anything else in the container.
   This code's only job is to tell GTM what the visitor chose, via a
   dataLayer event GTM's Consent Update triggers listen for.
   -------------------------------------------------------------------------- */
function solsticeInitConsentBanner() {
  const stored = localStorage.getItem("solstice_consent");
  if (stored) return; // already decided this session/device

  const banner = document.createElement("div");
  banner.className = "solstice-consent-banner";
  banner.innerHTML = `
    <div class="solstice-consent-copy">
      We use cookies to understand how this demo store is used and to show
      relevant ads. Nothing here is a real transaction.
    </div>
    <div class="solstice-consent-actions">
      <button type="button" class="btn btn-ghost" data-consent="reject">Reject</button>
      <button type="button" class="btn btn-primary" data-consent="accept">Accept all</button>
    </div>`;
  document.body.appendChild(banner);

  banner.querySelectorAll("[data-consent]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const choice = btn.getAttribute("data-consent");
      localStorage.setItem("solstice_consent", choice);
      window.dataLayer.push({ event: choice === "accept" ? "consent_accepted" : "consent_rejected" });
      banner.remove();
    });
  });
}

/* --------------------------------------------------------------------------
   DataLayer debug panel — small floating button, bottom-right, every page.
   Intercepts dataLayer.push so you can watch events land in real time
   while you click through the site yourself.
   -------------------------------------------------------------------------- */
function solsticeInitDebugPanel() {
  const toggle = document.createElement("button");
  toggle.className = "solstice-debug-toggle";
  toggle.type = "button";
  toggle.textContent = "dataLayer";
  document.body.appendChild(toggle);

  const panel = document.createElement("div");
  panel.className = "solstice-debug-panel";
  panel.innerHTML = `<div class="solstice-debug-head">dataLayer — live</div><div class="solstice-debug-body"></div>`;
  document.body.appendChild(panel);

  const body = panel.querySelector(".solstice-debug-body");
  toggle.addEventListener("click", () => panel.classList.toggle("open"));

  function render(entry) {
    const row = document.createElement("div");
    row.className = "solstice-debug-row";
    const label = entry.event || Object.keys(entry).join(",");
    row.innerHTML = `<span class="solstice-debug-event">${label}</span><pre>${JSON.stringify(entry, null, 2)}</pre>`;
    body.prepend(row);
  }

  const originalPush = window.dataLayer.push.bind(window.dataLayer);
  window.dataLayer.push = function (...args) {
    args.forEach((a) => render(a));
    return originalPush(...args);
  };

  // Render anything already pushed before the panel initialized.
  window.dataLayer.forEach(render);
}

/* --------------------------------------------------------------------------
   Click / form / scroll engagement hooks — GTM's own native triggers
   (Click Classes, Form Submission, Scroll Depth) do the actual tag firing;
   this file doesn't need to push engagement events itself. Elements just
   need class="track-click" or a real <form> for GTM's built-in triggers
   to pick up. Nothing to wire here — this comment documents why.
   -------------------------------------------------------------------------- */

/* --------------------------------------------------------------------------
   Boot — runs on every page.
   -------------------------------------------------------------------------- */
document.addEventListener("DOMContentLoaded", () => {
  solsticeCaptureUtm();
  solsticeInitConsentBanner();
  solsticeInitDebugPanel();

  // Cart count badge, if the page has one.
  const badge = document.querySelector("[data-cart-count]");
  if (badge) {
    const cart = solsticeGetCart();
    const count = cart.reduce((s, i) => s + i.qty, 0);
    badge.textContent = count;
    badge.style.display = count > 0 ? "inline-flex" : "none";
  }
});
