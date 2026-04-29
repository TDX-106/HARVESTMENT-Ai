"""
test_predict.py  –  Quick smoke test for the yield prediction pipeline
=======================================================================
Run AFTER training:
    python train.py --data path/to/data.csv
    python test_predict.py
"""

import json
from predictor import YieldPredictor


def separator(title: str):
    print(f"\n{'─'*50}")
    print(f"  {title}")
    print('─'*50)


def main():
    model = YieldPredictor(model_dir="saved_models")

    # ── Show available options ─────────────────────────────────────────────
    separator("Available dropdown options")
    opts = model.available_options()
    for key, values in opts.items():
        print(f"  {key}: {values[:5]}{'...' if len(values) > 5 else ''}")

    # ── Single predictions ─────────────────────────────────────────────────
    test_cases = [
        {
            "label": "Groundnut – Amreli – Kharif",
            "params": dict(
                district="Amreli", crop="Groundnut", season="Kharif",
                area=100.0, min_temp=24.97, max_temp=31.5,
                total_rain=465.5, humidity_avg=77.3,
                yearly_min_temp=21.5, yearly_max_temp=32.9,
                yearly_total_rain=534.4, yearly_humidity_avg=56.7,
                soil_type="Black", soil_fertility_score=4.0, irrigation_score=0.6,
            ),
        },
        {
            "label": "Wheat – Anand – Rabi",
            "params": dict(
                district="Anand", crop="Wheat", season="Rabi",
                area=50.0, min_temp=15.0, max_temp=28.0,
                total_rain=80.0, humidity_avg=60.0,
                yearly_min_temp=20.0, yearly_max_temp=33.0,
                yearly_total_rain=600.0, yearly_humidity_avg=55.0,
                soil_type="Alluvial", soil_fertility_score=5.0, irrigation_score=0.8,
            ),
        },
        {
            "label": "Sugarcane – Surat – Kharif",
            "params": dict(
                district="Surat", crop="Sugarcane", season="Kharif",
                area=25.0, min_temp=25.0, max_temp=34.0,
                total_rain=700.0, humidity_avg=80.0,
                yearly_min_temp=22.0, yearly_max_temp=35.0,
                yearly_total_rain=900.0, yearly_humidity_avg=72.0,
                soil_type="Alluvial", soil_fertility_score=6.0, irrigation_score=0.9,
            ),
        },
    ]

    separator("Predictions")
    for tc in test_cases:
        r = model.predict(**tc["params"])
        print(f"\n  ▸ {tc['label']}")
        print(f"    Predicted yield : {r['predicted_yield']} t/ha")
        print(f"    Min yield       : {r['min_yield']} t/ha  (10th percentile)")
        print(f"    Max yield       : {r['max_yield']} t/ha  (90th percentile)")
        print(f"    Total production: {r['total_predicted']} t  [{r['total_min']} – {r['total_max']} t]")
        print(f"    Category        : {r['yield_category']}  |  Confidence: {r['confidence']}")

    # ── Batch prediction ───────────────────────────────────────────────────
    separator("Batch prediction (2 records)")
    batch_results = model.predict_batch([tc["params"] for tc in test_cases[:2]])
    for res in batch_results:
        print(f"\n  {res['crop']} – {res['district']}")
        print(f"    {res['min_yield']} ≤ {res['predicted_yield']} ≤ {res['max_yield']} t/ha")

    print("\n✅ All tests passed.\n")


if __name__ == "__main__":
    main()
