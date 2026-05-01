# Harvestment: Smart Crop Advisory System for Gujarat

Harvestment is an AI-powered agricultural advisory system tailored for farmers in Gujarat. It uses a HistGradientBoosting machine learning model to predict crop yields with confidence intervals, integrates live weather data via OpenWeatherMap, and calculates a full financial breakdown (costs, expected revenue, ROI, and breakeven risk).

![Harvestment Interface](frontend/bg.png)

## Features
- **AI Yield Prediction:** Quantile regression models providing pessimistic, expected, and optimistic yield estimates (R² = 0.974).
- **Financial Advisory:** Breakdowns of cultivation costs based on CACP data and revenue based on APMC/MSP prices.
- **Scenario Planning:** Dynamic risk analysis showing breakeven points.
- **Live Weather Integration:** Blends real-time temperature and humidity into the prediction pipeline.

---

## How to Run This Project Locally

If you have downloaded or cloned this project from GitHub, you can run the full frontend and backend locally in 3 simple steps:

### 1. Install Dependencies
Make sure you have Python installed. Open your terminal in the project folder and run:
```bash
pip install -r requirements.txt
```

### 1.5 Configure environment (.env)
Create a `.env` file in the project root (it’s already in `.gitignore`) with:

```bash
OWM_API_KEY=your_openweathermap_key_here
# Optional (recommended for any deployment):
# ALLOWED_ORIGINS=http://localhost:8000,https://your-domain.com
```

### 2. Start the Backend Server
The backend is built with FastAPI and serves both the API and the beautiful frontend interface. Start it by running:
```bash
python -m uvicorn api:app --reload --port 8000
```

### 3. Open the Dashboard
Once the server is running, simply open your web browser and navigate to:
👉 **http://localhost:8000/**

*(Note: The machine learning models are already pre-trained and included in the `saved_models/` directory. You do not need the massive original training dataset to run the web application!)*

---

### Tech Stack
- **Backend:** Python, FastAPI, Uvicorn
- **Machine Learning:** scikit-learn (HistGradientBoostingRegressor), Pandas, NumPy
- **Frontend:** Vanilla JavaScript, HTML5, CSS3 (Glassmorphism design), Chart.js
- **External APIs:** OpenWeatherMap
