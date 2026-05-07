"""
Diagnose why the model is inaccurate — per-crop error analysis
"""
import joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, r2_score

# Load artifacts
rf       = joblib.load('saved_models/rf_model.pkl')
imputer  = joblib.load('saved_models/imputer.pkl')
encoders = joblib.load('saved_models/encoders.pkl')
meta     = joblib.load('saved_models/feature_meta.pkl')

CAT = meta['categorical']
NUM = meta['numerical']

df = pd.read_csv('final_merged_crop_weather_soil_irrigation_data.csv')
df = df[df['Yield'] > 0].copy()

# Encode
df_enc = df.copy()
for col in CAT:
    le = encoders[col]
    # handle unseen labels
    df_enc[col] = df_enc[col].astype(str).apply(
        lambda v: le.transform([v])[0] if v in le.classes_ else 0
    )

X = df_enc[CAT + NUM].values
y = df['Yield'].values

X_train, X_test, y_train, y_test, idx_train, idx_test = train_test_split(
    X, y, df.index, test_size=0.2, random_state=42
)

X_test_imp = imputer.transform(X_test)
y_pred = np.expm1(rf.predict(X_test_imp))
y_pred = np.maximum(y_pred, 0)

df_test = df.loc[idx_test].copy()
df_test['predicted'] = y_pred
df_test['actual']    = y_test
df_test['error']     = np.abs(y_pred - y_test)
df_test['pct_error'] = (df_test['error'] / df_test['actual'] * 100).round(1)

print('=== OVERALL METRICS ===')
print(f'MAE:  {mean_absolute_error(y_test, y_pred):.3f} t/ha')
print(f'R2:   {r2_score(y_test, y_pred):.3f}')

print()
print('=== PER-CROP MAE (t/ha) ===')
per_crop = df_test.groupby('Crop').apply(
    lambda g: pd.Series({
        'n':       len(g),
        'avg_actual': g['actual'].mean().round(2),
        'avg_predicted': g['predicted'].mean().round(2),
        'MAE':     g['error'].mean().round(3),
        'pct_err': g['pct_error'].mean().round(1),
    })
).sort_values('MAE', ascending=False)
print(per_crop.to_string())

print()
print('=== WORST INDIVIDUAL PREDICTIONS ===')
worst = df_test.nlargest(10, 'pct_error')[['Crop','district','actual','predicted','pct_error']]
print(worst.to_string())

print()
print('=== TRAINING DATA SIZE ISSUE ===')
small = df.groupby('Crop').size()
print('Crops with < 50 training rows (very low data):')
print(small[small < 50].sort_values())
