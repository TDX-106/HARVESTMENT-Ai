"""
financials.py  –  Gujarat Crop Financial Advisory Layer
=========================================================
Computes revenue, profit, ROI, breakeven yield, and scenario planning
for all 28 Gujarat crops modeled by the yield prediction engine.

Data sources:
  - Costs: Based on CACP (Commission for Agricultural Costs & Prices) &
    Gujarat Agriculture Dept cost-of-cultivation reports (INR/ha).
  - Prices: Based on MSP + prevailing Gujarat APMC mandi rates (INR/tonne).
"""

from typing import Dict, Any

# ─────────────────────────────────────────────────────────────────────────────
# BASELINE COSTS PER HECTARE (INR)
# Includes: seed, fertilizer, pesticides, labor, irrigation, machinery, land rent
# ─────────────────────────────────────────────────────────────────────────────

DEFAULT_COSTS: Dict[str, float] = {
    "Arhar/Tur":            35000,   # Pigeonpea – moderate input crop
    "Bajra":                22000,   # Pearl millet – low input, rain-fed
    "Banana":              120000,   # High-value horticultural, intensive inputs
    "Castor seed":          28000,   # Low water, low fertilizer crop
    "Cotton(lint)":         58000,   # High input: pesticides, irrigated
    "Dry chillies":         55000,   # Labour-intensive, high pesticide use
    "Garlic":               75000,   # Very labour-intensive
    "Gram":                 28000,   # Chickpea – winter crop, low input
    "Groundnut":            45000,   # Key Gujarat crop, moderate input
    "Guar seed":            20000,   # Drought-tolerant, very low input
    "Jowar":                22000,   # Sorghum – low input, mixed use
    "Maize":                32000,   # Moderate input, irrigated
    "Moong(Green Gram)":    25000,   # Short-duration pulse
    "Moth":                 18000,   # Very drought-tolerant, minimal input
    "Onion":                65000,   # High labour, storage, transport costs
    "Other  Rabi pulses":   25000,   # Generic Rabi pulse baseline
    "Other Cereals":        24000,   # Generic cereal baseline
    "Other Kharif pulses":  23000,   # Generic Kharif pulse baseline
    "Potato":               80000,   # High input: seed cost is major
    "Ragi":                 20000,   # Finger millet – low input
    "Rapeseed &Mustard":    30000,   # Winter oilseed – moderate input
    "Rice":                 42000,   # Transplanted paddy – high water + labour
    "Sesamum":              22000,   # Sesame – drought-tolerant, low input
    "Small millets":        18000,   # Very low input traditional crop
    "Soyabean":             28000,   # Moderate input oilseed
    "Sugarcane":            95000,   # Very high input: ratoon management
    "Tobacco":              60000,   # High input, curing costs included
    "Urad":                 24000,   # Black gram – short-duration
    "Wheat":                36000,   # Winter cereal – irrigated, moderate input
    # Fallback
    "default":              35000,
}

# ─────────────────────────────────────────────────────────────────────────────
# MARKET PRICES PER TONNE (INR)
# Based on MSP + Gujarat APMC mandi prevailing rates
# ─────────────────────────────────────────────────────────────────────────────

DEFAULT_PRICES: Dict[str, float] = {
    "Arhar/Tur":            70000,   # MSP ~₹7,000/quintal = ₹70,000/tonne
    "Bajra":                23150,   # MSP ₹2,315/quintal
    "Banana":                20000,  # ₹20/kg average farmgate price
    "Castor seed":           65000,  # Gujarat mandi: ₹6,000–7,000/quintal
    "Cotton(lint)":          75000,  # MSP ₹7,020/quintal (long staple)
    "Dry chillies":         150000,  # ₹15,000/quintal – highly variable
    "Garlic":                60000,  # ₹6,000/quintal farmgate average
    "Gram":                  54000,  # MSP ₹5,440/quintal
    "Groundnut":             60000,  # MSP ₹6,377/quintal (pod basis)
    "Guar seed":             45000,  # ₹4,500/quintal Gujarat mandi
    "Jowar":                 33000,  # MSP ₹3,371/quintal (hybrid)
    "Maize":                 22500,  # MSP ₹2,090/quintal + premium
    "Moong(Green Gram)":     86000,  # MSP ₹8,682/quintal
    "Moth":                  58000,  # ₹5,800/quintal
    "Onion":                 15000,  # ₹15/kg – very volatile, using average
    "Other  Rabi pulses":    55000,  # Generic Rabi pulse price
    "Other Cereals":         22000,  # Generic cereal price
    "Other Kharif pulses":   50000,  # Generic Kharif pulse price
    "Potato":                15000,  # ₹15/kg average farmgate
    "Ragi":                  39000,  # MSP ₹3,846/quintal
    "Rapeseed &Mustard":     55000,  # MSP ₹5,650/quintal
    "Rice":                  23000,  # MSP ₹2,300/quintal (common grade)
    "Sesamum":               90000,  # MSP ₹9,267/quintal
    "Small millets":         35000,  # ₹3,500/quintal average
    "Soyabean":              46000,  # MSP ₹4,600/quintal (Yellow)
    "Sugarcane":              3500,  # SAP ₹315–350/quintal → ₹3,500/tonne
    "Tobacco":               70000,  # FCV tobacco: ₹7,000/quintal
    "Urad":                  70000,  # MSP ₹7,000/quintal
    "Wheat":                 25000,  # MSP ₹2,275/quintal
    # Fallback
    "default":               30000,
}

# ─────────────────────────────────────────────────────────────────────────────
# COST BREAKDOWN SHARES (for UI pie chart / table display)
# Approximate percentage of total cost per category
# ─────────────────────────────────────────────────────────────────────────────

COST_BREAKDOWN_TEMPLATE = {
    "Seed & Planting":    0.18,
    "Fertilizers":        0.22,
    "Pesticides":         0.15,
    "Labour":             0.25,
    "Irrigation":         0.10,
    "Machinery & Misc":   0.10,
}


def get_cost_breakdown(total_cost: float) -> Dict[str, float]:
    """Return itemized cost breakdown in INR."""
    return {
        category: round(total_cost * share, 2)
        for category, share in COST_BREAKDOWN_TEMPLATE.items()
    }


# ─────────────────────────────────────────────────────────────────────────────
# MAIN FINANCIAL CALCULATION
# ─────────────────────────────────────────────────────────────────────────────

def calculate_financials(
    crop: str,
    area_ha: float,
    pred_yield: float,
    min_yield: float,
    max_yield: float,
) -> Dict[str, Any]:
    """
    Calculate revenue, profit, ROI, breakeven, and scenario planning.

    Parameters
    ----------
    crop        : Crop name (must match keys in DEFAULT_COSTS/PRICES)
    area_ha     : Cultivated area in hectares
    pred_yield  : Central predicted yield (t/ha)
    min_yield   : Lower bound yield (t/ha)  – 10th percentile
    max_yield   : Upper bound yield (t/ha)  – 90th percentile

    Returns
    -------
    dict with:
        financial_summary  – Core profit/cost/ROI metrics
        breakeven          – Breakeven analysis
        scenarios          – Optimistic / Expected / Pessimistic
        cost_breakdown     – Itemized cost table
    """

    # ── 1. Base values ─────────────────────────────────────────────────────
    cost_per_ha      = DEFAULT_COSTS.get(crop, DEFAULT_COSTS["default"])
    price_per_tonne  = DEFAULT_PRICES.get(crop, DEFAULT_PRICES["default"])

    total_cost       = cost_per_ha * area_ha
    expected_prod    = pred_yield * area_ha           # total tonnes
    gross_revenue    = expected_prod * price_per_tonne
    net_profit       = gross_revenue - total_cost
    roi_percent      = (net_profit / total_cost * 100) if total_cost > 0 else 0.0

    # ── 2. Breakeven ───────────────────────────────────────────────────────
    breakeven_prod_tonnes = total_cost / price_per_tonne
    breakeven_yield_ha    = breakeven_prod_tonnes / area_ha if area_ha > 0 else 0.0
    # Risk flag: predicted yield within 10% of breakeven or below
    breakeven_risk        = pred_yield <= (breakeven_yield_ha * 1.10)

    # ── 3. Scenarios ───────────────────────────────────────────────────────
    def _scenario(yield_ha: float, price_multiplier: float) -> Dict[str, float]:
        prod      = yield_ha * area_ha
        revenue   = prod * price_per_tonne * price_multiplier
        profit    = revenue - total_cost
        roi       = (profit / total_cost * 100) if total_cost > 0 else 0.0
        return {
            "yield_ha":      round(yield_ha, 3),
            "production_t":  round(prod, 2),
            "revenue_inr":   round(revenue, 2),
            "net_profit_inr": round(profit, 2),
            "roi_percent":   round(roi, 2),
        }

    optimistic  = _scenario(max_yield, 1.10)   # max yield + 10% price
    expected    = _scenario(pred_yield, 1.00)  # predicted yield, market price
    pessimistic = _scenario(min_yield,  0.90)  # min yield − 10% price

    # Add assumptions labels for UI display
    optimistic["assumptions"]  = "Max yield + 10% price premium"
    expected["assumptions"]    = "Predicted yield at current market price"
    pessimistic["assumptions"] = "Min yield + 10% price discount"

    # ── 4. Cost breakdown ──────────────────────────────────────────────────
    breakdown = get_cost_breakdown(total_cost)

    return {
        "financial_summary": {
            "crop":                       crop,
            "area_ha":                    round(area_ha, 2),
            "cost_per_ha_inr":            round(cost_per_ha, 2),
            "total_cost_inr":             round(total_cost, 2),
            "market_price_per_tonne_inr": round(price_per_tonne, 2),
            "expected_production_tonnes": round(expected_prod, 2),
            "expected_gross_revenue_inr": round(gross_revenue, 2),
            "expected_net_profit_inr":    round(net_profit, 2),
            "expected_roi_percent":       round(roi_percent, 2),
            "breakeven_risk_alert":       breakeven_risk,
        },
        "breakeven": {
            "breakeven_yield_per_ha":     round(breakeven_yield_ha, 3),
            "breakeven_production_t":     round(breakeven_prod_tonnes, 2),
            "breakeven_risk":             breakeven_risk,
            "margin_above_breakeven_tha": round(pred_yield - breakeven_yield_ha, 3),
        },
        "scenarios": {
            "optimistic":  optimistic,
            "expected":    expected,
            "pessimistic": pessimistic,
        },
        "cost_breakdown": breakdown,
    }
