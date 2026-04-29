# Gujarat Crop Yield Prediction Model

## Project Structure

```
yield_model/
│
├── train.py            ← Step 1: Train all models on your dataset
├── predictor.py        ← Step 2: Load models + predict (import this in your app)
├── api.py              ← Step 3: FastAPI backend (serves predictions over HTTP)
├── test_predict.py     ← Smoke test to verify everything works
├── requirements.txt
│
└── saved_models/       ← Auto-created by train.py
    ├── rf_model.pkl        Main prediction model (RandomForest)
    ├── gbm_low.pkl         Min yield model (10th percentile quantile GBM)
    ├── gbm_high.pkl        Max yield model (90th percentile quantile GBM)
    ├── encoders.pkl        LabelEncoders for district / crop / season / soil_type
    ├── imputer.pkl         SimpleImputer for missing values
    ├── feature_meta.pkl    Column lists + log_transform flag
    └── training_report.txt Model performance metrics
```

---

## Setup

```bash
pip install -r requirements.txt
```

---

## Step 1 — Train

```bash
python train.py --data path/to/final_merged_crop_weather_soil_irrigation_data.csv
```

Expected output:
```
RandomForest  → MAE: 0.79  RMSE: 3.03  R²: 0.94
Quantile band → Coverage: 72%  Avg width: 5.67 t/ha
```

**Why log transform?**
Your dataset has crops ranging from ~0.4 t/ha (Moth) to ~77 t/ha (Banana).
Without log transform, the model focuses on high-yield crops and ignores
low-yield ones. `log1p(yield)` compresses the scale so all crops are
weighted equally during training.

---

## Step 2 — Predict (Python)

```python
from predictor import YieldPredictor

model = YieldPredictor(model_dir="saved_models")

result = model.predict(
    district             = "Amreli",
    crop                 = "Groundnut",
    season               = "Kharif",
    area                 = 100.0,           # hectares
    min_temp             = 24.97,           # °C
    max_temp             = 31.5,
    total_rain           = 465.5,           # mm
    humidity_avg         = 77.3,            # %
    yearly_min_temp      = 21.5,
    yearly_max_temp      = 32.9,
    yearly_total_rain    = 534.4,
    yearly_humidity_avg  = 56.7,
    soil_type            = "Black",
    soil_fertility_score = 4.0,             # 1–10
    irrigation_score     = 0.6,             # 0–1
)

print(result)
# {
#   'predicted_yield': 1.471,   ← tonnes/hectare (central estimate)
#   'min_yield':       1.211,   ← 10th percentile
#   'max_yield':       1.996,   ← 90th percentile
#   'total_predicted': 147.09,  ← total tonnes for 100 ha
#   'total_min':       121.1,
#   'total_max':       199.61,
#   'yield_category':  'Low',
#   'confidence':      'Medium'
# }
```

---

## Step 3 — Run API

```bash
uvicorn api:app --reload --port 8000
```

### POST /predict

```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{
    "district": "Amreli",
    "crop": "Groundnut",
    "season": "Kharif",
    "area": 100,
    "min_temp": 24.97,
    "max_temp": 31.5,
    "total_rain": 465.5,
    "humidity_avg": 77.3,
    "yearly_min_temp": 21.5,
    "yearly_max_temp": 32.9,
    "yearly_total_rain": 534.4,
    "yearly_humidity_avg": 56.7,
    "soil_type": "Black",
    "soil_fertility_score": 4.0,
    "irrigation_score": 0.6
  }'
```

### GET /options

Returns valid dropdown values for district, crop, season, soil_type.
Use this to populate your frontend form automatically.

### API Docs (Swagger UI)

```
http://localhost:8000/docs
```

---

## Output Fields Reference

| Field              | Unit       | Description                                   |
|--------------------|------------|-----------------------------------------------|
| `predicted_yield`  | t/ha       | Central yield estimate (RandomForest)         |
| `min_yield`        | t/ha       | Lower bound — 10th percentile (GBM quantile)  |
| `max_yield`        | t/ha       | Upper bound — 90th percentile (GBM quantile)  |
| `total_predicted`  | tonnes     | `predicted_yield × area`                      |
| `total_min`        | tonnes     | `min_yield × area`                            |
| `total_max`        | tonnes     | `max_yield × area`                            |
| `yield_category`   | —          | Low / Medium / High vs crop historical avg    |
| `confidence`       | —          | High / Medium / Low based on band width       |

---

## Model Performance (on your dataset)

| Metric       | Value          |
|--------------|----------------|
| R²           | 0.94           |
| MAE          | 0.80 t/ha      |
| RMSE         | 3.03 t/ha      |
| Band coverage| 72% of actuals |
| Training rows| 2,544          |
| Test rows    | 636            |
| Crops        | 29             |
| Districts    | 32             |
| Years        | 2016–2019      |

---

## Frontend Integration

From your React/HTML form, call the API like this:

```javascript
const response = await fetch("http://localhost:8000/predict", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(formData)
});
const result = await response.json();

// result.predicted_yield  → show as main number
// result.min_yield        → show as range lower bound
// result.max_yield        → show as range upper bound
// result.yield_category   → show as badge (Low/Medium/High)
```

To populate dropdowns on page load:

```javascript
const options = await fetch("http://localhost:8000/options").then(r => r.json());
// options.district → array of all 32 districts
// options.Crop     → array of all 29 crops
// options.Season   → ['Kharif', 'Rabi', 'Other']
// options.soil_type → ['Black', 'Alluvial', 'Red', 'Desert', 'Laterite']
```
