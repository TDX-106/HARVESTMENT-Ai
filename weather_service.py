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

def get_live_weather(district: str) -> Dict[str, float]:
    """
    Fetches live weather from OpenWeatherMap for the given district in Gujarat.
    Returns temperatures in Celsius and humidity.
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
    url = f"https://api.openweathermap.org/data/2.5/weather?q={safe_district},Gujarat,IN&appid={API_KEY}&units=metric"
    
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()
        
        # We need min_temp, max_temp, humidity_avg
        current_temp = data["main"]["temp"]
        temp_min = data["main"]["temp_min"]
        temp_max = data["main"]["temp_max"]
        humidity = data["main"]["humidity"]
        
        return {
            "min_temp": temp_min,
            "max_temp": temp_max,
            "humidity_avg": humidity,
            "current_temp": current_temp,
            # We don't get total_rain easily from current weather unless it's raining right now, 
            # so we'll just indicate 0 if 'rain' key is missing.
            "current_rain_mm": data.get("rain", {}).get("1h", 0.0)
        }
    except Exception as e:
        print(f"Weather API Error: {e}")
        # Fallback to sensible defaults if API fails
        return {
            "min_temp": 22.0,
            "max_temp": 32.0,
            "humidity_avg": 60.0,
            "current_temp": 28.0,
            "current_rain_mm": 0.0
        }

def merge_weather_with_historical(district: str, live_data: Dict[str, float]) -> Dict[str, float]:
    """
    The ML model needs seasonal/yearly averages. Since live weather is just a snapshot,
    we'll blend the live temperature/humidity with historical Gujarat averages to generate
    plausible season data for the model prediction.
    """
    # In a real app, you'd pull from a historical climatology database.
    # Here we mock the yearly/seasonal averages, slightly adjusted by current live deviations.
    
    # Let's say standard Gujarat averages are:
    std_min = 20.0
    std_max = 35.0
    std_hum = 55.0
    
    # Calculate deviation of current live weather from standard
    dev_min = live_data["min_temp"] - std_min
    dev_max = live_data["max_temp"] - std_max
    dev_hum = live_data["humidity_avg"] - std_hum
    
    # Apply scaled deviation to create "season" and "yearly" inputs for the model
    return {
        "min_temp": std_min + (dev_min * 0.5),
        "max_temp": std_max + (dev_max * 0.5),
        "total_rain": 400.0, # Mock seasonal rain
        "humidity_avg": std_hum + (dev_hum * 0.5),
        "yearly_min_temp": std_min + (dev_min * 0.2),
        "yearly_max_temp": std_max + (dev_max * 0.2),
        "yearly_total_rain": 800.0, # Mock yearly rain
        "yearly_humidity_avg": std_hum + (dev_hum * 0.2)
    }
