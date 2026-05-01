import os
from typing import Dict

import requests

try:
    # Optional convenience for local dev when a .env exists
    from dotenv import load_dotenv  # type: ignore

    load_dotenv()
except Exception:
    pass

API_KEY = os.environ.get("OWM_API_KEY")

# ─────────────────────────────────────────────────────────────────────────────
# DISTRICT-LEVEL RAINFALL LOOKUP (Gujarat IMD averages, mm)
# Source: IMD Gujarat state reports & Gujarat Agriculture Dept data
# ─────────────────────────────────────────────────────────────────────────────

# Seasonal rainfall by district: (kharif_mm, rabi_mm, yearly_mm)
# Kharif = June–October (southwest monsoon), Rabi = November–March
_DISTRICT_RAIN = {
    "Ahmedabad":       (550,  30, 600),
    "Amreli":          (650,  40, 720),
    "Anand":           (820,  35, 880),
    "Aravalli":        (780,  30, 840),
    "Banaskantha":     (620,  25, 680),
    "Bharuch":         (900,  45, 980),
    "Bhavnagar":       (570,  30, 630),
    "Botad":           (510,  25, 560),
    "Chhota Udaipur":  (1200, 55, 1300),
    "Dahod":           (1050, 50, 1150),
    "Dang":            (2100, 80, 2300),
    "Devbhumi Dwarka": (490,  30, 540),
    "Gandhinagar":     (740,  30, 800),
    "Gir Somnath":     (700,  40, 770),
    "Jamnagar":        (510,  30, 570),
    "Junagadh":        (780,  45, 860),
    "Kheda":           (830,  35, 890),
    "Kutch":           (360,  20, 400),
    "Mahisagar":       (880,  40, 950),
    "Mehsana":         (610,  25, 660),
    "Morbi":           (520,  25, 570),
    "Narmada":         (1050, 50, 1150),
    "Navsari":         (1500, 60, 1650),
    "Panchmahal":      (980,  45, 1060),
    "Patan":           (590,  25, 640),
    "Porbandar":       (620,  35, 680),
    "Rajkot":          (620,  30, 680),
    "Sabarkantha":     (850,  35, 920),
    "Surat":           (1400, 60, 1550),
    "Surendranagar":   (470,  25, 520),
    "Tapi":            (1150, 55, 1270),
    "Vadodara":        (870,  40, 950),
    "Valsad":          (1750, 70, 1950),
}

# State-level fallback averages (Gujarat overall)
_DEFAULT_RAIN = (700, 35, 760)


def _get_district_rain(district: str, season: str) -> tuple:
    """Return (seasonal_mm, yearly_mm) for a given district and season."""
    kharif_mm, rabi_mm, yearly_mm = _DISTRICT_RAIN.get(district, _DEFAULT_RAIN)
    season_lower = (season or "").lower()
    if "rabi" in season_lower:
        return rabi_mm, yearly_mm
    # Kharif, Other/Zaid, or unknown → use monsoon (dominant season)
    return kharif_mm, yearly_mm


def sanitize_district(district: str) -> str:
    """Strip non-alpha characters to prevent injection in URL params."""
    return "".join(c for c in district if c.isalpha() or c in (" ", "-"))


def get_live_weather(district: str) -> Dict[str, float]:
    """
    Fetches live weather from OpenWeatherMap for the given district in Gujarat.
    Returns temperatures in Celsius and humidity.
    Falls back to sensible Gujarat defaults if API key is not set or call fails.
    """
    if not API_KEY:
        # Fallback to sensible defaults if key is not configured
        return {
            "min_temp": 22.0,
            "max_temp": 32.0,
            "humidity_avg": 60.0,
            "current_temp": 28.0,
            "current_rain_mm": 0.0,
        }

    # Sanitize input to prevent injection
    safe_district = sanitize_district(district)
    url = (
        f"https://api.openweathermap.org/data/2.5/weather"
        f"?q={safe_district},Gujarat,IN&appid={API_KEY}&units=metric"
    )

    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()

        current_temp = data["main"]["temp"]
        temp_min     = data["main"]["temp_min"]
        temp_max     = data["main"]["temp_max"]
        humidity     = data["main"]["humidity"]

        return {
            "min_temp":       temp_min,
            "max_temp":       temp_max,
            "humidity_avg":   humidity,
            "current_temp":   current_temp,
            # Rain key only present when it's actually raining
            "current_rain_mm": data.get("rain", {}).get("1h", 0.0),
        }
    except Exception as e:
        print(f"Weather API Error: {e}")
        return {
            "min_temp":       22.0,
            "max_temp":       32.0,
            "humidity_avg":   60.0,
            "current_temp":   28.0,
            "current_rain_mm": 0.0,
        }


def merge_weather_with_historical(
    district: str, live_data: Dict[str, float], season: str = "Kharif"
) -> Dict[str, float]:
    """
    The ML model needs seasonal/yearly averages.
    Live weather is a snapshot, so we blend it with district-level historical
    Gujarat IMD averages to produce plausible seasonal features for the model.

    Rainfall is now district + season aware (not hardcoded).
    """
    # Standard Gujarat averages used as the baseline
    std_min = 20.0
    std_max = 35.0
    std_hum = 55.0

    # Deviation of live reading from the standard baseline
    dev_min = live_data["min_temp"]    - std_min
    dev_max = live_data["max_temp"]    - std_max
    dev_hum = live_data["humidity_avg"] - std_hum

    # District + season specific rainfall (replaces the old hardcoded 400/800)
    seasonal_rain_mm, yearly_rain_mm = _get_district_rain(district, season)

    return {
        "min_temp":          std_min + (dev_min * 0.5),
        "max_temp":          std_max + (dev_max * 0.5),
        "total_rain":        float(seasonal_rain_mm),
        "humidity_avg":      std_hum + (dev_hum * 0.5),
        "yearly_min_temp":   std_min + (dev_min * 0.2),
        "yearly_max_temp":   std_max + (dev_max * 0.2),
        "yearly_total_rain": float(yearly_rain_mm),
        "yearly_humidity_avg": std_hum + (dev_hum * 0.2),
    }
