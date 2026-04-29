/* ───────────────────────────────────────────────────────
   app.js  –  Harvestment Frontend Logic
   ─────────────────────────────────────────────────────── */

const API = "http://localhost:8000";
let scenarioChart = null;
let costChart     = null;
let lastData      = null;

// ── INIT ─────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
    initNavbar();
    loadOptions();
    loadMetrics();
    document.getElementById("btn-get-started").addEventListener("click", () => {
        document.getElementById("advisory").scrollIntoView({ behavior: "smooth" });
    });
    document.getElementById("prediction-form").addEventListener("submit", handleSubmit);
    window.addEventListener("click", e => {
        if (e.target.classList.contains("modal-overlay")) e.target.classList.remove("active");
    });
});

// ── NAVBAR SCROLL EFFECT ─────────────────────────────────
function initNavbar() {
    window.addEventListener("scroll", () => {
        const nb = document.getElementById("navbar");
        nb.classList.toggle("scrolled", window.scrollY > 60);
    });
}

// ── LOAD OPTIONS (dropdowns) ─────────────────────────────
async function loadOptions() {
    try {
        const res  = await fetch(`${API}/options`);
        const opts = await res.json();
        populate("district",  opts.district);
        populate("crop",      opts.Crop);
        populate("season",    opts.Season);
        populate("soil_type", opts.soil_type);
    } catch {
        // Fallback static lists if API is unreachable
        populate("district",  ["Amreli","Anand","Banaskantha","Bharuch","Rajkot","Surat"]);
        populate("crop",      ["Groundnut","Wheat","Cotton(lint)","Sugarcane","Bajra","Maize"]);
        populate("season",    ["Kharif","Rabi","Other"]);
        populate("soil_type", ["Black","Alluvial","Red","Laterite","Desert"]);
    }
}

function populate(id, values) {
    const sel = document.getElementById(id);
    sel.innerHTML = values.map((v, i) =>
        `<option value="${v}"${i === 0 ? " selected" : ""}>${v}</option>`
    ).join("");
}

// ── LOAD MODEL METRICS ────────────────────────────────────
async function loadMetrics() {
    try {
        const res = await fetch(`${API}/metrics`);
        const m   = await res.json();
        const r2  = m.r2_score ?? "—";
        document.getElementById("nav-r2").textContent    = `R² ${r2}`;
        document.getElementById("stat-r2").textContent   = r2;
    } catch { /* silent */ }
}

// ── FORM SUBMIT ───────────────────────────────────────────
async function handleSubmit(e) {
    e.preventDefault();
    showLoading(true);

    const payload = {
        district:             document.getElementById("district").value,
        crop:                 document.getElementById("crop").value,
        season:               document.getElementById("season").value,
        area:                 parseFloat(document.getElementById("area").value),
        soil_type:            document.getElementById("soil_type").value,
        soil_fertility_score: parseFloat(document.getElementById("soil_fertility").value),
        irrigation_score:     parseFloat(document.getElementById("irrigation").value),
    };

    try {
        const res = await fetch(`${API}/predict`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });
        if (!res.ok) throw new Error(await res.text());
        const data = await res.json();
        lastData = data;
        populateAll(data);
        showDashboard(data);
    } catch (err) {
        alert("❌ Could not reach the backend.\n\nMake sure the API is running:\n  python -m uvicorn api:app --reload --port 8000\n\n" + err.message);
        console.error(err);
    } finally {
        showLoading(false);
    }
}

// ── LOADING ───────────────────────────────────────────────
function showLoading(on) {
    const ov  = document.getElementById("loading-overlay");
    const btn = document.getElementById("submit-btn");
    ov.classList.toggle("active", on);
    btn.disabled = on;
    document.getElementById("btn-text").textContent = on ? "⏳ Analyzing…" : "🚀 Run AI Prediction";
}

// ── SHOW DASHBOARD ────────────────────────────────────────
function showDashboard(data) {
    const dash = document.getElementById("dashboard-section");
    dash.style.display = "block";
    setTimeout(() => dash.scrollIntoView({ behavior: "smooth" }), 120);

    const crop = data.crop;
    const dist = data.district;
    document.getElementById("dashboard-subtitle").textContent =
        `${crop} · ${dist} · ${data.season} · ${data.area_ha} ha`;
}

// ── POPULATE ALL SECTIONS ─────────────────────────────────
function populateAll(data) {
    const fin = data.financials.financial_summary;
    const be  = data.financials.breakeven;
    const sc  = data.financials.scenarios;
    const cd  = data.financials.cost_breakdown;
    const wt  = data.live_weather;

    // Summary strip
    document.getElementById("strip-yield").textContent      = `${data.predicted_yield} t/ha`;
    setColoredValue("strip-profit", fin.expected_net_profit_inr, true, true);
    document.getElementById("strip-roi").textContent        = `${fin.expected_roi_percent}%`;
    document.getElementById("strip-roi").style.color        = fin.expected_roi_percent >= 0 ? "var(--success)" : "var(--danger)";
    document.getElementById("strip-temp").textContent       = `${wt.current_temp ?? "—"}°C`;
    document.getElementById("strip-confidence").textContent = data.confidence;

    // Card previews
    document.getElementById("preview-yield").textContent    = `${data.predicted_yield} t/ha`;
    document.getElementById("preview-profit").textContent   = formatINR(fin.expected_net_profit_inr);
    document.getElementById("preview-cost").textContent     = formatINR(fin.total_cost_inr);
    document.getElementById("preview-weather").textContent  = `${wt.current_temp ?? "—"}°C`;
    document.getElementById("preview-breakeven").textContent= `${be.breakeven_yield_per_ha} t/ha`;

    // ── YIELD MODAL ──────────────────────────────────────
    document.getElementById("yield-meta").textContent =
        `${data.crop} · ${data.district} · ${data.season}`;
    document.getElementById("res-yield").textContent    = `${data.predicted_yield}`;
    document.getElementById("res-min-yield").textContent= `${data.min_yield}`;
    document.getElementById("res-max-yield").textContent= `${data.max_yield}`;
    document.getElementById("res-total-yield").textContent = `${data.total_predicted} t`;
    document.getElementById("res-total-range").textContent = `${data.total_min} – ${data.total_max} tonnes`;
    document.getElementById("res-category").textContent = data.yield_category;
    document.getElementById("res-confidence").textContent = data.confidence;
    setYieldGauge(data.min_yield, data.predicted_yield, data.max_yield);
    document.getElementById("yield-insight").textContent =
        `Predicted ${data.predicted_yield} t/ha is classified as ${data.yield_category} for ${data.crop} in Gujarat. ` +
        `The 80% confidence interval spans ${data.min_yield}–${data.max_yield} t/ha.`;

    // ── FINANCIAL MODAL ──────────────────────────────────
    document.getElementById("fin-meta").textContent =
        `${data.crop} · ${data.area_ha} ha · Market price ₹${fin.market_price_per_tonne_inr.toLocaleString("en-IN")}/tonne`;
    document.getElementById("res-cost").textContent    = formatINR(fin.total_cost_inr);
    document.getElementById("res-revenue").textContent = formatINR(fin.expected_gross_revenue_inr);
    setColoredValue("res-profit", fin.expected_net_profit_inr, true);
    setColoredValue("res-roi",    fin.expected_roi_percent, false, false, "%");
    document.getElementById("res-msp").textContent     = `₹${fin.market_price_per_tonne_inr.toLocaleString("en-IN")}`;
    document.getElementById("res-cost-ha").textContent = `₹${fin.cost_per_ha_inr.toLocaleString("en-IN")}`;
    document.getElementById("fin-insight").textContent =
        `Based on ${data.crop} MSP/APMC rates (₹${fin.market_price_per_tonne_inr.toLocaleString("en-IN")}/tonne) and CACP cultivation costs for Gujarat.`;
    const alert = document.getElementById("breakeven-alert");
    alert.style.display = fin.breakeven_risk_alert ? "block" : "none";

    // ── SCENARIO CARDS ────────────────────────────────────
    fillScenario("pess", sc.pessimistic);
    fillScenario("exp",  sc.expected);
    fillScenario("opt",  sc.optimistic);
    renderScenarioChart(sc);

    // ── WEATHER ──────────────────────────────────────────
    document.getElementById("res-district").textContent   = data.district;
    document.getElementById("w-temp-big").textContent     = `${wt.current_temp ?? "—"}°C`;
    document.getElementById("w-min-temp").textContent     = `${wt.min_temp ?? "—"}°C`;
    document.getElementById("w-max-temp").textContent     = `${wt.max_temp ?? "—"}°C`;
    document.getElementById("w-hum").textContent          = `${wt.humidity_avg ?? "—"}%`;
    document.getElementById("w-rain").textContent         = `${wt.current_rain_mm ?? 0} mm/h`;

    // ── COST BREAKDOWN ────────────────────────────────────
    document.getElementById("cost-meta").textContent =
        `Total: ${formatINR(fin.total_cost_inr)} for ${data.area_ha} ha of ${data.crop}`;
    renderCostTable(cd, fin.total_cost_inr);
    renderCostChart(cd);

    // ── BREAKEVEN ─────────────────────────────────────────
    document.getElementById("res-breakeven-yield").textContent = `${be.breakeven_yield_per_ha} t/ha`;
    document.getElementById("res-pred-yield-be").textContent   = `${data.predicted_yield} t/ha`;
    document.getElementById("res-margin").textContent          = `${be.margin_above_breakeven_tha} t/ha`;
    document.getElementById("res-breakeven-prod").textContent  = `${be.breakeven_production_t} tonnes`;
    renderBeBar(be.breakeven_yield_per_ha, data.predicted_yield, data.max_yield);
    const risk = be.breakeven_risk;
    document.getElementById("be-insight-text").textContent = risk
        ? "⚠️ Your predicted yield is dangerously close to the breakeven threshold. Consider reducing input costs or boosting irrigation."
        : `✅ Your predicted yield (${data.predicted_yield} t/ha) is ${be.margin_above_breakeven_tha} t/ha above the breakeven point. You are in the profit zone.`;
    document.getElementById("be-box-risk").className = "data-box " + (risk ? "highlight-red" : "highlight-green");
}

// ── HELPERS ───────────────────────────────────────────────
function formatINR(v) {
    if (v == null) return "₹—";
    return "₹" + Math.abs(v).toLocaleString("en-IN", { maximumFractionDigits: 0 });
}

function setColoredValue(id, val, rupee = false, large = false, suffix = "") {
    const el = document.getElementById(id);
    if (!el) return;
    const pos = val >= 0;
    el.textContent = (rupee ? (pos ? "₹" : "−₹") + Math.abs(val).toLocaleString("en-IN", { maximumFractionDigits: 0 }) : (pos ? "" : "−") + Math.abs(val)) + suffix;
    el.style.color = pos ? "var(--success)" : "var(--danger)";
}

function fillScenario(key, sc) {
    document.getElementById(`sc-${key}-assumption`).textContent = sc.assumptions;
    document.getElementById(`sc-${key}-profit`).textContent     = formatINR(sc.net_profit_inr);
    document.getElementById(`sc-${key}-roi`).textContent        = `ROI: ${sc.roi_percent}%`;
}

// ── YIELD GAUGE ───────────────────────────────────────────
function setYieldGauge(min, pred, max) {
    const range = max - min || 1;
    const pct   = ((pred - min) / range) * 100;
    document.getElementById("gauge-fill").style.width   = `${Math.min(pct, 100)}%`;
    document.getElementById("gauge-marker").style.left  = `${Math.min(pct, 100)}%`;
}

// ── BREAKEVEN BAR ─────────────────────────────────────────
function renderBeBar(breakeven, predicted, maxY) {
    const scale = maxY * 1.1 || 1;
    const bePct = Math.min((breakeven / scale) * 100, 100);
    const prPct = Math.min((predicted / scale) * 100, 100);
    document.getElementById("be-cost-bar").style.width = `${bePct}%`;
    document.getElementById("be-pred-bar").style.left  = `${prPct}%`;
}

// ── COST TABLE ────────────────────────────────────────────
function renderCostTable(breakdown, total) {
    const container = document.getElementById("cost-table");
    const max = Math.max(...Object.values(breakdown));
    container.innerHTML = Object.entries(breakdown).map(([label, amount]) => {
        const pct = Math.round((amount / max) * 100);
        return `<div class="cost-row">
            <span class="cost-row-label">${label}</span>
            <div class="cost-row-bar"><div class="cost-row-fill" style="width:${pct}%"></div></div>
            <span class="cost-row-amount">₹${amount.toLocaleString("en-IN", { maximumFractionDigits: 0 })}</span>
        </div>`;
    }).join("");
}

// ── CHARTS ────────────────────────────────────────────────
function renderScenarioChart(sc) {
    const ctx = document.getElementById("scenarioChart").getContext("2d");
    if (scenarioChart) scenarioChart.destroy();

    const labels = ["Pessimistic", "Expected", "Optimistic"];
    const values = [sc.pessimistic.net_profit_inr, sc.expected.net_profit_inr, sc.optimistic.net_profit_inr];
    const colors = values.map(v => v < 0 ? "rgba(239,83,80,0.75)" : v === sc.expected.net_profit_inr ? "rgba(232,160,32,0.75)" : "rgba(76,175,120,0.75)");
    const borders= values.map(v => v < 0 ? "#ef5350" : v === sc.expected.net_profit_inr ? "#e8a020" : "#4caf78");

    scenarioChart = new Chart(ctx, {
        type: "bar",
        data: {
            labels,
            datasets: [{
                label: "Net Profit (₹)",
                data: values,
                backgroundColor: colors,
                borderColor: borders,
                borderWidth: 1.5,
                borderRadius: 8,
            }]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                x: { ticks: { color: "#9a9590" }, grid: { color: "rgba(255,255,255,0.05)" } },
                y: {
                    ticks: { color: "#9a9590", callback: v => "₹" + (v / 1000).toFixed(0) + "k" },
                    grid: { color: "rgba(255,255,255,0.05)" }
                }
            }
        }
    });
}

function renderCostChart(breakdown) {
    const ctx = document.getElementById("costChart").getContext("2d");
    if (costChart) costChart.destroy();
    const palette = ["#e8a020","#c47c1a","#f5d06a","#ff9800","#4caf78","#42a5f5"];
    costChart = new Chart(ctx, {
        type: "doughnut",
        data: {
            labels: Object.keys(breakdown),
            datasets: [{
                data: Object.values(breakdown),
                backgroundColor: palette,
                borderColor: "#1a1e26",
                borderWidth: 2,
                hoverOffset: 8,
            }]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: {
                legend: { position: "right", labels: { color: "#9a9590", font: { size: 11 }, boxWidth: 14 } }
            }
        }
    });
}

// ── MODAL HELPERS ─────────────────────────────────────────
function openModal(id)  { document.getElementById(id).classList.add("active"); }
function closeModal(id) { document.getElementById(id).classList.remove("active"); }
