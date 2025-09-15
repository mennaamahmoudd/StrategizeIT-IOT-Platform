import paho.mqtt.client as mqtt
import json
import joblib
import pandas as pd

rf = joblib.load("rf_crop_health.pkl")
encoders = joblib.load("label_encoders.pkl")

THINGSBOARD_HOST = "localhost"   
SENSOR_TOKEN = "TvZfPq6PyB09zMS33Dac"  # Token of the sensor device
AI_TOKEN = "raFF8vt0GfbcL0hFjMHa"          # Token of the AI device
sensor_client = mqtt.Client()
sensor_client.username_pw_set(SENSOR_TOKEN)
ai_client = mqtt.Client()
ai_client.username_pw_set(AI_TOKEN)
ai_client.connect(THINGSBOARD_HOST, 1883, 60)

def on_connect(client, userdata, flags, rc):
    print("Connected to ThingsBoard, result code:", rc)
    client.subscribe("v1/devices/me/telemetry")

def on_message(client, userdata, msg):
    data = json.loads(msg.payload.decode("utf-8"))
    print("Received telemetry:", data)
    crop_name = data.get("Crop", "Unknown")
    plant_phase = data.get("Plant phase", "Unknown")

    df_input = pd.DataFrame([data])
    for col in ["Plant phase", "Crop"]:
        df_input[col] = encoders[col].transform(df_input[col])

    pred = rf.predict(df_input)[0]
    label = encoders["Healthy"].inverse_transform([pred])[0]
    result = {
        "predicted_health": label,
        "crop_name": crop_name,
        "plant_phase": plant_phase
    }
    ai_client.publish("v1/devices/me/telemetry", json.dumps(result))
    print("Published to AI device:", result)

sensor_client.on_connect = on_connect
sensor_client.on_message = on_message

sensor_client.connect(THINGSBOARD_HOST, 1883, 60)
sensor_client.loop_forever()
