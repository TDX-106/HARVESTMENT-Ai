# Harvestment — Technology Stack Documentation

> **Smart Crop Advisory System for Gujarat**  
> An AI-powered yield prediction and financial advisory platform for Gujarat farmers.

---

## 📐 System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        FRONTEND (Browser)                        │
│         HTML5 + Vanilla CSS + JavaScript + Chart.js              │
│              frontend/index.html · styles.css · app.js           │
└──────────────────────────┬──────────────────────────────────────┘
                           │  HTTP REST (JSON)
                           │  POST /predict · GET /options · GET /metrics
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                    BACKEND API LAYER                             │
│                   FastAPI + Uvicorn (Python)                     │
│                          api.py                                  │
│                                                                  │
│   ┌────────────────┐  ┌─────────────────┐  ┌────────────────┐   │
│   │  predictor.py  │  │ weather_service  │  │ financials.py  │   │
│   │  (ML inference)│  │  (OWM live API) │  │ (ROI/scenarios)│   │
│   └───────┬────────┘  └────────┬────────┘  └────────────────┘   │
│           │                    │                                  │
│   ┌───────▼────────────────────▼──────────────────────────────┐  │
│   │              saved_models/                                 │  │
│   │   rf_model.pkl · gbm_low.pkl · gbm_high.pkl               │  │
│   │   encoders.pkl · imputer.pkl · feature_meta.pkl           │  │
│   └────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                           │
              ┌────────────▼────────────┐
              │   External APIs          │
              │   OpenWeatherMap API     │
              └─────────────────────────┘
```

---

## 🔧 Backend Tech Stack

### Core Framework

| Technology | Version | Role | File(s) |
|---|---|---|---|
| **Python** | 3.10+ | Primary backend language | All `.py` files |
| **FastAPI** | ≥0.110.0 | REST API framework — auto-generates `/docs` (Swagger) | `api.py` |
| **Uvicorn** | ≥0.27.0 | ASGI server to run FastAPI | Launch command |
| **Pydantic v2** | ≥2.0.0 | Request validation & schema definition | `api.py` |

**Why FastAPI?** Auto-generates interactive API docs at `http://localhost:8000/docs`, async-ready, and Pydantic gives free request validation with clear error messages.

---

### Machine Learning Stack

| Technology | Version | Role | File(s) |
|---|---|---|---|
| **scikit-learn** | ≥1.3.0 | `HistGradientBoostingRegressor` for quantile bounds, `SimpleImputer`, `LabelEncoder`, metrics | `train.py`, `predictor.py` |
| **NumPy** | ≥1.24.0 | Array operations, log/exp transforms, clipping | `train.py`, `predictor.py` |
| **Pandas** | ≥2.0.0 | Data loading, cleaning, feature engineering | `train.py` |
| **joblib** | ≥1.3.0 | Model serialization (`.pkl` files) — save/load | `train.py`, `predictor.py` |

#### Models Trained

| Model File | Algorithm | Purpose |
|---|---|---|
| `rf_model.pkl` | `HistGradientBoostingRegressor` (500 iter, lr=0.05) | **Central yield prediction** (t/ha) |
| `gbm_low.pkl` | `HistGradientBoostingRegressor` (quantile α=0.10) | **Lower bound** — 10th percentile yield |
| `gbm_high.pkl` | `HistGradientBoostingRegressor` (quantile α=0.90) | **Upper bound** — 90th percentile yield |

**Training technique:** Target is log-transformed (`log1p`) before training and inverse-transformed (`expm1`) at inference, which handles the extreme yield variance across crops (Sugarcane ~65 t/ha vs Guar ~0.69 t/ha).

#### Features Used by the Model

| Feature | Type | Source |
|---|---|---|
| `district` | Categorical | User input (Label Encoded) |
| `Crop` | Categorical | User input (Label Encoded) |
| `Season` | Categorical | User input (Label Encoded) |
| `soil_type` | Categorical | User input (Label Encoded) |
| `Area` | Numerical | User input (hectares) |
| `min_temp_avg` | Numerical | Live weather + historical blend |
| `max_temp_avg` | Numerical | Live weather + historical blend |
| `total_rain` | Numerical | Historical seasonal estimate |
| `humidity_avg` | Numerical | Live weather + historical blend |
| `yearly_min_temp_avg` | Numerical | Historical yearly average |
| `yearly_max_temp_avg` | Numerical | Historical yearly average |
| `yearly_total_rain` | Numerical | Historical yearly total |
| `yearly_humidity_avg` | Numerical | Historical yearly average |
| `soil_fertility_score` | Numerical | User input (1–10 scale) |
| `irrigation_score` | Numerical | User input (0–1 fraction) |

---

### Data & Financial Layer

| Technology | Role | File(s) |
|---|---|---|
| **financials.py** | Custom module: computes cost, revenue, ROI, breakeven, 3-scenario planning | `financials.py` |
| **CACP Cost Data** | Baseline crop costs per hectare (INR) — Commission for Agricultural Costs & Prices | `financials.py` → `DEFAULT_COSTS` |
| **Gujarat APMC / MSP Prices** | Market price per tonne (INR) — Agricultural Produce Market Committee & Minimum Support Price | `financials.py` → `DEFAULT_PRICES` |

**Crops covered (28 total):** Arhar/Tur, Bajra, Banana, Castor seed, Cotton(lint), Dry chillies, Garlic, Gram, Groundnut, Guar seed, Jowar, Maize, Moong, Moth, Onion, Potato, Ragi, Rapeseed & Mustard, Rice, Sesamum, Small millets, Soyabean, Sugarcane, Tobacco, Urad, Wheat, and generic Rabi/Kharif pulse categories.

---

### Weather Integration

| Technology | Role | File(s) |
|---|---|---|
| **OpenWeatherMap API** | Live temperature, humidity, rainfall for Gujarat districts | `weather_service.py` |
| **`requests`** | HTTP client for OWM API calls | `weather_service.py` |

**How it works:** Live weather (current snapshot) is fetched for the selected district. Since the model needs seasonal/yearly averages, the live reading is blended with historical Gujarat baselines using a weighted deviation formula. This gives plausible seasonal inputs while incorporating real-time conditions.

---

### Artifact Storage

| File | Contents |
|---|---|
| `saved_models/rf_model.pkl` | Central yield prediction model |
| `saved_models/gbm_low.pkl` | 10th percentile (min yield) model |
| `saved_models/gbm_high.pkl` | 90th percentile (max yield) model |
| `saved_models/encoders.pkl` | `LabelEncoder` per categorical column |
| `saved_models/imputer.pkl` | `SimpleImputer` (median strategy) |
| `saved_models/feature_meta.pkl` | Column name lists + `log_transform` flag |
| `saved_models/training_report.txt` | Metrics: MAE, RMSE, R², quantile coverage |
| `final_merged_crop_weather_soil_irrigation_data.csv` | Training dataset (Gujarat historical data) |

---

## 🎨 Frontend Tech Stack

| Technology | Version/Source | Role | File(s) |
|---|---|---|---|
| **HTML5** | — | Page structure, semantic layout | `frontend/index.html` |
| **Vanilla CSS** | — | Styling — glassmorphism cards, animations, responsive grid | `frontend/styles.css` |
| **Vanilla JavaScript** | ES2020+ | API calls (`fetch`), DOM updates, modal logic | `frontend/app.js` |
| **Chart.js** | CDN (latest) | Bar chart for scenario profit visualization | `frontend/app.js` |
| **Google Fonts** | CDN | Typography — *Outfit* font family | `frontend/index.html` |

**Why no framework?** The UI is a single-page advisory tool. Plain HTML/CSS/JS keeps load time < 1 second, zero build step, and opens directly from the filesystem without a dev server.

---

## 🌐 API Endpoints Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Server liveness check |
| `GET` | `/options` | Valid values for all dropdowns (from encoder classes) |
| `GET` | `/metrics` | Model accuracy metrics from training report |
| `POST` | `/predict` | Full prediction pipeline (yield + weather + financials) |
| `GET` | `/docs` | Auto-generated Swagger UI (FastAPI) |
| `GET` | `/redoc` | ReDoc API documentation |

---

## 📦 Python Dependencies (`requirements.txt`)

```
scikit-learn>=1.3.0   # ML models, preprocessing, metrics
pandas>=2.0.0         # Data loading and manipulation
numpy>=1.24.0         # Numerical operations
joblib>=1.3.0         # Model serialization
fastapi>=0.110.0      # REST API framework
uvicorn>=0.27.0       # ASGI server
pydantic>=2.0.0       # Request/response validation
requests>=2.31.0      # HTTP client (OpenWeatherMap API)
```

---

## 🚀 How to Run

### Step 1 — Install Dependencies
```powershell
cd "C:\Users\tds36\Downloads\HARVESTMENT MODEL"
pip install -r requirements.txt
```

### Step 2 — Train Models
```powershell
python train.py --data final_merged_crop_weather_soil_irrigation_data.csv
```
Expected output: `R² > 0.90`, models saved to `saved_models/`.

### Step 3 — Start Backend API
```powershell
uvicorn api:app --reload --port 8000
```
API is live at `http://localhost:8000`  
Swagger docs at `http://localhost:8000/docs`

### Step 4 — Open Frontend
Open `frontend/index.html` directly in any browser (Chrome/Edge/Firefox).  
No additional server needed — the frontend calls the backend API directly.

---

## 📁 Project File Structure

```
HARVESTMENT MODEL/
│
├── 📄 api.py                          # FastAPI backend (main entry point)
├── 📄 predictor.py                    # ML inference class (YieldPredictor)
├── 📄 train.py                        # Model training script
├── 📄 financials.py                   # Financial advisory calculations
├── 📄 weather_service.py              # OpenWeatherMap live weather integration
├── 📄 requirements.txt                # Python dependencies
├── 📄 TECH_STACK.md                   # ← This document
│
├── 📂 saved_models/                   # Trained model artifacts
│   ├── rf_model.pkl                   # Central prediction model
│   ├── gbm_low.pkl                    # Min yield (10th percentile)
│   ├── gbm_high.pkl                   # Max yield (90th percentile)
│   ├── encoders.pkl                   # Label encoders
│   ├── imputer.pkl                    # Missing value imputer
│   ├── feature_meta.pkl               # Feature column metadata
│   └── training_report.txt            # Accuracy metrics
│
├── 📂 frontend/                       # Static web UI
│   ├── index.html                     # Main page
│   ├── styles.css                     # All styling
│   ├── app.js                         # API integration & interactivity
│   └── bg.png                         # Hero background image
│
└── 📄 final_merged_crop_weather_      # Training dataset (Gujarat)
    soil_irrigation_data.csv
```

---

## 🔒 Security Notes

- The OpenWeatherMap API key in `weather_service.py` is hardcoded for development. Before production deployment, move it to an environment variable:
  ```python
  import os
  API_KEY = os.environ.get("OWM_API_KEY", "your_fallback_key")
  ```
- CORS is set to `allow_origins=["*"]` for development. Restrict to your domain before deploying publicly.

---

*Last updated: April 2026 | Gujarat Smart Crop Advisory System v2.0*
