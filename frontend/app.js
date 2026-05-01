/* ───────────────────────────────────────────────────────
   app.js  –  Harvestment Frontend Logic
   ─────────────────────────────────────────────────────── */

const API = (window.location.origin && window.location.origin !== "null")
    ? window.location.origin
    : "http://localhost:8000";
let scenarioChart = null;
let costChart     = null;
let lastData      = null;

const STORAGE_KEY = "harvestment:lastPrediction";

// ── MONTH → SEASON MAPPING ────────────────────────────
// Kharif: June–October (monsoon sowing)
// Rabi:   November–March (winter sowing)
// Other:  April–May (Zaid / summer crops)
const MONTH_TO_SEASON = {
    1: "Rabi", 2: "Rabi", 3: "Rabi",
    4: "Other", 5: "Other",
    6: "Kharif", 7: "Kharif", 8: "Kharif", 9: "Kharif", 10: "Kharif",
    11: "Rabi", 12: "Rabi",
};

// ── INIT ─────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
    initNavbar();
    loadMetrics();

    const btnGetStarted = document.getElementById("btn-get-started");
    if (btnGetStarted) {
        btnGetStarted.addEventListener("click", () => {
            window.location.href = "/advisory";
        });
    }

    // Advisory page: form + dropdown options
    const predictionForm = document.getElementById("prediction-form");
    if (predictionForm) {
        loadOptions();
        predictionForm.addEventListener("submit", handleSubmit);
        initMonthSeasonWiring();
        initIrrigationCards();
    }

    // Dashboard page: render from last prediction
    const dashboard = document.getElementById("dashboard-section");
    if (dashboard && !predictionForm) {
        tryLoadDashboardFromStorage();
    }

    window.addEventListener("click", e => {
        if (e.target.classList.contains("modal-overlay")) e.target.classList.remove("active");
    });
});

// ── NAVBAR SCROLL EFFECT ─────────────────────────────────
function initNavbar() {
    window.addEventListener("scroll", () => {
        const nb = document.getElementById("navbar");
        if (nb) nb.classList.toggle("scrolled", window.scrollY > 60);
    });

    // Active link highlight for multi-page navigation
    const path = (window.location.pathname || "/").toLowerCase();
    const navHome     = document.getElementById("nav-home");
    const navAdvisory = document.getElementById("nav-advisory");
    const navDashboard= document.getElementById("nav-dashboard");
    const navCrops    = document.getElementById("nav-crops");
    [navHome, navAdvisory, navDashboard, navCrops].forEach(el => el && el.classList.remove("active"));
    if (path.endsWith("/advisory"))       navAdvisory?.classList.add("active");
    else if (path.endsWith("/dashboard")) navDashboard?.classList.add("active");
    else if (path.endsWith("/crops"))     navCrops?.classList.add("active");
    else navHome?.classList.add("active");
}

// ── PLANTING MONTH → SEASON AUTO-FILL ────────────────────
function initMonthSeasonWiring() {
    const monthSel  = document.getElementById("planting_month");
    const seasonSel = document.getElementById("season");
    if (!monthSel || !seasonSel) return;

    monthSel.addEventListener("change", () => {
        const month = parseInt(monthSel.value, 10);
        const suggested = MONTH_TO_SEASON[month] || "";

        // Rebuild season options with the suggested one pre-selected
        const seasons = ["Kharif", "Rabi", "Other"];
        seasonSel.innerHTML = seasons
            .map(s => `<option value="${s}"${s === suggested ? " selected" : ""}>${s}</option>`)
            .join("");
    });
}

// ── IRRIGATION CARD WIRING ───────────────────────────────
function initIrrigationCards() {
    const cards   = document.querySelectorAll(".irrigation-card input[type=radio]");
    const hidden  = document.getElementById("irrigation");
    if (!cards.length || !hidden) return;

    cards.forEach(radio => {
        radio.addEventListener("change", () => {
            hidden.value = radio.value;
            // Visual active state
            document.querySelectorAll(".irrigation-card").forEach(c => c.classList.remove("selected"));
            radio.closest(".irrigation-card")?.classList.add("selected");
        });
    });
}

// ── LOAD OPTIONS (dropdowns) ─────────────────────────────
async function loadOptions() {
    try {
        const res  = await fetch(`${API}/options`);
        const opts = await res.json();
        populate("district",  opts.district);
        populate("crop",      opts.Crop);
        populate("soil_type", opts.soil_type);
        // Season is handled by month wiring — don't auto-populate it
    } catch {
        // Fallback static lists if API is unreachable
        populate("district",  ["Amreli","Anand","Banaskantha","Bharuch","Rajkot","Surat"]);
        populate("crop",      ["Groundnut","Wheat","Cotton(lint)","Sugarcane","Bajra","Maize"]);
        populate("soil_type", ["Black","Alluvial","Red","Laterite","Desert"]);
    }
}

/**
 * Populate a <select> element with an array of values.
 * Always adds a disabled placeholder as the first option so the
 * user must consciously choose — no accidental first-value submission.
 */
function populate(id, values) {
    const sel = document.getElementById(id);
    if (!sel) return;

    // Keep existing placeholder if present, otherwise generate one
    const placeholderText = sel.querySelector("option[disabled]")?.textContent || "— Select —";
    sel.innerHTML =
        `<option value="" disabled selected>${placeholderText}</option>` +
        values.map(v => `<option value="${v}">${v}</option>`).join("");
}

// ── LOAD MODEL METRICS ────────────────────────────────────
async function loadMetrics() {
    const badge = document.getElementById("nav-accuracy-badge");
    const navR2 = document.getElementById("nav-r2");
    try {
        const res = await fetch(`${API}/metrics`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const m   = await res.json();
        const r2  = m.r2_score ?? null;

        if (r2 !== null) {
            if (navR2) navR2.textContent = `R² ${r2}`;
            if (badge) badge.style.visibility = "visible";
        }
        // Update hero stat if present
        const statR2 = document.getElementById("stat-r2");
        if (statR2 && r2 !== null) statR2.textContent = r2;
    } catch {
        // Metrics endpoint unavailable — keep badge hidden (already hidden via CSS)
        if (navR2) navR2.textContent = "Model Live";
        if (badge) badge.style.visibility = "visible";
    }
}

// ── FORM SUBMIT ───────────────────────────────────────────
async function handleSubmit(e) {
    e.preventDefault();

    // Validate irrigation selection (radio cards)
    const irrigationValue = document.getElementById("irrigation")?.value;
    if (irrigationValue === "" || irrigationValue === null || irrigationValue === undefined) {
        alert("⚠️ Please select your Irrigation / Water availability option before submitting.");
        return;
    }

    showLoading(true);

    const payload = {
        district:             document.getElementById("district").value,
        crop:                 document.getElementById("crop").value,
        season:               document.getElementById("season").value,
        area:                 parseFloat(document.getElementById("area").value),
        soil_type:            document.getElementById("soil_type").value,
        soil_fertility_score: parseFloat(document.getElementById("soil_fertility").value),
        irrigation_score:     parseFloat(irrigationValue),
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
        try {
            sessionStorage.setItem(STORAGE_KEY, JSON.stringify(data));
        } catch { /* ignore */ }
        window.location.href = "/dashboard";
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
    if (ov) ov.classList.toggle("active", on);
    if (btn) btn.disabled = on;
    const btnText = document.getElementById("btn-text");
    if (btnText) btnText.textContent = on ? "⏳ Analyzing…" : "🚀 Run AI Prediction";
}

function tryLoadDashboardFromStorage() {
    let raw = null;
    try {
        raw = sessionStorage.getItem(STORAGE_KEY);
    } catch { /* ignore */ }
    if (!raw) return;
    try {
        const data = JSON.parse(raw);
        lastData = data;
        populateAll(data);
        showDashboard(data);
    } catch {
        // ignore bad storage
    }
}

// ── SHOW DASHBOARD ────────────────────────────────────────
function showDashboard(data) {
    const dash = document.getElementById("dashboard-section");
    if (!dash) return;
    dash.style.display = "block";

    const crop = data.crop;
    const dist = data.district;
    const subtitle = document.getElementById("dashboard-subtitle");
    if (subtitle) subtitle.textContent = `${crop} · ${dist} · ${data.season} · ${data.area_ha} ha`;
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
