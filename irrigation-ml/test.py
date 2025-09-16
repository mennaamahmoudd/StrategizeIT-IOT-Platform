import json
import time
import joblib
import pandas as pd
import requests

# ----------------------------
# Load irrigation model & scaler
# ----------------------------
model = joblib.load("irrigation_model.pkl")
scaler = joblib.load("scaler.pkl")

# ----------------------------
# ThingsBoard setup
# ----------------------------
THINGSBOARD_HOST = "http://localhost:8080"
USERNAME = "tenant@thingsboard.org"   # change to your TB username
PASSWORD = "tenant1"                   # change to your TB password

SENSOR_DEVICE_ID = "ec7e25b0-9140-11f0-9afe-1fb5e17afd17"  # UUID from ThingsBoard
AI_TOKEN = "ZnuKyUvWvkXtO1jlNX95"           # Token of AI device (for sending predictions)

# ----------------------------
# Helper: create input row for model
# ----------------------------
def create_sample(data: dict) -> pd.DataFrame:
    sample = {
        "MOI": data.get("moisture", 0) / 100,
        "temp": data.get("temperature", 0),
        "humidity": float(data.get("humidity", 0.0)),
        "crop ID_Chilli": False,
        "crop ID_Potato": False,
        "crop ID_Tomato": False,
        "crop ID_Wheat": False,
        "soil_type_Black Soil": False,
        "soil_type_Chalky Soil": False,
        "soil_type_Clay Soil": False,
        "soil_type_Loam Soil": False,
        "soil_type_Red Soil": False,
        "soil_type_Sandy Soil": False,
        "Seedling Stage_Fruit/Grain/Bulb Formation": False,
        "Seedling Stage_Germination": False,
        "Seedling Stage_Harvest": False,
        "Seedling Stage_Maturation": False,
        "Seedling Stage_Pollination": False,
        "Seedling Stage_Seedling Stage": False,
        "Seedling Stage_Vegetative Growth / Root or Tuber Development": False,
    }

    crop_key = f"crop ID_{data.get('crop_type', '')}"
    if crop_key in sample:
        sample[crop_key] = True

    soil_key = f"soil_type_{data.get('soil_type', '')}"
    if soil_key in sample:
        sample[soil_key] = True

    stage_key = f"Seedling Stage_{data.get('seedling_stage', '')}"
    if stage_key in sample:
        sample[stage_key] = True

    df = pd.DataFrame([sample])
    df[['MOI', 'temp', 'humidity']] = scaler.transform(df[['MOI', 'temp', 'humidity']])
    return df

# ----------------------------
# Helpers: JWT login + fetch telemetry
# ----------------------------
def login():
    url = f"{THINGSBOARD_HOST}/api/auth/login"
    body = {"username": USERNAME, "password": PASSWORD}
    r = requests.post(url, json=body)
    r.raise_for_status()
    return r.json()["token"]

def fetch_latest_telemetry(jwt_token):
    url = f"{THINGSBOARD_HOST}/api/plugins/telemetry/DEVICE/{SENSOR_DEVICE_ID}/values/timeseries"
    keys = "temperature,humidity,moisture,soil_type,seedling_stage,crop_type"
    r = requests.get(f"{url}?keys={keys}", headers={"Authorization": f"Bearer {jwt_token}"})
    r.raise_for_status()
    return r.json()

def parse_latest(telemetry: dict):
    return {
        "temperature": float(telemetry.get("temperature", [{}])[-1].get("value", 0)),
        "humidity": float(telemetry.get("humidity", [{}])[-1].get("value", 0)),
        "moisture": float(telemetry.get("moisture", [{}])[-1].get("value", 0)),
        "soil_type": telemetry.get("soil_type", [{}])[-1].get("value", ""),
        "seedling_stage": telemetry.get("seedling_stage", [{}])[-1].get("value", ""),
        "crop_type": telemetry.get("crop_type", [{}])[-1].get("value", ""),
    }
# ----------------------------
# Main loop
# ----------------------------
jwt = login()
print("✅ Logged in, got JWT token")

while True:
    try:
        # fetch latest sensor telemetry
        telemetry = fetch_latest_telemetry(jwt)
        print("Fetched telemetry:", telemetry)

        data = parse_latest(telemetry)
        print("Parsed values:", data)

        # predict irrigation
        features = create_sample(data)
        irrigation_pred = int(model.predict(features)[0])
        print("Model prediction:", irrigation_pred)

        # send prediction to AI device
        ai_url = f"{THINGSBOARD_HOST}/api/v1/{AI_TOKEN}/telemetry"
        payload = {"prediction": irrigation_pred}
        r = requests.post(ai_url, json=payload)
        print("Sent prediction:", payload, "Status:", r.status_code)

    except requests.HTTPError as e:
        # if JWT expired → re-login
        if e.response.status_code == 401:
            print("⚠️ JWT expired, logging in again...")
            jwt = login()
        else:
            print("HTTP error:", e)

    except Exception as e:
        print("Error:", e)

    time.sleep(10)  # check every 10 seconds
