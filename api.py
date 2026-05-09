"""
api.py  –  FastAPI backend for Gujarat Crop Yield Prediction
=============================================================
Run:
    uvicorn api:app --reload --port 8000

Endpoints:
    GET  /health     – server status
    GET  /options    – valid dropdown choices (from trained encoders)
    GET  /metrics    – model accuracy metrics from latest training report
    POST /predict    – full prediction + weather + financials
"""

import os
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn
from time import time
from collections import defaultdict

from predictor import YieldPredictor
from weather_service import get_live_weather, merge_weather_with_historical
from financials import calculate_financials

# Optional convenience for local dev when a .env exists
try:
    from dotenv import load_dotenv  # type: ignore

    load_dotenv()
except Exception:
    pass

# ─────────────────────────────────────────────────────────────────────────────
# APP INIT
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Harvestment – Gujarat Crop Yield Prediction API",
    description=(
        "AI-powered crop yield prediction with financial advisory for Gujarat farmers. "
        "Predicts yield (t/ha) with confidence intervals, integrates live weather, "
        "and provides cost/profit/ROI analysis."
    ),
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

def _read_allowed_origins() -> list[str]:
    raw = (os.environ.get("ALLOWED_ORIGINS") or "").strip()
    if not raw:
        return ["http://localhost:8000", "http://127.0.0.1:8000"]
    return [o.strip() for o in raw.split(",") if o.strip()]


# Allow frontend to call this API (restrict via ALLOWED_ORIGINS in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_read_allowed_origins(),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load models once at startup (avoids re-loading on every request)
MODEL_DIR = "saved_models"
model = YieldPredictor(model_dir=MODEL_DIR)


# ─────────────────────────────────────────────────────────────────────────────
# REQUEST / RESPONSE SCHEMAS
# ─────────────────────────────────────────────────────────────────────────────

class PredictRequest(BaseModel):
    district:             str   = Field(..., example="Amreli",     description="Gujarat district name")
    crop:                 str   = Field(..., example="Groundnut",  description="Crop name")
    season:               str   = Field(..., example="Kharif",     description="Kharif or Rabi")
    area:                 float = Field(..., gt=0, example=10.0,   description="Cultivated area in hectares")
    soil_type:            str   = Field(..., example="Black",      description="Soil type")
    soil_fertility_score: float = Field(..., ge=1, le=10, example=5.0, description="Fertility score 1–10")
    irrigation_score:     float = Field(..., ge=0, le=1,  example=0.6,  description="Irrigation coverage 0–1")

    class Config:
        json_schema_extra = {
            "example": {
                "district": "Amreli",
                "crop": "Groundnut",
                "season": "Kharif",
                "area": 10.0,
                "soil_type": "Black",
                "soil_fertility_score": 5.0,
                "irrigation_score": 0.6,
            }
        }


# ─────────────────────────────────────────────────────────────────────────────
# HELPER – parse training report
# ─────────────────────────────────────────────────────────────────────────────

def _parse_training_report(report_path: str) -> dict:
    """Read training_report.txt and return structured metrics dict."""
    metrics = {
        "model": "Unknown",
        "mae":       None,
        "rmse":      None,
        "r2":        None,
        "coverage":  None,
        "avg_width": None,
        "report_raw": "",
    }
    if not os.path.exists(report_path):
        return metrics

    with open(report_path, "r") as f:
        lines = f.readlines()

    metrics["report_raw"] = "".join(lines)

    for line in lines:
        line = line.strip()
        if line.startswith("MODEL:"):
            metrics["model"] = line.split("MODEL:")[-1].strip()
        elif line.startswith("MAE"):
            try:
                metrics["mae"] = float(line.split(":")[1].split()[0])
            except Exception:
                pass
        elif line.startswith("RMSE"):
            try:
                metrics["rmse"] = float(line.split(":")[1].split()[0])
            except Exception:
                pass
        elif line.startswith("R²") or line.startswith("R2"):
            try:
                metrics["r2"] = float(line.split(":")[1].strip())
            except Exception:
                pass
        elif line.startswith("Coverage"):
            try:
                val = line.split(":")[1].strip().replace("%", "").split()[0]
                metrics["coverage"] = float(val)
            except Exception:
                pass
        elif line.startswith("Avg width"):
            try:
                metrics["avg_width"] = float(line.split(":")[1].split()[0])
            except Exception:
                pass

    return metrics


# ─────────────────────────────────────────────────────────────────────────────
# ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/health", tags=["System"])
def health():
    """Server liveness check."""
    return {
        "status": "ok",
        "model_version": "gujarat_yield_v2",
        "api_version": "2.0.0",
    }


@app.get("/options", tags=["System"])
def get_options():
    """
    Returns all valid choices for district, crop, season, soil_type.
    Use this to dynamically populate dropdowns in the frontend.
    Values are derived directly from the trained LabelEncoders,
    so they always match what the model supports.
    """
    return model.available_options()


@app.get("/metrics", tags=["System"])
def get_metrics():
    """
    Returns model accuracy metrics from the latest training report.
    Reads saved_models/training_report.txt and returns structured JSON.
    """
    report_path = os.path.join(MODEL_DIR, "training_report.txt")
    metrics = _parse_training_report(report_path)
    if metrics["r2"] is None:
        raise HTTPException(
            status_code=404,
            detail="Training report not found. Run train.py first."
        )
    return {
        "model":            metrics["model"],
        "mae_tonnes_ha":    metrics["mae"],
        "rmse_tonnes_ha":   metrics["rmse"],
        "r2_score":         metrics["r2"],
        "quantile_coverage_pct": metrics["coverage"],
        "quantile_avg_width_tha": metrics["avg_width"],
        "report_path":      report_path,
    }


@app.post("/predict", tags=["Prediction"])
def predict(req: PredictRequest):
    """
    Full prediction pipeline:
      1. Fetch live weather for the district (OpenWeatherMap)
      2. Blend live weather with historical averages → model inputs
      3. Run yield prediction (central + 10th/90th percentile)
      4. Calculate financial advisory (cost, revenue, ROI, scenarios)
      5. Return combined response
    """
    try:
        # 1. Fetch live weather
        live_weather = get_live_weather(req.district)

        # 2. Merge with historical baseline → full weather feature set
        weather_inputs = merge_weather_with_historical(req.district, live_weather, req.season)

        # 3. Predict Yield
        result = model.predict(
            district             = req.district,
            crop                 = req.crop,
            season               = req.season,
            area                 = req.area,
            min_temp             = weather_inputs["min_temp"],
            max_temp             = weather_inputs["max_temp"],
            total_rain           = weather_inputs["total_rain"],
            humidity_avg         = weather_inputs["humidity_avg"],
            yearly_min_temp      = weather_inputs["yearly_min_temp"],
            yearly_max_temp      = weather_inputs["yearly_max_temp"],
            yearly_total_rain    = weather_inputs["yearly_total_rain"],
            yearly_humidity_avg  = weather_inputs["yearly_humidity_avg"],
            soil_type            = req.soil_type,
            soil_fertility_score = req.soil_fertility_score,
            irrigation_score     = req.irrigation_score,
        )

        # 4. Calculate Financials
        fin_data = calculate_financials(
            crop       = req.crop,
            area_ha    = req.area,
            pred_yield = result["predicted_yield"],
            min_yield  = result["min_yield"],
            max_yield  = result["max_yield"],
        )

        # 5. Compose response
        result["live_weather"] = live_weather
        result["financials"]   = fin_data

        return result

    except ValueError as ve:
        raise HTTPException(status_code=422, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")


# ─────────────────────────────────────────────────────────────────────────────
# FRONTEND SERVING
# ─────────────────────────────────────────────────────────────────────────────
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

@app.get("/", include_in_schema=False)
def serve_index():
    return FileResponse(os.path.join("frontend", "index.html"))

@app.get("/advisory", include_in_schema=False)
def serve_advisory():
    return FileResponse(os.path.join("frontend", "advisory.html"))

@app.get("/dashboard", include_in_schema=False)
def serve_dashboard():
    return FileResponse(os.path.join("frontend", "dashboard.html"))

@app.get("/crops", include_in_schema=False)
def serve_crops():
    return FileResponse(os.path.join("frontend", "crops.html"))

app.mount("/", StaticFiles(directory="frontend"), name="frontend")

# ─────────────────────────────────────────────────────────────────────────────
# DIRECT RUN
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("api:app", host="0.0.0.0", port=port, reload=True)
