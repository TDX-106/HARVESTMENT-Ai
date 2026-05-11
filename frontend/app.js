/* ───────────────────────────────────────────────────────
   app.js  –  Harvestment Frontend Logic
   ─────────────────────────────────────────────────────── */

const API = (window.location.origin && window.location.origin !== "null")
    ? window.location.origin
    : "http://localhost:8000";
let scenarioChart = null;
let costChart     = null;
let lastData      = null;

/** Snapshot used for the "Previous advisory" cards + modals (from localStorage history). */
let previousSectionData   = null;
/** Entries shown as chips: all saved runs except the one matching the current dashboard. */
let previousAdvisoryOptions = [];

const STORAGE_KEY = "harvestment:lastPrediction";
const HISTORY_KEY = "harvestment:history";
/** Full prediction objects for each run (localStorage). */
const HISTORY_MAX = 25;

/** Align stored / legacy API keys so UI always reads crop, district, season, area_ha. */
function normalizeStoredPrediction(d) {
    if (!d || typeof d !== "object") return d;
    const out = { ...d };
    if (out.crop == null && out.Crop != null) out.crop = out.Crop;
    if (out.district == null && out.District != null) out.district = out.District;
    if (out.season == null && out.Season != null) out.season = out.Season;
    if (out.area_ha == null && out.area != null) out.area_ha = Number(out.area);
    if (out.area_ha == null && out.Area != null) out.area_ha = Number(out.Area);
    return out;
}

/** Same single-line summary as Full Report modal (`#report-meta`). */
function advisoryMetaLine(d) {
    const n = normalizeStoredPrediction(d);
    if (!n || typeof n !== "object") return "— · — · — · — ha";
    return `${n.crop || "—"} · ${n.district || "—"} · ${n.season || "—"} · ${n.area_ha ?? "—"} ha`;
}

function historyFingerprint(data) {
    if (!data) return "";
    const n = normalizeStoredPrediction(data);
    return [
        n.district,
        n.crop,
        n.season,
        n.area_ha,
        n.predicted_yield,
        n.financials?.financial_summary?.expected_net_profit_inr,
    ].join("|");
}

function loadHistory() {
    try {
        const raw = localStorage.getItem(HISTORY_KEY);
        if (!raw) return [];
        const arr = JSON.parse(raw);
        if (!Array.isArray(arr)) return [];

        // Normalize legacy/incorrect formats:
        // - old entries might be stored as the prediction object itself
        // - entry.data might be a JSON string
        // - entry might be missing savedAt
        return arr.map((entry) => {
            // Prediction object stored directly (with or without wrapper)
            const looksLikeFlatPayload =
                entry &&
                typeof entry === "object" &&
                !("data" in entry) &&
                (
                    "crop" in entry ||
                    "district" in entry ||
                    "Crop" in entry ||
                    "District" in entry ||
                    (entry.financials && typeof entry.financials === "object")
                );
            if (looksLikeFlatPayload) {
                const savedAt = typeof entry.savedAt === "string" ? entry.savedAt : new Date().toISOString();
                return { savedAt, data: normalizeStoredPrediction(entry) };
            }

            if (!entry || typeof entry !== "object") return null;

            let data = entry.data;
            if (typeof data === "string") {
                try { data = JSON.parse(data); } catch { /* ignore */ }
            }

            const savedAt = typeof entry.savedAt === "string" ? entry.savedAt : new Date().toISOString();
            if (!data || typeof data !== "object") return null;

            return { savedAt, data: normalizeStoredPrediction(data) };
        }).filter(Boolean);
    } catch {
        return [];
    }
}

function saveHistory(history) {
    try {
        localStorage.setItem(HISTORY_KEY, JSON.stringify(history));
    } catch { /* quota or private mode */ }
}

function persistPrediction(data) {
    const normalized = normalizeStoredPrediction(data);
    const json = JSON.stringify(normalized);
    try {
        sessionStorage.setItem(STORAGE_KEY, json);
    } catch { /* ignore */ }
    try {
        localStorage.setItem(STORAGE_KEY, json);
    } catch { /* ignore */ }

    let hist = loadHistory();
    const fp = historyFingerprint(normalized);
    if (hist.length && historyFingerprint(hist[0].data) === fp) {
        hist[0] = { savedAt: new Date().toISOString(), data: normalized };
    } else {
        hist.unshift({ savedAt: new Date().toISOString(), data: normalized });
    }
    hist = hist.slice(0, HISTORY_MAX);
    saveHistory(hist);
}

function formatRelativeTime(iso) {
    if (!iso) return "";
    const t = new Date(iso).getTime();
    if (Number.isNaN(t)) return "";
    const diff = Date.now() - t;
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return "just now";
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    const days = Math.floor(hrs / 24);
    if (days < 7) return `${days}d ago`;
    return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function renderPrevAdvisories(activeFp) {
    const section = document.getElementById("prev-advisory-section");
    const list = document.getElementById("prev-searches-list");
    if (!section || !list) return;

    const hist = loadHistory().filter(e => {
        const d = normalizeStoredPrediction(e?.data);
        return d && typeof d === "object" && (d.crop || d.district);
    });
    if (!hist.length) {
        section.style.display = "none";
        list.innerHTML = "";
        previousSectionData = null;
        previousAdvisoryOptions = [];
        return;
    }

    const fpActive = activeFp || (lastData ? historyFingerprint(lastData) : "");
    const entriesToShow = fpActive
        ? hist.filter(e => historyFingerprint(e?.data) !== fpActive)
        : hist.slice(0);

    if (!entriesToShow.length) {
        section.style.display = "none";
        list.innerHTML = "";
        previousSectionData = null;
        previousAdvisoryOptions = [];
        return;
    }

    section.style.display = "block";
    previousAdvisoryOptions = entriesToShow;

    list.replaceChildren();
    entriesToShow.forEach((entry, idx) => {
        const d = normalizeStoredPrediction(entry.data);
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "prev-search-chip notranslate" + (idx === 0 ? " is-active" : "");
        btn.dataset.prevIdx = String(idx);
        btn.setAttribute("role", "listitem");
        btn.setAttribute("translate", "no");

        const main = document.createElement("span");
        main.className = "prev-chip-main";
        main.textContent = advisoryMetaLine(d);

        const meta = document.createElement("span");
        meta.className = "prev-chip-meta";
        const rel = formatRelativeTime(entry.savedAt);
        meta.textContent = rel ? `Saved ${rel}` : "";

        btn.append(main, meta);
        list.appendChild(btn);
    });

    previousSectionData = normalizeStoredPrediction(entriesToShow[0].data);
    populatePreviousSection(entriesToShow[0].data);
}

function populatePreviousSection(data) {
    if (!data) return;
    const d = normalizeStoredPrediction(data);
    previousSectionData = d;
    const fin = d?.financials?.financial_summary || {};
    const be  = d?.financials?.breakeven || {};
    const wt  = d?.live_weather || {};

    // Summary strip (previous)
    const elYield = document.getElementById("prev-strip-yield");
    if (elYield) elYield.textContent = `${d.predicted_yield ?? "—"} t/ha`;
    const elRange = document.getElementById("prev-strip-yield-range");
    if (elRange) elRange.textContent = `${d.min_yield ?? "—"} – ${d.max_yield ?? "—"} t/ha`;
    setColoredValue("prev-strip-profit", fin.expected_net_profit_inr ?? 0, true, true);

    const elRoi = document.getElementById("prev-strip-roi");
    if (elRoi) {
        const roi = fin.expected_roi_percent;
        elRoi.textContent = roi != null ? `${roi}%` : "—";
        elRoi.style.color = (roi ?? 0) >= 0 ? "var(--success)" : "var(--danger)";
    }
    const elTemp = document.getElementById("prev-strip-temp");
    if (elTemp) elTemp.textContent = `${wt.current_temp ?? "—"}°C`;
    const elConf = document.getElementById("prev-strip-confidence");
    if (elConf) elConf.textContent = d.confidence ?? "—";

    // Card previews (previous)
    const pYield = document.getElementById("prev-preview-yield");
    if (pYield) pYield.textContent = `${d.predicted_yield ?? "—"} t/ha`;
    const pYieldRange = document.getElementById("prev-preview-yield-range");
    if (pYieldRange) pYieldRange.textContent = `Range: ${d.min_yield ?? "—"} – ${d.max_yield ?? "—"} t/ha`;

    const pProfit = document.getElementById("prev-preview-profit");
    if (pProfit) pProfit.textContent = formatINR(fin.expected_net_profit_inr);
    const pCost = document.getElementById("prev-preview-cost");
    if (pCost) pCost.textContent = formatINR(fin.total_cost_inr);
    const pWeather = document.getElementById("prev-preview-weather");
    if (pWeather) pWeather.textContent = `${wt.current_temp ?? "—"}°C`;
    const pBe = document.getElementById("prev-preview-breakeven");
    if (pBe) pBe.textContent = `${be.breakeven_yield_per_ha ?? "—"} t/ha`;
    const pScenario = document.getElementById("prev-preview-scenario");
    if (pScenario) pScenario.textContent = "3 Scenarios";
}

function applyHistoryEntry(data) {
    const d = normalizeStoredPrediction(data);
    lastData = d;
    const json = JSON.stringify(d);
    try {
        sessionStorage.setItem(STORAGE_KEY, json);
    } catch { /* ignore */ }
    try {
        localStorage.setItem(STORAGE_KEY, json);
    } catch { /* ignore */ }

    const emptyState = document.getElementById("dashboard-empty-state");
    const dash = document.getElementById("dashboard-section");
    if (emptyState) emptyState.style.display = "none";
    if (dash) dash.style.display = "block";

    populateAll(d);
    showDashboard(d);
    renderPrevAdvisories(historyFingerprint(d));
    window.scrollTo({ top: 0, behavior: "smooth" });
}

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
        initPrevAdvisorySection();
        tryLoadDashboardFromStorage();
    }

    window.addEventListener("click", e => {
        if (e.target.classList.contains("modal-overlay")) e.target.classList.remove("active");
    });
});

// ── NAVBAR SCROLL EFFECT & DROPDOWN MENU ────────────────
function initNavbar() {
    // Scroll effect (throttled via rAF)
    let scrollTicking = false;
    window.addEventListener("scroll", () => {
        if (!scrollTicking) {
            scrollTicking = true;
            requestAnimationFrame(() => {
                const nb = document.getElementById("navbar");
                if (nb) nb.classList.toggle("scrolled", window.scrollY > 20);
                scrollTicking = false;
            });
        }
    }, { passive: true });

    // ── Dropdown toggle (click) ──────────────────────────
    const menuDropdown = document.getElementById("menu-dropdown");
    const menuBtn      = document.getElementById("mobile-menu-btn");
    const dropPanel    = document.getElementById("dropdown-panel");

    if (menuBtn && menuDropdown) {
        menuBtn.addEventListener("click", (e) => {
            e.stopPropagation();
            const isOpen = menuDropdown.classList.toggle("open");
            menuBtn.setAttribute("aria-expanded", isOpen);
        });
    }
    // Close when clicking outside
    document.addEventListener("click", (e) => {
        if (menuDropdown && !menuDropdown.contains(e.target)) {
            menuDropdown.classList.remove("open");
            menuBtn && menuBtn.setAttribute("aria-expanded", "false");
        }
    });

    // ── About Us modal ───────────────────────────────────
    const aboutBtn = document.getElementById("dp-about-btn");
    if (aboutBtn) {
        aboutBtn.addEventListener("click", () => {
            menuDropdown && menuDropdown.classList.remove("open");
            openModal("about-modal");
        });
    }

    // ── Active link highlight ────────────────────────────
    const path = (window.location.pathname || "/").toLowerCase();
    const navHome      = document.getElementById("nav-home");
    const navAdvisory  = document.getElementById("nav-advisory");
    const navDashboard = document.getElementById("nav-dashboard");
    const navCrops     = document.getElementById("nav-crops");
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
        populate("crop",      opts.Crop ?? opts.crop);   // API uses capital 'C'
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
        // Do NOT show badge on error — it would be misleading
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
        lastData = normalizeStoredPrediction(data);
        persistPrediction(lastData);
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
    if (btnText) btnText.innerHTML = on
        ? '<i class="ph-duotone ph-spinner-gap" style="vertical-align:middle;font-size:18px;"></i> Analyzing…'
        : '<i class="ph-bold ph-lightning" style="vertical-align:middle;font-size:18px;"></i> Run AI Prediction';
}

function tryLoadDashboardFromStorage() {
    let raw = null;
    try {
        raw = sessionStorage.getItem(STORAGE_KEY);
    } catch { /* ignore */ }
    if (!raw) {
        try {
            raw = localStorage.getItem(STORAGE_KEY);
        } catch { /* ignore */ }
    }
    if (!raw) {
        const hist = loadHistory();
        if (hist.length && hist[0].data) {
            try {
                raw = JSON.stringify(hist[0].data);
            } catch { /* ignore */ }
        }
    }
    if (!raw) {
        const dash = document.getElementById("dashboard-section");
        const emptyState = document.getElementById("dashboard-empty-state");
        if (dash) dash.style.display = "none";
        if (emptyState) emptyState.style.display = "block";
        renderPrevAdvisories();
        return;
    }
    try {
        const data = JSON.parse(raw);
        const d = normalizeStoredPrediction(data);
        lastData = d;
        populateAll(d);
        showDashboard(d);
        renderPrevAdvisories(historyFingerprint(d));
    } catch {
        const dash = document.getElementById("dashboard-section");
        const emptyState = document.getElementById("dashboard-empty-state");
        if (dash) dash.style.display = "none";
        if (emptyState) emptyState.style.display = "block";
        renderPrevAdvisories();
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
    let subtitleText = `${crop} · ${dist} · ${data.season} · ${data.area_ha} ha`;
    if (data.area_ha === null || data.area_ha === undefined) {
        subtitleText = `${crop} · ${dist} · ${data.season}`;
    }
    if (subtitle) subtitle.textContent = subtitleText;
}

// ── POPULATE ALL SECTIONS ─────────────────────────────────
function populateAll(data) {
    const d = normalizeStoredPrediction(data);
    populateDashboardStripAndPreviews(d);
    populateModalsFromData(d);
}

/** Summary strip + main dashboard card previews only (does not touch modals). */
function populateDashboardStripAndPreviews(data) {
    const fin = data.financials.financial_summary;
    const be  = data.financials.breakeven;
    const wt  = data.live_weather;

    document.getElementById("strip-yield").textContent      = `${data.predicted_yield} t/ha`;
    const stripRange = document.getElementById("strip-yield-range");
    if (stripRange) stripRange.textContent = `${data.min_yield} – ${data.max_yield} t/ha`;
    setColoredValue("strip-profit", fin.expected_net_profit_inr, true, true);
    document.getElementById("strip-roi").textContent        = `${fin.expected_roi_percent}%`;
    document.getElementById("strip-roi").style.color        = fin.expected_roi_percent >= 0 ? "var(--success)" : "var(--danger)";
    document.getElementById("strip-temp").textContent       = `${wt.current_temp ?? "—"}°C`;
    document.getElementById("strip-confidence").textContent = data.confidence;

    document.getElementById("preview-yield").textContent    = `${data.predicted_yield} t/ha`;
    const prevRange = document.getElementById("preview-yield-range");
    if (prevRange) prevRange.textContent = `Range: ${data.min_yield} – ${data.max_yield} t/ha`;
    document.getElementById("preview-profit").textContent   = formatINR(fin.expected_net_profit_inr);
    document.getElementById("preview-cost").textContent     = formatINR(fin.total_cost_inr);
    document.getElementById("preview-weather").textContent  = `${wt.current_temp ?? "—"}°C`;
    document.getElementById("preview-breakeven").textContent= `${be.breakeven_yield_per_ha} t/ha`;
}

/** All modal bodies + charts (used for current data and when opening a previous-advisory card). */
function populateModalsFromData(data) {
    const d = normalizeStoredPrediction(data);
    if (!d?.financials) return;

    const fin = d.financials.financial_summary;
    const be  = d.financials.breakeven;
    const sc  = d.financials.scenarios;
    const cd  = d.financials.cost_breakdown;
    const wt  = d.live_weather || {};

    document.getElementById("yield-meta").textContent =
        `${d.crop} · ${d.district} · ${d.season}`;
    document.getElementById("res-yield").textContent    = `${d.predicted_yield}`;
    document.getElementById("res-min-yield").textContent= `${d.min_yield}`;
    document.getElementById("res-max-yield").textContent= `${d.max_yield}`;
    document.getElementById("res-total-yield").textContent = `${d.total_predicted} t`;
    document.getElementById("res-total-range").textContent = `${d.total_min} – ${d.total_max} tonnes`;
    document.getElementById("res-category").textContent = d.yield_category;
    document.getElementById("res-confidence").textContent = d.confidence;
    setYieldGauge(d.min_yield, d.predicted_yield, d.max_yield);
    document.getElementById("yield-insight").textContent =
        `Predicted ${d.predicted_yield} t/ha is classified as ${d.yield_category} for ${d.crop} in Gujarat. ` +
        `The 80% confidence interval spans ${d.min_yield}–${d.max_yield} t/ha.`;

    const mspStr = fin.market_price_per_tonne_inr != null
        ? fin.market_price_per_tonne_inr.toLocaleString("en-IN")
        : "—";
    document.getElementById("fin-meta").textContent =
        `${d.crop} · ${d.area_ha} ha · Market price ₹${mspStr}/tonne`;
    document.getElementById("res-cost").textContent    = formatINR(fin.total_cost_inr);
    document.getElementById("res-revenue").textContent = formatINR(fin.expected_gross_revenue_inr);
    setColoredValue("res-profit", fin.expected_net_profit_inr, true);
    setColoredValue("res-roi",    fin.expected_roi_percent, false, false, "%");
    document.getElementById("res-msp").textContent     =
        fin.market_price_per_tonne_inr != null ? `₹${fin.market_price_per_tonne_inr.toLocaleString("en-IN")}` : "₹—";
    document.getElementById("res-cost-ha").textContent =
        fin.cost_per_ha_inr != null ? `₹${fin.cost_per_ha_inr.toLocaleString("en-IN")}` : "₹—";
    document.getElementById("fin-insight").textContent =
        `Based on ${d.crop} MSP/APMC rates (₹${mspStr}/tonne) and CACP cultivation costs for Gujarat.`;
    const alert = document.getElementById("breakeven-alert");
    if (alert) alert.style.display = fin.breakeven_risk_alert ? "block" : "none";

    fillScenario("pess", sc?.pessimistic);
    fillScenario("exp",  sc?.expected);
    fillScenario("opt",  sc?.optimistic);
    renderScenarioChart(sc);

    document.getElementById("res-district").textContent   = d.district;
    document.getElementById("w-temp-big").textContent     = `${wt.current_temp ?? "—"}°C`;
    document.getElementById("w-min-temp").textContent     = `${wt.min_temp ?? "—"}°C`;
    document.getElementById("w-max-temp").textContent     = `${wt.max_temp ?? "—"}°C`;
    document.getElementById("w-hum").textContent          = `${wt.humidity_avg ?? "—"}%`;
    document.getElementById("w-rain").textContent         = `${wt.current_rain_mm ?? 0} mm/h`;

    document.getElementById("cost-meta").textContent =
        `Total: ${formatINR(fin.total_cost_inr)} for ${d.area_ha} ha of ${d.crop}`;
    renderCostTable(cd, fin.total_cost_inr);
    renderCostChart(cd);

    document.getElementById("res-breakeven-yield").textContent = `${be.breakeven_yield_per_ha} t/ha`;
    document.getElementById("res-pred-yield-be").textContent   = `${d.predicted_yield} t/ha`;
    document.getElementById("res-margin").textContent          = `${be.margin_above_breakeven_tha} t/ha`;
    document.getElementById("res-breakeven-prod").textContent  = `${be.breakeven_production_t} tonnes`;
    renderBeBar(be.breakeven_yield_per_ha, d.predicted_yield, d.max_yield);
    const risk = be.breakeven_risk;
    document.getElementById("be-insight-text").textContent = risk
        ? "\u26a0\ufe0f Your predicted yield is dangerously close to the breakeven threshold. Consider reducing input costs or boosting irrigation."
        : `\u2705 Your predicted yield (${d.predicted_yield} t/ha) is ${be.margin_above_breakeven_tha} t/ha above the breakeven point. You are in the profit zone.`;
    document.getElementById("be-box-risk").className = "data-box " + (risk ? "highlight-red" : "highlight-green");

    populateReportModal(d);
}

/** Click chips + previous cards: open modals for the selected stored advisory. */
function initPrevAdvisorySection() {
    const section = document.getElementById("prev-advisory-section");
    if (!section || section.dataset.prevInit === "1") return;
    section.dataset.prevInit = "1";

    section.addEventListener("click", (e) => {
        const chip = e.target.closest(".prev-search-chip[data-prev-idx]");
        if (chip) {
            const idx = parseInt(chip.getAttribute("data-prev-idx"), 10);
            const entry = previousAdvisoryOptions[idx];
            if (entry?.data) {
                previousSectionData = normalizeStoredPrediction(entry.data);
                populatePreviousSection(entry.data);
                section.querySelectorAll(".prev-search-chip").forEach(c => c.classList.remove("is-active"));
                chip.classList.add("is-active");
            }
            return;
        }

        const card = e.target.closest(".prev-card[data-advisory-modal]");
        if (card && previousSectionData) {
            const mid = card.getAttribute("data-advisory-modal");
            if (mid) openAdvisoryModal(mid, previousSectionData);
        }
    });
}

// ── FULL REPORT MODAL POPULATION ─────────────────────────
function populateReportModal(data) {
    if (!data) return;
    const d = normalizeStoredPrediction(data);

    const fin = d?.financials?.financial_summary || {};
    const be  = d?.financials?.breakeven        || {};
    const sc  = d?.financials?.scenarios        || {};
    const cd  = d?.financials?.cost_breakdown   || {};
    const wt  = d?.live_weather                 || {};
    const area = parseFloat(d.area_ha) || 1;

    // Meta header (must match advisory list chips — advisoryMetaLine)
    setText('report-meta', advisoryMetaLine(d));

    // ─ Yield ────────────────────────────────────────────────
const minY  = d.min_yield        ?? '—';
    const predY = d.predicted_yield  ?? '—';
    const maxY  = d.max_yield        ?? '—';
    setText('rpt-min-yield',  `${minY} t/ha`);
    setText('rpt-pred-yield', `${predY} t/ha`);
    setText('rpt-max-yield',  `${maxY} t/ha`);
    const minTot  = (typeof minY  === 'number') ? (minY  * area).toFixed(2) : '—';
    const predTot = d.total_predicted ?? ((typeof predY === 'number') ? (predY * area).toFixed(2) : '—');
    const maxTot  = (typeof maxY  === 'number') ? (maxY  * area).toFixed(2) : '—';
    setText('rpt-min-total',  `${minTot} tonnes total`);
    setText('rpt-pred-total', `${predTot} tonnes total`);
    setText('rpt-max-total',  `${maxTot} tonnes total`);
    setText('rpt-yield-cat',  d.yield_category  || '—');
    setText('rpt-confidence', d.confidence      || '—');
    const totalMin = d.total_min ?? minTot;
    const totalMax = d.total_max ?? maxTot;
    setText('rpt-prod-range', `${totalMin} – ${totalMax} t`);

    // ─ Financials ───────────────────────────────────────────
    setText('rpt-cost',    formatINR(fin.total_cost_inr));
    setText('rpt-revenue', formatINR(fin.expected_gross_revenue_inr));
    if (fin.market_price_per_tonne_inr != null)
        setText('rpt-msp', `₹${fin.market_price_per_tonne_inr.toLocaleString('en-IN')}`);
    if (fin.cost_per_ha_inr != null)
        setText('rpt-cost-ha', `₹${fin.cost_per_ha_inr.toLocaleString('en-IN')}`);
    if (fin.expected_net_profit_inr != null) setColoredValue('rpt-profit', fin.expected_net_profit_inr, true);
    if (fin.expected_roi_percent    != null) setColoredValue('rpt-roi',    fin.expected_roi_percent, false, false, '%');

    // ─ Scenarios ────────────────────────────────────────────
    const fillRptSc = (key, s) => {
        if (!s) return;
        setText(`rpt-sc-${key}`,     formatINR(s.net_profit_inr));
        setText(`rpt-sc-${key}-roi`, `ROI: ${s.roi_percent ?? '—'}%`);
    };
    fillRptSc('pess', sc.pessimistic);
    fillRptSc('exp',  sc.expected);
    fillRptSc('opt',  sc.optimistic);

    // ─ Cost breakdown table ───────────────────────────────
    const ct = document.getElementById('rpt-cost-table');
    if (ct) {
        if (cd && Object.keys(cd).length) {
            const max = Math.max(...Object.values(cd));
            ct.innerHTML = Object.entries(cd).map(([label, amount]) => {
                const pct = Math.round((amount / max) * 100);
                return `<div class="cost-row">
                <span class="cost-row-label">${label}</span>
                <div class="cost-row-bar"><div class="cost-row-fill" style="width:${pct}%"></div></div>
                <span class="cost-row-amount">₹${amount.toLocaleString('en-IN', {maximumFractionDigits:0})}</span>
            </div>`;
            }).join('');
        } else {
            ct.innerHTML = "";
        }
    }

    // ─ Breakeven ────────────────────────────────────────────
    setText('rpt-be-yield',  be.breakeven_yield_per_ha    ? `${be.breakeven_yield_per_ha} t/ha`    : '—');
    setText('rpt-be-pred',   d.predicted_yield          ? `${d.predicted_yield} t/ha`         : '—');
    setText('rpt-be-margin', be.margin_above_breakeven_tha ? `${be.margin_above_breakeven_tha} t/ha` : '—');
    const beBox = document.getElementById('rpt-be-box');
    if (beBox) beBox.className = 'data-box ' + (be.breakeven_risk ? 'highlight-red' : 'highlight-green');

    // ─ Weather ───────────────────────────────────────────────
setText('rpt-district', d.district || '—');
    setText('rpt-temp', wt.current_temp  != null ? `${wt.current_temp}°C`   : '—');
    setText('rpt-hum',  wt.humidity_avg  != null ? `${wt.humidity_avg}%`    : '—');
    setText('rpt-rain', wt.current_rain_mm != null ? `${wt.current_rain_mm} mm/h` : '—');
}

function setText(id, val) {
    const el = document.getElementById(id);
    if (el) el.textContent = val;
}

// ── HELPERS ───────────────────────────────────────────────
function formatINR(v) {
    if (v == null) return "₹—";
    const abs = Math.abs(v).toLocaleString("en-IN", { maximumFractionDigits: 0 });
    return (v < 0 ? "−₹" : "₹") + abs;
}

function setColoredValue(id, val, rupee = false, large = false, suffix = "") {
    const el = document.getElementById(id);
    if (!el) return;
    const pos = val >= 0;
    el.textContent = (rupee ? (pos ? "₹" : "−₹") + Math.abs(val).toLocaleString("en-IN", { maximumFractionDigits: 0 }) : (pos ? "" : "−") + Math.abs(val)) + suffix;
    el.style.color = pos ? "var(--success)" : "var(--danger)";
}

function fillScenario(key, sc) {
    const a = document.getElementById(`sc-${key}-assumption`);
    const p = document.getElementById(`sc-${key}-profit`);
    const r = document.getElementById(`sc-${key}-roi`);
    if (!sc) {
        if (a) a.textContent = "—";
        if (p) p.textContent = formatINR(null);
        if (r) r.textContent = "ROI: —%";
        return;
    }
    if (a) a.textContent = sc.assumptions ?? "—";
    if (p) p.textContent = formatINR(sc.net_profit_inr);
    if (r) r.textContent = `ROI: ${sc.roi_percent ?? "—"}%`;
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
    if (!container) return;
    if (!breakdown || typeof breakdown !== "object" || !Object.keys(breakdown).length) {
        container.innerHTML = "";
        return;
    }
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
    const canvas = document.getElementById("scenarioChart");
    if (!canvas) return;
    if (!sc?.pessimistic || !sc?.expected || !sc?.optimistic) {
        if (scenarioChart) {
            scenarioChart.destroy();
            scenarioChart = null;
        }
        return;
    }
    const ctx = canvas.getContext("2d");
    if (scenarioChart) scenarioChart.destroy();

    const labels = ["Pessimistic", "Expected", "Optimistic"];
    const values = [
        sc.pessimistic.net_profit_inr ?? 0,
        sc.expected.net_profit_inr ?? 0,
        sc.optimistic.net_profit_inr ?? 0,
    ];
    const expVal = sc.expected.net_profit_inr ?? 0;
    const colors = values.map(v => v < 0 ? "rgba(239,83,80,0.75)" : v === expVal ? "rgba(232,160,32,0.75)" : "rgba(76,175,120,0.75)");
    const borders= values.map(v => v < 0 ? "#ef5350" : v === expVal ? "#e8a020" : "#4caf78");

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
    const canvas = document.getElementById("costChart");
    if (!canvas) return;
    if (!breakdown || typeof breakdown !== "object" || !Object.keys(breakdown).length) {
        if (costChart) {
            costChart.destroy();
            costChart = null;
        }
        return;
    }
    const ctx = canvas.getContext("2d");
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
/** Repopulate modal/chart DOM from a prediction object, then show the modal. Omit `data` to use the current dashboard run. */
function openAdvisoryModal(modalId, data) {
    const src = (arguments.length >= 2 && data != null) ? data : lastData;
    if (!src || !modalId) return;
    try {
        populateModalsFromData(src);
    } catch (err) {
        console.error(err);
        return;
    }
    document.getElementById(modalId)?.classList.add("active");
}

function openModal(id) {
    document.getElementById(id)?.classList.add("active");
}
function closeModal(id) { document.getElementById(id)?.classList.remove("active"); }
