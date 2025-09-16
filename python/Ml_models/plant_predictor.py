import os
import time
import joblib
import numpy as np
import requests
import logging

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("plant_predictor")

BASE_DIR = os.path.dirname(__file__)
MODEL_PATH = os.path.join(BASE_DIR, "logistic_regression_model.pkl")
ENCODER_PATH = os.path.join(BASE_DIR, "label_encoder.pkl")

model = joblib.load(MODEL_PATH)
label_encoder = joblib.load(ENCODER_PATH)

THINGSBOARD_HOST = os.getenv("TB_HOST", "http://localhost:8080")
USERNAME = os.getenv("TB_USER", "tenant@thingsboard.org")
PASSWORD = os.getenv("TB_PASS", "tenant")

DEVICE_ID = os.getenv("TB_DEVICE_ID", "65e46ee0-909d-11f0-81e7-8d96a163022e")
AI_TOKEN = os.getenv("TB_AI_TOKEN",  "zd6JOLPpr6DvHrgTP5p3")


def login():
    url = f"{THINGSBOARD_HOST}/api/auth/login"
    r = requests.post(
        url, json={"username": USERNAME, "password": PASSWORD}, timeout=10)
    r.raise_for_status()
    return r.json()["token"]


def fetch_latest(jwt):
    keys = "N,P,K,temperature,humidity,ph,rainfall,water_availability"
    url = f"{THINGSBOARD_HOST}/api/plugins/telemetry/DEVICE/{DEVICE_ID}/values/timeseries?keys={keys}"
    r = requests.get(
        url, headers={"Authorization": f"Bearer {jwt}"}, timeout=10)
    r.raise_for_status()
    return r.json()


def parse_latest(raw):
    def val(k): return float(raw.get(k, [{}])[-1].get("value", 0))
    return {k: val(k) for k in ["N", "P", "K", "temperature", "humidity", "ph", "rainfall", "water_availability"]}


def predict(features):
    X = np.array([[features[k] for k in ["N", "P", "K", "temperature",
                 "humidity", "ph", "rainfall", "water_availability"]]])
    idx = model.predict(X)
    label = label_encoder.inverse_transform(idx)[0]
    conf = None
    if hasattr(model, "predict_proba"):
        try:
            conf = float(np.max(model.predict_proba(X)))
        except Exception:
            pass
    return label, conf


def send_prediction(label, conf):
    payload = {"plant_prediction": label}
    if conf is not None:
        payload["plant_confidence"] = conf
    r = requests.post(f"{THINGSBOARD_HOST}/api/v1/{AI_TOKEN}/telemetry",
                      json=payload, timeout=10)
    r.raise_for_status()


def main():
    jwt = login()
    logger.info("Logged in to ThingsBoard")
    while True:
        try:
            data = parse_latest(fetch_latest(jwt))
            label, conf = predict(data)
            send_prediction(label, conf)
            logger.info("Prediction sent: %s (conf: %s)", label, conf)
        except requests.HTTPError as e:
            if e.response.status_code == 401:
                logger.warning("JWT expired, re-logging…")
                jwt = login()
            else:
                logger.exception("HTTP error")
        except Exception:
            logger.exception("Loop error")
        time.sleep(10)


if __name__ == "__main__":
    main()

"""
This will:

Log in to ThingsBoard.

Pull the latest telemetry from the device whose UUID you configured.

Run the logistic regression model every 10 seconds.

Push the prediction and confidence to the AI device token.

"""