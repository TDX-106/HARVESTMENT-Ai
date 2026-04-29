"""
train.py  -- Gujarat Crop Yield Prediction Model
=================================================
Trains three models on your dataset:
  1. RandomForestRegressor       → central yield prediction
  2. GradientBoostingRegressor   → 10th percentile (min yield)
  3. GradientBoostingRegressor   → 90th percentile (max yield)

Usage:
    python train.py --data path/to/final_merged_crop_weather_soil_irrigation_data.csv

Outputs (saved to ./saved_models/):
    rf_model.pkl       – main prediction model
    gbm_low.pkl        – lower-bound quantile model
    gbm_high.pkl       – upper-bound quantile model
    encoders.pkl       – LabelEncoders for categorical columns
    imputer.pkl        – SimpleImputer for missing values
    feature_meta.pkl   – column name lists
    training_report.txt
"""

import argparse
import os
import warnings
import joblib
import numpy as np
import pandas as pd
warnings.filterwarnings("ignore")

from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor, HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import cross_val_score, train_test_split
from sklearn.preprocessing import LabelEncoder

# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────

SAVE_DIR = "saved_models"

CATEGORICAL_COLS = ["district", "Crop", "Season", "soil_type"]

NUMERICAL_COLS = [
    "Area",
    "min_temp_avg",
    "max_temp_avg",
    "total_rain",
    "humidity_avg",
    "yearly_min_temp_avg",
    "yearly_max_temp_avg",
    "yearly_total_rain",
    "yearly_humidity_avg",
    "soil_fertility_score",
    "irrigation_score",
]

TARGET = "Yield"

LOWER_ALPHA = 0.10   # 10th percentile → min yield
UPPER_ALPHA = 0.90   # 90th percentile → max yield


# ─────────────────────────────────────────────────────────────────────────────
# 1. DATA LOADING & CLEANING
# ─────────────────────────────────────────────────────────────────────────────

def load_and_clean(filepath: str) -> pd.DataFrame:
    """Load the CSV and apply standard cleaning steps."""
    df = pd.read_csv(filepath)
    original_rows = len(df)

    # Fill categorical nulls with mode
    for col in ["soil_type"]:
        if col in df.columns:
            df[col].fillna(df[col].mode()[0], inplace=True)

    # Fill numerical nulls with median
    for col in ["soil_fertility_score", "irrigation_score", "Production"]:
        if col in df.columns:
            df[col].fillna(df[col].median(), inplace=True)

    # Remove rows with zero/negative yield (data entry errors)
    df = df[df[TARGET] > 0].copy()

    removed = original_rows - len(df)
    print(f"  Loaded  : {original_rows:,} rows")
    print(f"  Removed : {removed} zero-yield rows")
    print(f"  Clean   : {len(df):,} rows")
    print(f"  Crops   : {df['Crop'].nunique()} | Districts: {df['district'].nunique()} | Years: {sorted(df['Year'].unique())}")
    return df


# ─────────────────────────────────────────────────────────────────────────────
# 2. ENCODING
# ─────────────────────────────────────────────────────────────────────────────

def encode_features(df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, dict]:
    """
    Label-encode categorical columns.
    Returns (X_array, y_array, encoders_dict).
    """
    df_enc = df.copy()
    encoders = {}

    for col in CATEGORICAL_COLS:
        le = LabelEncoder()
        df_enc[col] = le.fit_transform(df_enc[col].astype(str))
        encoders[col] = le

    X = df_enc[CATEGORICAL_COLS + NUMERICAL_COLS].values
    y = df_enc[TARGET].values
    return X, y, encoders


# ─────────────────────────────────────────────────────────────────────────────
# 3. TRAINING
# ─────────────────────────────────────────────────────────────────────────────

def train_models(X_train: np.ndarray, y_train: np.ndarray):
    """
    Train all three models and return them.
    Uses log1p(yield) to handle the large scale variance across crops
    (e.g. Sugarcane ~65 t/ha vs Guar ~0.69 t/ha).
    Predictions are converted back with expm1() at inference time.
    """
    print("\n  [1/3] Fitting imputer ...")
    imputer = SimpleImputer(strategy="median")
    X_train = imputer.fit_transform(X_train)

    # Log-transform the target
    y_log = np.log1p(y_train)

    print("  [2/3] Training HistGradientBoosting on log(yield) ...")
    rf = HistGradientBoostingRegressor(
        max_iter=500,
        learning_rate=0.05,
        random_state=42,
    )
    rf.fit(X_train, y_log)

    print("  [3/3] Training quantile HistGradientBoosting models on log(yield) ...")
    gbm_low = HistGradientBoostingRegressor(
        loss="quantile",
        quantile=LOWER_ALPHA,
        max_iter=300,
        learning_rate=0.05,
        random_state=42,
    )
    gbm_high = HistGradientBoostingRegressor(
        loss="quantile",
        quantile=UPPER_ALPHA,
        max_iter=300,
        learning_rate=0.05,
        random_state=42,
    )
    gbm_low.fit(X_train, y_log)
    gbm_high.fit(X_train, y_log)

    return rf, gbm_low, gbm_high, imputer


# ─────────────────────────────────────────────────────────────────────────────
# 4. EVALUATION
# ─────────────────────────────────────────────────────────────────────────────

def evaluate(
    rf, gbm_low, gbm_high, imputer,
    X_test: np.ndarray, y_test: np.ndarray,
) -> dict:
    """Return a dict of evaluation metrics."""
    X_test_imp = imputer.transform(X_test)

    # Reverse log1p transform
    y_pred  = np.expm1(rf.predict(X_test_imp))
    y_low   = np.expm1(gbm_low.predict(X_test_imp))
    y_high  = np.expm1(gbm_high.predict(X_test_imp))

    # Clamp negatives
    y_pred  = np.maximum(y_pred, 0)
    y_low   = np.maximum(y_low, 0)
    y_high  = np.maximum(y_high, 0)

    mae     = mean_absolute_error(y_test, y_pred)
    rmse    = mean_squared_error(y_test, y_pred) ** 0.5
    r2      = r2_score(y_test, y_pred)
    coverage = float(((y_test >= y_low) & (y_test <= y_high)).mean())
    avg_width = float((y_high - y_low).mean())

    metrics = {
        "MAE":        round(mae, 4),
        "RMSE":       round(rmse, 4),
        "R2":         round(r2, 4),
        "Coverage":   round(coverage, 4),   # % actual yields inside [min, max]
        "Avg_width":  round(avg_width, 4),  # average (max - min) band width t/ha
    }
    return metrics


# ─────────────────────────────────────────────────────────────────────────────
# 5. SAVE
# ─────────────────────────────────────────────────────────────────────────────

def save_artifacts(rf, gbm_low, gbm_high, imputer, encoders, metrics):
    os.makedirs(SAVE_DIR, exist_ok=True)

    joblib.dump(rf,       os.path.join(SAVE_DIR, "rf_model.pkl"))
    joblib.dump(gbm_low,  os.path.join(SAVE_DIR, "gbm_low.pkl"))
    joblib.dump(gbm_high, os.path.join(SAVE_DIR, "gbm_high.pkl"))
    joblib.dump(imputer,  os.path.join(SAVE_DIR, "imputer.pkl"))
    joblib.dump(encoders, os.path.join(SAVE_DIR, "encoders.pkl"))
    joblib.dump(
        {"categorical": CATEGORICAL_COLS, "numerical": NUMERICAL_COLS, "log_transform": True},
        os.path.join(SAVE_DIR, "feature_meta.pkl"),
    )

    report_path = os.path.join(SAVE_DIR, "training_report.txt")
    with open(report_path, "w") as f:
        f.write("Gujarat Crop Yield Model – Training Report\n")
        f.write("=" * 45 + "\n\n")
        f.write("MODEL: HistGradientBoosting (central prediction)\n")
        f.write(f"  MAE  : {metrics['MAE']} tonnes/ha\n")
        f.write(f"  RMSE : {metrics['RMSE']} tonnes/ha\n")
        f.write(f"  R²   : {metrics['R2']}\n\n")
        f.write("QUANTILE INTERVAL [10th – 90th percentile]\n")
        f.write(f"  Coverage  : {metrics['Coverage']*100:.1f}% actual yields inside band\n")
        f.write(f"  Avg width : {metrics['Avg_width']} tonnes/ha\n")

    print(f"\n  Artifacts saved to ./{SAVE_DIR}/")
    print(f"  Training report  : {report_path}")


# ─────────────────────────────────────────────────────────────────────────────
# 6. MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Train Gujarat Yield Prediction Models")
    parser.add_argument("--data", required=True, help="Path to the merged CSV dataset")
    args = parser.parse_args()

    print("\n══ STEP 1: Load & Clean ══════════════════════════════")
    df = load_and_clean(args.data)

    print("\n══ STEP 2: Encode Features ═══════════════════════════")
    X, y, encoders = encode_features(df)
    print(f"  Feature matrix: {X.shape[0]} rows × {X.shape[1]} columns")

    print("\n══ STEP 3: Train/Test Split ══════════════════════════")
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )
    print(f"  Train: {len(X_train)} rows  |  Test: {len(X_test)} rows")

    print("\n══ STEP 4: Train Models ══════════════════════════════")
    rf, gbm_low, gbm_high, imputer = train_models(X_train, y_train)

    print("\n══ STEP 5: Evaluate ══════════════════════════════════")
    metrics = evaluate(rf, gbm_low, gbm_high, imputer, X_test, y_test)
    print(f"  HistGradientBoosting  → MAE: {metrics['MAE']}  RMSE: {metrics['RMSE']}  R²: {metrics['R2']}")
    print(f"  Quantile band → Coverage: {metrics['Coverage']*100:.1f}%  Avg width: {metrics['Avg_width']} t/ha")

    print("\n══ STEP 6: Save ══════════════════════════════════════")
    save_artifacts(rf, gbm_low, gbm_high, imputer, encoders, metrics)

    print("\n✅ Training complete!\n")


if __name__ == "__main__":
    main()
