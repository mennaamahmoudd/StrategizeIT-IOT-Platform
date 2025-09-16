import json
import time
import joblib
import pandas as pd
import requests

# ----------------------------
# Load crop health model & encoders
# ----------------------------
rf = joblib.load("rf_crop_health.pkl")
encoders = joblib.load("label_encoders.pkl")

# ----------------------------
# ThingsBoard setup
# ----------------------------
THINGSBOARD_HOST = "http://localhost:8080"
USERNAME = "tenant@thingsboard.org"   # your TB username
PASSWORD = "tenant"                   # your TB password

SENSOR_DEVICE_ID = "0c81c9f0-8d83-11f0-8a0a-af88f2e450d8"  # sensor UUID
AI_TOKEN = "raFF8vt0GfbcL0hFjMHa"          # AI device token

# ----------------------------
# Helpers
# ----------------------------
def login():
    url = f"{THINGSBOARD_HOST}/api/auth/login"
    body = {"username": USERNAME, "password": PASSWORD}
    r = requests.post(url, json=body)
    r.raise_for_status()
    return r.json()["token"]

def fetch_latest_telemetry(jwt_token):
    url = f"{THINGSBOARD_HOST}/api/plugins/telemetry/DEVICE/{SENSOR_DEVICE_ID}/values/timeseries"
    keys = "Crop,EC,Humidity,Moisture,PAR,pH,Plant phase,Temp_air,Temp_soil"
    r = requests.get(f"{url}?keys={keys}", headers={"Authorization": f"Bearer {jwt_token}"})
    r.raise_for_status()
    return r.json()

def parse_latest(telemetry: dict):
    # get the latest value for each key
    return {
        "Crop": telemetry.get("Crop", [{}])[-1].get("value", "Unknown"),
        "EC": float(telemetry.get("EC", [{}])[-1].get("value", 0.0)),
        "Humidity": float(telemetry.get("Humidity", [{}])[-1].get("value", 0.0)),
        "Moisture": float(telemetry.get("Moisture", [{}])[-1].get("value", 0.0)),
        "PAR": float(telemetry.get("PAR", [{}])[-1].get("value", 0.0)),
        "pH": float(telemetry.get("pH", [{}])[-1].get("value", 0.0)),
        "Plant phase": telemetry.get("Plant phase", [{}])[-1].get("value", "Unknown"),
        "Temp_air": float(telemetry.get("Temp_air", [{}])[-1].get("value", 0.0)),
        "Temp_soil": float(telemetry.get("Temp_soil", [{}])[-1].get("value", 0.0)),
    }

def create_sample(data: dict) -> pd.DataFrame:
    df_input = pd.DataFrame([data])
    # encode categorical columns
    for col in ["Plant phase", "Crop"]:
        df_input[col] = encoders[col].transform(df_input[col])
    return df_input

# ----------------------------
# Main loop
# ----------------------------
jwt = login()
print("✅ Logged in, got JWT token")

while True:
    try:
        telemetry = fetch_latest_telemetry(jwt)
        print("Fetched telemetry:", telemetry)

        data = parse_latest(telemetry)
        print("Parsed values:", data)

        # predict crop health
        features = create_sample(data)
        pred = rf.predict(features)[0]
        label = encoders["Healthy"].inverse_transform([pred])[0]

        result = {
            "crop_name": data.get("Crop", "Unknown"),
            "plant_phase": data.get("Plant phase", "Unknown"),
            "predicted_health": label
        }

        # send prediction to AI device
        ai_url = f"{THINGSBOARD_HOST}/api/v1/{AI_TOKEN}/telemetry"
        r = requests.post(ai_url, json=result)
        print("Sent prediction:", result, "Status:", r.status_code)

    except requests.HTTPError as e:
        if e.response.status_code == 401:
            print("⚠️ JWT expired, logging in again...")
            jwt = login()
        else:
            print("HTTP error:", e)

    except Exception as e:
        print("Error:", e)

    time.sleep(10)  # check every 10 seconds
