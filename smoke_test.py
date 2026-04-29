import urllib.request, json

payload = json.dumps({
    "district": "Amreli",
    "crop": "Groundnut",
    "season": "Kharif",
    "area": 10.0,
    "soil_type": "Black",
    "soil_fertility_score": 5.0,
    "irrigation_score": 0.6
}).encode()

req = urllib.request.Request(
    "http://localhost:8000/predict",
    data=payload,
    headers={"Content-Type": "application/json"},
    method="POST"
)

r = urllib.request.urlopen(req)
data = json.loads(r.read())

print("=== YIELD PREDICTION ===")
print(f"  Predicted yield : {data['predicted_yield']} t/ha")
print(f"  Min yield       : {data['min_yield']} t/ha")
print(f"  Max yield       : {data['max_yield']} t/ha")
print(f"  Category        : {data['yield_category']}")
print(f"  Confidence      : {data['confidence']}")

fin = data["financials"]["financial_summary"]
print("\n=== FINANCIALS ===")
print(f"  Total Cost      : INR {fin['total_cost_inr']:,}")
print(f"  Gross Revenue   : INR {fin['expected_gross_revenue_inr']:,}")
print(f"  Net Profit      : INR {fin['expected_net_profit_inr']:,}")
print(f"  ROI             : {fin['expected_roi_percent']}%")
print(f"  Breakeven Risk  : {fin['breakeven_risk_alert']}")

print("\n=== SCENARIOS ===")
for name, sc in data["financials"]["scenarios"].items():
    print(f"  {name}: profit = INR {sc['net_profit_inr']:,}  ROI={sc['roi_percent']}%")

print("\n=== LIVE WEATHER ===")
wt = data["live_weather"]
print(f"  Temp: {wt.get('current_temp')}C  Humidity: {wt.get('humidity_avg')}%")

print("\nFULL END-TO-END TEST PASSED")
