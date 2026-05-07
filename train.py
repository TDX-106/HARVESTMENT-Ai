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

from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
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

    # Fill numerical nulls with median PER CROP (much more accurate than global median)
    for col in ["soil_fertility_score", "irrigation_score"]:
        if col in df.columns:
            df[col] = df.groupby("Crop")[col].transform(
                lambda x: x.fillna(x.median())
            )
            # Fall back to global median for any remaining nulls
            df[col].fillna(df[col].median(), inplace=True)

    # Fill Production nulls
    if "Production" in df.columns:
        df["Production"].fillna(df["Production"].median(), inplace=True)

    # Remove rows with zero/negative yield (data entry errors)
    df = df[df[TARGET] > 0].copy()

    removed = original_rows - len(df)
    print(f"  Loaded  : {original_rows:,} rows")
    print(f"  Removed : {removed} zero-yield rows")
    print(f"  Clean   : {len(df):,} rows")
    print(f"  Crops   : {df['Crop'].nunique()} | Districts: {df['district'].nunique()}")
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
    Train three models:
      1. RandomForestRegressor (central prediction) — tuned with per-crop
         sample weighting to handle scale imbalance across crops.
      2. GradientBoostingRegressor (10th percentile lower bound)
      3. GradientBoostingRegressor (90th percentile upper bound)
    Uses log1p(yield) to handle large scale variance across crops.
    Predictions are converted back with expm1() at inference time.
    """
    from sklearn.ensemble import ExtraTreesRegressor

    print("\n  [1/3] Fitting imputer ...")
    imputer = SimpleImputer(strategy="median")
    X_train_imp = imputer.fit_transform(X_train)

    # Log-transform the target to normalise scale
    y_log = np.log1p(y_train)

    # Per-crop sample weighting: give more weight to crops with fewer rows
    # so the RF doesn't bias toward high-density crops (e.g. Groundnut)
    crop_col = X_train_imp[:, 1]  # Crop is index 1 in CATEGORICAL_COLS
    unique_crops, counts = np.unique(crop_col, return_counts=True)
    freq_map = dict(zip(unique_crops, counts))
    max_count = max(counts)
    sample_weights = np.array([max_count / freq_map[c] for c in crop_col])
    sample_weights = np.sqrt(sample_weights)  # Soften the weighting

    print("  [2/3] Training RandomForest (with crop-weighted sampling) ...")
    rf = RandomForestRegressor(
        n_estimators=600,
        max_depth=None,
        min_samples_split=3,
        min_samples_leaf=1,
        max_features=0.6,
        n_jobs=-1,
        random_state=42,
        oob_score=True,
    )
    rf.fit(X_train_imp, y_log, sample_weight=sample_weights)
    print(f"     RF OOB R2 (log scale): {rf.oob_score_:.4f}")

    print("  [3/3] Training GradientBoosting quantile models on log(yield) ...")
    gbm_low = GradientBoostingRegressor(
        loss="quantile",
        alpha=LOWER_ALPHA,
        n_estimators=500,
        learning_rate=0.04,
        max_depth=6,
        min_samples_leaf=3,
        subsample=0.8,
        random_state=42,
    )
    gbm_high = GradientBoostingRegressor(
        loss="quantile",
        alpha=UPPER_ALPHA,
        n_estimators=500,
        learning_rate=0.04,
        max_depth=6,
        min_samples_leaf=3,
        subsample=0.8,
        random_state=42,
    )
    gbm_low.fit(X_train_imp, y_log)
    gbm_high.fit(X_train_imp, y_log)

    return rf, gbm_low, gbm_high, imputer


# ─────────────────────────────────────────────────────────────────────────────
# 4. EVALUATION
# ─────────────────────────────────────────────────────────────────────────────

def evaluate(
    rf, gbm_low, gbm_high, imputer,
    X_test: np.ndarray, y_test: np.ndarray,
    df_test: pd.DataFrame = None,
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

    # Per-crop MAE
    per_crop_mae = {}
    if df_test is not None:
        tmp = df_test.copy()
        tmp["pred"] = y_pred
        tmp["err"]  = np.abs(y_pred - y_test)
        for crop, g in tmp.groupby("Crop"):
            per_crop_mae[crop] = round(float(g["err"].mean()), 3)

    metrics = {
        "MAE":        round(mae, 4),
        "RMSE":       round(rmse, 4),
        "R2":         round(r2, 4),
        "Coverage":   round(coverage, 4),
        "Avg_width":  round(avg_width, 4),
        "per_crop_mae": per_crop_mae,
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
        f.write(f"R²   : {metrics['R2']}\n\n")
        f.write("QUANTILE INTERVAL [10th – 90th percentile]\n")
        f.write(f"  Coverage  : {metrics['Coverage']*100:.1f}% actual yields inside band\n")
        f.write(f"  Avg width : {metrics['Avg_width']} tonnes/ha\n")
        if metrics.get('per_crop_mae'):
            f.write("\nPER-CROP MAE (t/ha):\n")
            for crop, mae in sorted(metrics['per_crop_mae'].items()):
                f.write(f"  {crop:<30} {mae}\n")

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
    # Stratify by Crop so every crop is proportionally represented in test set
    # For crops with very few rows, fall back to ungrouped split
    try:
        X_train, X_test, y_train, y_test, idx_train, idx_test = train_test_split(
            X, y, df.index, test_size=0.2, random_state=42, stratify=df["Crop"]
        )
        print("  Stratified split by Crop ✓")
    except ValueError:
        X_train, X_test, y_train, y_test, idx_train, idx_test = train_test_split(
            X, y, df.index, test_size=0.2, random_state=42
        )
        print("  Random split (stratify not possible) ✓")
    print(f"  Train: {len(X_train)} rows  |  Test: {len(X_test)} rows")

    print("\n══ STEP 4: Train Models ══════════════════════════════")
    rf, gbm_low, gbm_high, imputer = train_models(X_train, y_train)

    print("\n══ STEP 5: Evaluate ══════════════════════════════════")
    df_test = df.loc[idx_test].copy()
    metrics = evaluate(rf, gbm_low, gbm_high, imputer, X_test, y_test, df_test)
    print(f"  HistGradientBoosting  → MAE: {metrics['MAE']}  RMSE: {metrics['RMSE']}  R²: {metrics['R2']}")
    print(f"  Quantile band → Coverage: {metrics['Coverage']*100:.1f}%  Avg width: {metrics['Avg_width']} t/ha")

    print("\n══ STEP 6: Save ══════════════════════════════════════")
    save_artifacts(rf, gbm_low, gbm_high, imputer, encoders, metrics)

    print("\n✅ Training complete!\n")


if __name__ == "__main__":
    main()
