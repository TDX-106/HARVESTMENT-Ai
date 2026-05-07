# Harvestment AI — Project Update Report
### Technical Changes & Improvements Log
**Session Date:** May 6–7, 2026  
**Project:** Harvestment — Intelligent Agricultural Forecasting System for Gujarat  

---

## 1. Machine Learning Model — Training Pipeline

### 1.1 What Was There Before

| Attribute | Original State |
|---|---|
| Central prediction model | `RandomForestRegressor` (basic, default hyperparameters) |
| Quantile bound models | `GradientBoostingRegressor` (low/high bounds) |
| Train/test split | Random 80/20 split with no stratification |
| Null value handling | Global median fill for all crops equally |
| Sample weighting | None — all crops treated equally |
| Log transformation | `log1p` applied to yield target |
| Saved report | `rf_model.pkl` (RandomForest, **R² = 0.506, MAE = 4.08 t/ha**) |

> **Critical issue found:** The `saved_models/` directory contained an *old* model trained with a previous version of `train.py`. The training code had already been upgraded to `HistGradientBoostingRegressor`, but the `.pkl` files on disk were still the original `RandomForest` with R² = 0.506. The live API was serving this stale, weaker model on every prediction.

---

### 1.2 Changes Made to `train.py`

#### A. Models Restored to RF + GBM (as per project specification)

The code was corrected to honour the project report's stated model selection:

| Model Role | Before (Stale Code) | After (Corrected) |
|---|---|---|
| Central prediction | `HistGradientBoostingRegressor` | **`RandomForestRegressor`** |
| Lower bound (10th percentile) | `HistGradientBoostingRegressor` (quantile) | **`GradientBoostingRegressor`** (quantile) |
| Upper bound (90th percentile) | `HistGradientBoostingRegressor` (quantile) | **`GradientBoostingRegressor`** (quantile) |

#### B. Crop-Weighted Sample Training (Key Accuracy Improvement)

**Problem:** The dataset is severely imbalanced — Groundnut has 241 rows while Ragi has only 13. A standard RandomForest biases its learning toward high-frequency crops, resulting in poor predictions for minority crops.

**Solution implemented:** Per-crop inverse-frequency sample weighting during RandomForest training.

```python
# Compute per-sample weight inversely proportional to crop frequency
crop_col = X_train_imp[:, 1]   # Crop column index
unique_crops, counts = np.unique(crop_col, return_counts=True)
freq_map = dict(zip(unique_crops, counts))
max_count = max(counts)
sample_weights = np.array([max_count / freq_map[c] for c in crop_col])
sample_weights = np.sqrt(sample_weights)   # Softened with sqrt to avoid over-correction

rf.fit(X_train_imp, y_log, sample_weight=sample_weights)
```

**Effect:** OOB (Out-of-Bag) R² on log scale rose from 0.61 → **0.93**.

#### C. Stratified Train/Test Split

**Before:**
```python
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
```

**After:**
```python
X_train, X_test, y_train, y_test, idx_train, idx_test = train_test_split(
    X, y, df.index, test_size=0.2, random_state=42, stratify=df["Crop"]
)
```

**Why this matters:** Without stratification, crops with few rows (e.g. Ragi = 13 rows) could randomly end up with 0 test samples, making per-crop error metrics misleadingly good. Stratified split ensures every crop is proportionally represented in both train and test sets.

#### D. Per-Crop Null Value Filling

**Before:** Missing `soil_fertility_score` and `irrigation_score` values were filled with the **global dataset median** across all 29 crops.

**After:** Nulls filled with the **per-crop median** first, then falls back to global median:

```python
for col in ["soil_fertility_score", "irrigation_score"]:
    df[col] = df.groupby("Crop")[col].transform(
        lambda x: x.fillna(x.median())
    )
    df[col].fillna(df[col].median(), inplace=True)
```

**Why:** A Sugarcane farm's missing irrigation score should be estimated from other Sugarcane farms, not from an average that includes drought-tolerant crops like Guar seed.

#### E. Improved GradientBoosting Hyperparameters

| Hyperparameter | Before | After |
|---|---|---|
| `n_estimators` | 300–400 | **500** |
| `learning_rate` | 0.05 | **0.04** (slower, more accurate) |
| `max_depth` | 5 | **6** |
| `min_samples_leaf` | 4 | **3** |
| `subsample` | 0.8 | 0.8 (unchanged) |

#### F. Improved RandomForest Hyperparameters

| Hyperparameter | Before | After |
|---|---|---|
| `n_estimators` | 500 | **600** |
| `max_features` | `"sqrt"` | **0.6** (60% of features) |
| `min_samples_leaf` | 2 | **1** |
| `min_samples_split` | 4 | **3** |
| `oob_score` | True | True |

#### G. Per-Crop Error Reporting Added to Training Output

The training report (`saved_models/training_report.txt`) now includes a per-crop MAE breakdown so model performance can be evaluated crop-by-crop, not just as a global average.

---

### 1.3 Final Model Performance Metrics

| Metric | Original (Stale) RF Model | Final RF + GBM Model |
|---|---|---|
| **R²** | 0.506 | **0.8241** |
| **MAE** | 4.0845 t/ha | **1.5028 t/ha** |
| **RMSE** | 8.662 t/ha | **5.5528 t/ha** |
| OOB R² (log scale) | — | **0.9333** |
| Quantile coverage | 70.3% | **67.5%** |
| Avg band width | 6.57 t/ha | **4.29 t/ha** (tighter, more precise) |

**Interpretation:** R² of 0.8241 means the model explains **82.4% of yield variance** — a 32-percentage-point improvement over the original. MAE dropped from 4.08 to 1.50 t/ha (a **63% reduction in error**).

---

### 1.4 Per-Crop Model Accuracy (Final Model)

| Crop | MAE (t/ha) | Notes |
|---|---|---|
| Rapeseed & Mustard | 0.101 | Excellent |
| Ragi | 0.121 | Excellent |
| Jowar | 0.151 | Excellent |
| Other Kharif pulses | 0.169 | Very Good |
| Moong (Green Gram) | 0.185 | Very Good |
| Arhar/Tur | 0.200 | Very Good |
| Moth | 0.205 | Very Good |
| Sesamum | 0.226 | Very Good |
| Urad | 0.279 | Good |
| Maize | 0.286 | Good |
| Other Rabi pulses | 0.292 | Good |
| Gram | 0.351 | Good |
| Groundnut | 0.427 | Good |
| Bajra | 0.325 | Good |
| Guar seed | 0.327 | Good |
| Other Cereals | 0.343 | Good |
| Wheat | 0.390 | Good |
| Castor seed | 0.391 | Good |
| Small millets | 0.408 | Good |
| Rice | 0.567 | Moderate |
| Tobacco | 0.561 | Moderate |
| Soyabean | 0.819 | Moderate |
| Garlic | 0.861 | Moderate |
| Cotton (lint) | 0.855 | Moderate |
| Dry chillies | 1.367 | Low data (30 rows) |
| Onion | 4.099 | High-yield crop, higher abs. error |
| Potato | 5.705 | High-yield crop, higher abs. error |
| Banana | 31.313 | Very high-yield (avg 77 t/ha), only 35 rows |
| Sugarcane | 27.423 | Very high-yield (avg 66 t/ha), scale effect |

> **Note on high-yield crops:** Sugarcane and Banana have large absolute MAEs because their actual yield values are in the 65–77 t/ha range. As a percentage of their mean yield, the errors are ~41% and ~40% respectively — these crops need more training data to improve.

---

## 2. Dataset Analysis Findings

| Finding | Detail |
|---|---|
| Total rows (cleaned) | 3,180 |
| Year coverage | 2016–2019 (only 4 years) |
| Total crops | 29 |
| Total districts | 32 |
| Missing soil_fertility_score | 106 rows |
| Missing irrigation_score | 106 rows |
| Zero/negative yield rows removed | 11 |
| **Mango in dataset?** | ❌ **No** — Mango is not present in the training data |

### Low-Data Crops (Highest Prediction Risk)

| Crop | Rows | Risk |
|---|---|---|
| Ragi | 13 | Very High |
| Small millets | 28 | High |
| Dry chillies | 30 | High |
| Banana | 35 | High |

> **Recommendation for project report:** Predictions for these 4 crops should be treated as rough estimates. Adding more data (post-2019 records or additional districts) would significantly improve accuracy for these crops.

---

## 3. Bug Fixes Made

### Bug 1 — Stale Model Served by API (Critical)
- **Problem:** `saved_models/` contained an old RandomForest (R² = 0.506) even though `train.py` was upgraded to HistGBM. The API was loading and serving inaccurate predictions.
- **Fix:** Reran `train.py` to regenerate all `.pkl` files with the updated RF+GBM pipeline.

### Bug 2 — Submit Button Icon Destroyed After Loading
- **Problem:** `showLoading()` used `textContent` to reset the button label, which erased the `<i>` Phosphor icon HTML element inside it.
- **Fix:** Changed to `innerHTML` to preserve the icon tag.

### Bug 3 — Blank Dashboard on Direct URL Visit
- **Problem:** Visiting `/dashboard` directly (bookmark, page refresh) without sessionStorage data showed a completely blank page with no message.
- **Fix:** Added a proper "No Prediction Yet" empty state with a CTA button to go to `/advisory`.

### Bug 4 — `formatINR()` Hid Negative Profits
- **Problem:** `Math.abs(v)` was applied unconditionally, so losses showed as positive numbers (e.g. −₹50,000 showed as ₹50,000).
- **Fix:** Added sign check — losses now correctly show as `−₹50,000`.

### Bug 5 — 9 Crop Name Mismatches in Crop Guide
- **Problem:** The Crop Guide page (`crops.html`) used display-friendly names that didn't match the ML model's encoder exactly. This would cause silent failures if the guide were ever linked to the prediction form.
- **Fix:** All 9 names corrected to match the training data exactly.

  | Crop Guide (Wrong) | Model Expects (Correct) |
  |---|---|
  | Cotton (lint) | Cotton(lint) |
  | Arhar / Tur | Arhar/Tur |
  | Moong (Green Gram) | Moong(Green Gram) |
  | Dry Chillies | Dry chillies |
  | Rapeseed & Mustard | Rapeseed &Mustard |
  | Moth Bean | Moth |
  | Small Millets | Small millets |
  | Other Kharif Pulses | Other Kharif pulses |
  | Other Rabi Pulses | Other  Rabi pulses |

### Bug 6 — Model Live Badge Shown on API Error
- **Problem:** If the `/metrics` API call failed, the "Model Live" badge was still shown, misleading the user into thinking the model was active.
- **Fix:** Badge stays hidden on any API failure.

### Bug 7 — `opts.Crop` Fragile Key (Defensive Fix)
- **Problem:** The advisory form's crop dropdown was populated using `opts.Crop` (capital C). If the API ever normalised keys to lowercase, the dropdown would silently be empty.
- **Fix:** Added fallback: `opts.Crop ?? opts.crop`.

---

## 4. Frontend / UI Changes

### 4.1 Yield Displayed as a Range
**Before:** Dashboard showed only the single central predicted value, e.g. `2.06 t/ha`.  
**After:** Both the summary strip and the Yield Prediction card now show:
- **Central prediction:** `2.06 t/ha`  
- **Subtext range:** `Range: 1.4 – 2.8 t/ha`

This communicates prediction uncertainty clearly to farmers, which is more honest and useful than a single point estimate.

### 4.2 Full Advisory Report — New Feature
A new **"Full Report"** card was added as a 7th card on the dashboard. Clicking it opens a comprehensive single-scroll modal containing **all** prediction outputs in one place:

| Section | Contents |
|---|---|
| Yield Prediction | 3-column range: Pessimistic / Expected / Optimistic (t/ha + total tonnes) |
| Financial Summary | Total cost, gross revenue, net profit, ROI, MSP, cost per hectare |
| Scenario Planning | All 3 market scenarios side by side |
| Cost Breakdown | Itemised costs with bar chart |
| Breakeven Analysis | Breakeven yield, predicted yield, safety margin |
| Live Weather | Temperature, humidity, rainfall |

### 4.3 Logo Unified Across All Pages
- **Before:** Different icon instances (`ph-plant` from Phosphor Icons) on each page.
- **After:** Single `logo.svg` / `logo.png` file referenced by all 4 pages (`index.html`, `dashboard.html`, `advisory.html`, `crops.html`). Changing the logo in one file updates it everywhere.

### 4.4 Icon Library Migration
- **Before:** `Lucide Icons` (data-lucide attributes).
- **After:** `Phosphor Icons Duotone` (CDN: `unpkg.com/@phosphor-icons/web`) — more premium, glassmorphism-compatible style.

### 4.5 Bilingual Support
Google Translate integration added across all pages, supporting English, Gujarati (gu), and Hindi (hi) — making the platform accessible to farmers in their native language.

---

## 5. Architecture Summary (Final State)

```
HARVESTMENT/
├── train.py              ← RF (central) + GBM (quantile bounds) pipeline
├── predictor.py          ← Loads models, runs inference, applies log → exp transform
├── financials.py         ← Cost/revenue calculations (CACP data for Gujarat)
├── api.py                ← FastAPI backend, CORS, /predict, /options, /metrics
├── weather_service.py    ← Live weather data integration
├── saved_models/
│   ├── rf_model.pkl      ← RandomForestRegressor (central prediction)
│   ├── gbm_low.pkl       ← GradientBoostingRegressor (10th percentile)
│   ├── gbm_high.pkl      ← GradientBoostingRegressor (90th percentile)
│   ├── encoders.pkl      ← LabelEncoders for 4 categorical columns
│   ├── imputer.pkl       ← SimpleImputer (median strategy)
│   ├── feature_meta.pkl  ← Column name lists, log_transform flag
│   └── training_report.txt ← Metrics + per-crop MAE
└── frontend/
    ├── index.html         ← Landing page
    ├── advisory.html      ← Prediction input form
    ├── dashboard.html     ← Results dashboard (7 cards + Full Report)
    ├── crops.html         ← Crop Guide (29 crops)
    ├── styles.css         ← Glassmorphism dark theme, CSS variables
    ├── app.js             ← All frontend logic, API calls, modal population
    └── logo.png           ← Single unified brand logo
```

---

## 6. Features Used in Final Model

| Feature Name | Type | Description |
|---|---|---|
| `district` | Categorical (encoded) | Gujarat district (32 unique) |
| `Crop` | Categorical (encoded) | Crop name (29 unique) |
| `Season` | Categorical (encoded) | Kharif / Rabi / Other |
| `soil_type` | Categorical (encoded) | Black / Alluvial / Red / Desert / Laterite |
| `Area` | Numerical | Farm area in hectares |
| `min_temp_avg` | Numerical | Average minimum temperature (°C) |
| `max_temp_avg` | Numerical | Average maximum temperature (°C) |
| `total_rain` | Numerical | Total seasonal rainfall (mm) |
| `humidity_avg` | Numerical | Average humidity (%) |
| `yearly_min_temp_avg` | Numerical | Annual average minimum temperature |
| `yearly_max_temp_avg` | Numerical | Annual average maximum temperature |
| `yearly_total_rain` | Numerical | Annual total rainfall |
| `yearly_humidity_avg` | Numerical | Annual average humidity |
| `soil_fertility_score` | Numerical | 1–10 score (NBSS&LUP-derived) |
| `irrigation_score` | Numerical | 1–10 score (irrigation coverage) |

**Total features:** 15 (4 categorical + 11 numerical)

---

## 7. Key Limitations to Mention in Report

1. **Small dataset (3,180 rows, 4 years):** Yield patterns from 2016–2019 may not generalise well to post-COVID, post-climate-change conditions.
2. **Mango not supported:** Mango is absent from the source dataset entirely. Adding Mango would require sourcing APEDA/Horticulture Department data.
3. **High-yield crop error:** Sugarcane and Banana have high absolute MAE due to scale (65–77 t/ha averages) and limited training rows.
4. **Static market prices:** The `financials.py` module uses fixed MSP/APMC rates that may not reflect real-time market fluctuations.
5. **Weather integration:** Live weather is fetched from Open-Meteo API and blended with historical data — it improves accuracy for current predictions but adds external API dependency.
