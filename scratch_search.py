import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor, HistGradientBoostingRegressor
from sklearn.metrics import r2_score, mean_absolute_error, mean_squared_error
from sklearn.preprocessing import LabelEncoder
from sklearn.impute import SimpleImputer

# Load
df = pd.read_csv("final_merged_crop_weather_soil_irrigation_data.csv")
for col in ["soil_type"]:
    if col in df.columns:
        df[col].fillna(df[col].mode()[0], inplace=True)
for col in ["soil_fertility_score", "irrigation_score", "Production"]:
    if col in df.columns:
        df[col].fillna(df[col].median(), inplace=True)
df = df[df["Yield"] > 0].copy()

CAT_COLS = ["district", "Crop", "Season", "soil_type"]
NUM_COLS = ["Area", "min_temp_avg", "max_temp_avg", "total_rain", "humidity_avg", 
            "yearly_min_temp_avg", "yearly_max_temp_avg", "yearly_total_rain", 
            "yearly_humidity_avg", "soil_fertility_score", "irrigation_score"]

for col in CAT_COLS:
    le = LabelEncoder()
    df[col] = le.fit_transform(df[col].astype(str))

X = df[CAT_COLS + NUM_COLS].values
y = df["Yield"].values
y_log = np.log1p(y)

X_train, X_test, y_train, y_test = train_test_split(X, y_log, test_size=0.2, random_state=42)

imputer = SimpleImputer(strategy="median")
X_train = imputer.fit_transform(X_train)
X_test = imputer.transform(X_test)

# Test RF with different max_features
print("RF (sqrt):")
rf_sqrt = RandomForestRegressor(n_estimators=300, min_samples_leaf=2, max_features="sqrt", random_state=42, n_jobs=-1)
rf_sqrt.fit(X_train, y_train)
y_pred_sqrt = np.expm1(rf_sqrt.predict(X_test))
print("R2:", r2_score(np.expm1(y_test), y_pred_sqrt))

print("RF (None):")
rf_none = RandomForestRegressor(n_estimators=300, min_samples_leaf=2, max_features=None, random_state=42, n_jobs=-1)
rf_none.fit(X_train, y_train)
y_pred_none = np.expm1(rf_none.predict(X_test))
print("R2:", r2_score(np.expm1(y_test), y_pred_none))

print("HistGradientBoosting:")
hgb = HistGradientBoostingRegressor(random_state=42, max_iter=500, learning_rate=0.05)
hgb.fit(X_train, y_train)
y_pred_hgb = np.expm1(hgb.predict(X_test))
print("R2:", r2_score(np.expm1(y_test), y_pred_hgb))
