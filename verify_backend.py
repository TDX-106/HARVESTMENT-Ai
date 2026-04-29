"""
verify_backend.py
-----------------
Tests all Harvestment API endpoints and prints a pass/fail summary.
Run with: python verify_backend.py
"""

import urllib.request
import json
import sys

BASE = "http://localhost:8000"
PASS = []
FAIL = []

def get(path):
    r = urllib.request.urlopen(BASE + path, timeout=8)
    return json.loads(r.read())

def post(path, payload):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        BASE + path, data=data,
        headers={"Content-Type": "application/json"}, method="POST"
    )
    r = urllib.request.urlopen(req, timeout=10)
    return json.loads(r.read())

def check(name, fn):
    try:
        result = fn()
        print(f"  [PASS] {name}")
        PASS.append(name)
        return result
    except Exception as e:
        print(f"  [FAIL] {name}  -->  {e}")
        FAIL.append(name)
        return None

print()
print("=" * 55)
print("  HARVESTMENT BACKEND VERIFICATION")
print("=" * 55)

# ── 1. Health ──────────────────────────────────────────────
print("\n[1] GET /health")
h = check("Server liveness", lambda: get("/health"))
if h:
    print(f"       status={h['status']}  version={h['api_version']}")

# ── 2. Metrics ─────────────────────────────────────────────
print("\n[2] GET /metrics")
m = check("Model accuracy metrics", lambda: get("/metrics"))
if m:
    print(f"       Model  : {m['model']}")
    print(f"       R2     : {m['r2_score']}   (target > 0.90)")
    print(f"       MAE    : {m['mae_tonnes_ha']} t/ha")
    print(f"       RMSE   : {m['rmse_tonnes_ha']} t/ha")
    print(f"       QI Cov : {m['quantile_coverage_pct']}%")
    if m['r2_score'] and m['r2_score'] >= 0.90:
        print("       Model accuracy: EXCELLENT (R2 >= 0.90)")
    else:
        print("       WARNING: R2 below 0.90 — consider retraining")

# ── 3. Options ─────────────────────────────────────────────
print("\n[3] GET /options")
o = check("Dropdown options (JSON-safe)", lambda: get("/options"))
if o:
    for col, vals in o.items():
        print(f"       {col:12s}: {len(vals)} values  -> {vals[:4]}")

# ── 4. Predict ─────────────────────────────────────────────
print("\n[4] POST /predict  (Groundnut, Amreli, Kharif, 10 ha)")
payload = {
    "district": "Amreli", "crop": "Groundnut", "season": "Kharif",
    "area": 10.0, "soil_type": "Black",
    "soil_fertility_score": 5.0, "irrigation_score": 0.6
}
p = check("Full prediction pipeline", lambda: post("/predict", payload))
if p:
    fin = p["financials"]["financial_summary"]
    be  = p["financials"]["breakeven"]
    sc  = p["financials"]["scenarios"]
    print(f"       Yield      : {p['predicted_yield']} t/ha  [{p['min_yield']} – {p['max_yield']}]")
    print(f"       Category   : {p['yield_category']}   Confidence: {p['confidence']}")
    print(f"       Net Profit : INR {fin['expected_net_profit_inr']:,.0f}")
    print(f"       ROI        : {fin['expected_roi_percent']}%")
    print(f"       Breakeven  : {be['breakeven_yield_per_ha']} t/ha  (margin: {be['margin_above_breakeven_tha']} t/ha)")
    print(f"       Optimistic : INR {sc['optimistic']['net_profit_inr']:,.0f}")
    print(f"       Pessimistic: INR {sc['pessimistic']['net_profit_inr']:,.0f}")
    wt = p.get("live_weather", {})
    print(f"       Live Temp  : {wt.get('current_temp')}°C   Humidity: {wt.get('humidity_avg')}%")

# ── Summary ────────────────────────────────────────────────
print()
print("=" * 55)
total = len(PASS) + len(FAIL)
print(f"  RESULT: {len(PASS)}/{total} checks passed")
if FAIL:
    print(f"  FAILED: {', '.join(FAIL)}")
else:
    print("  All backend endpoints are working correctly.")
print("=" * 55)
print()

sys.exit(0 if not FAIL else 1)
