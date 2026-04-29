"""
predictor.py  –  Gujarat Crop Yield Predictor
==============================================
Loads the trained models and exposes a clean predict() function.

Output per prediction:
  predicted_yield  (float)  – central estimate in tonnes/hectare
  min_yield        (float)  – lower bound (10th percentile) in tonnes/hectare
  max_yield        (float)  – upper bound (90th percentile) in tonnes/hectare
  total_predicted  (float)  – predicted_yield × Area  (total tonnes)
  total_min        (float)  – min_yield × Area
  total_max        (float)  – max_yield × Area
  yield_category   (str)    – "Low" / "Medium" / "High" relative to crop average
  confidence       (str)    – "High" / "Medium" / "Low" based on band width

Usage:
    from predictor import YieldPredictor

    model = YieldPredictor(model_dir="saved_models")

    result = model.predict(
        district="Amreli",
        crop="Groundnut",
        season="Kharif",
        area=100.0,
        min_temp=24.5,
        max_temp=32.0,
        total_rain=480.0,
        humidity_avg=75.0,
        yearly_min_temp=22.0,
        yearly_max_temp=33.5,
        yearly_total_rain=550.0,
        yearly_humidity_avg=55.0,
        soil_type="Black",
        soil_fertility_score=4.0,
        irrigation_score=0.6,
    )

    print(result)
"""

import os
import warnings
import joblib
import numpy as np
warnings.filterwarnings("ignore")


# ─────────────────────────────────────────────────────────────────────────────
# Crop average yields (tonnes/ha) derived from dataset – used for category labels
# ─────────────────────────────────────────────────────────────────────────────

CROP_AVG_YIELD = {
    "Arhar/Tur":          1.20,
    "Bajra":              2.20,
    "Banana":            77.06,
    "Castor seed":        2.04,
    "Cotton(lint)":       3.32,
    "Dry chillies":       1.20,
    "Garlic":             6.39,
    "Gram":               1.26,
    "Groundnut":          2.06,
    "Guar seed":          0.69,
    "Jowar":              1.36,
    "Maize":              2.07,
    "Moong(Green Gram)":  0.74,
    "Moth":               0.41,
    "Onion":             27.60,
    "Other  Rabi pulses": 0.83,
    "Other Cereals":      0.94,
    "Other Kharif pulses":0.61,
    "Potato":            27.46,
    "Ragi":               0.90,
    "Rapeseed &Mustard":  1.77,
    "Rice":               2.33,
    "Sesamum":            0.59,
    "Small millets":      1.46,
    "Soyabean":           1.24,
    "Sugarcane":         65.69,
    "Tobacco":            2.43,
    "Urad":               0.84,
    "Wheat":              2.97,
}


class YieldPredictor:
    """
    Loads trained models and provides yield predictions with min/max range.
    """

    def __init__(self, model_dir: str = "saved_models"):
        self.model_dir = model_dir
        self._load_models()

    # ── Load ──────────────────────────────────────────────────────────────────

    def _load_models(self):
        def path(name):
            return os.path.join(self.model_dir, name)

        self.rf        = joblib.load(path("rf_model.pkl"))
        self.gbm_low   = joblib.load(path("gbm_low.pkl"))
        self.gbm_high  = joblib.load(path("gbm_high.pkl"))
        self.imputer   = joblib.load(path("imputer.pkl"))
        self.encoders  = joblib.load(path("encoders.pkl"))
        meta                  = joblib.load(path("feature_meta.pkl"))
        self.categorical_cols = meta["categorical"]
        self.numerical_cols   = meta["numerical"]
        self.log_transform    = meta.get("log_transform", True)

    # ── Encode ────────────────────────────────────────────────────────────────

    def _encode_input(self, raw: dict) -> np.ndarray:
        """
        Convert a raw input dict to a numpy row ready for model inference.
        Handles unseen labels gracefully by falling back to the most-frequent class.
        """
        row = []

        for col in self.categorical_cols:
            le = self.encoders[col]
            value = str(raw.get(col, ""))
            if value in le.classes_:
                row.append(le.transform([value])[0])
            else:
                # Unseen label → use index 0 (most stable fallback)
                row.append(0)

        for col in self.numerical_cols:
            row.append(float(raw.get(col, np.nan)))

        X = np.array(row, dtype=float).reshape(1, -1)
        X = self.imputer.transform(X)
        return X

    # ── Classify ──────────────────────────────────────────────────────────────

    @staticmethod
    def _yield_category(predicted: float, crop: str) -> str:
        """
        Compare predicted yield against the crop's historical average.
        Returns "Low" / "Medium" / "High".
        """
        avg = CROP_AVG_YIELD.get(crop, predicted)
        ratio = predicted / avg if avg > 0 else 1.0
        if ratio < 0.8:
            return "Low"
        elif ratio > 1.2:
            return "High"
        else:
            return "Medium"

    @staticmethod
    def _confidence_label(min_y: float, max_y: float, predicted: float) -> str:
        """
        Estimate confidence from the relative width of the prediction interval.
        """
        if predicted == 0:
            return "Low"
        width_ratio = (max_y - min_y) / predicted
        if width_ratio < 0.5:
            return "High"
        elif width_ratio < 1.5:
            return "Medium"
        else:
            return "Low"

    # ── Public API ────────────────────────────────────────────────────────────

    def predict(
        self,
        district: str,
        crop: str,
        season: str,
        area: float,
        min_temp: float,
        max_temp: float,
        total_rain: float,
        humidity_avg: float,
        yearly_min_temp: float,
        yearly_max_temp: float,
        yearly_total_rain: float,
        yearly_humidity_avg: float,
        soil_type: str,
        soil_fertility_score: float,
        irrigation_score: float,
    ) -> dict:
        """
        Predict crop yield with min/max range.

        Returns
        -------
        dict with keys:
            district, crop, season, area
            predicted_yield   (t/ha)
            min_yield         (t/ha)
            max_yield         (t/ha)
            total_predicted   (total tonnes = predicted × area)
            total_min         (total tonnes = min × area)
            total_max         (total tonnes = max × area)
            yield_category    "Low" / "Medium" / "High"
            confidence        "High" / "Medium" / "Low"
        """
        raw = {
            "district":             district,
            "Crop":                 crop,
            "Season":               season,
            "soil_type":            soil_type,
            "Area":                 area,
            "min_temp_avg":         min_temp,
            "max_temp_avg":         max_temp,
            "total_rain":           total_rain,
            "humidity_avg":         humidity_avg,
            "yearly_min_temp_avg":  yearly_min_temp,
            "yearly_max_temp_avg":  yearly_max_temp,
            "yearly_total_rain":    yearly_total_rain,
            "yearly_humidity_avg":  yearly_humidity_avg,
            "soil_fertility_score": soil_fertility_score,
            "irrigation_score":     irrigation_score,
        }

        X = self._encode_input(raw)
        log_transform = getattr(self, "log_transform", True)

        if log_transform:
            pred  = float(np.maximum(np.expm1(self.rf.predict(X)[0]), 0))
            low   = float(np.maximum(np.expm1(self.gbm_low.predict(X)[0]), 0))
            high  = float(np.maximum(np.expm1(self.gbm_high.predict(X)[0]), 0))
        else:
            pred  = float(np.maximum(self.rf.predict(X)[0], 0))
            low   = float(np.maximum(self.gbm_low.predict(X)[0], 0))
            high  = float(np.maximum(self.gbm_high.predict(X)[0], 0))

        # Ensure logical ordering
        low   = min(low, pred)
        high  = max(high, pred)

        return {
            "district":        district,
            "crop":            crop,
            "season":          season,
            "area_ha":         round(area, 2),
            # Per hectare yields
            "predicted_yield": round(pred, 3),
            "min_yield":       round(low, 3),
            "max_yield":       round(high, 3),
            # Total farm production
            "total_predicted": round(pred * area, 2),
            "total_min":       round(low * area, 2),
            "total_max":       round(high * area, 2),
            # Labels
            "yield_category":  self._yield_category(pred, crop),
            "confidence":      self._confidence_label(low, high, pred),
        }

    # ── Batch ─────────────────────────────────────────────────────────────────

    def predict_batch(self, records: list[dict]) -> list[dict]:
        """
        Run predict() for a list of input dicts.
        Each dict must have the same keys as the predict() parameters.
        """
        return [self.predict(**r) for r in records]

    # ── Available options ─────────────────────────────────────────────────────

    def available_options(self) -> dict:
        """
        Return the valid choices for categorical inputs (from training data).
        NaN or 'nan' entries are stripped so the response is JSON-safe.
        """
        import math

        def _clean(classes):
            result = []
            for c in classes:
                # Skip float NaN
                if isinstance(c, float) and math.isnan(c):
                    continue
                # Skip the string "nan" that LabelEncoder creates from NaN rows
                if isinstance(c, str) and c.lower() == "nan":
                    continue
                result.append(str(c))
            return sorted(result)

        return {
            col: _clean(self.encoders[col].classes_)
            for col in self.categorical_cols
        }
