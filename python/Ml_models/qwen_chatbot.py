import os
import time
import requests
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("qwen_chatbot")

# ---- ThingsBoard Config ----
TB_HOST = os.getenv("TB_HOST", "http://localhost:8080")
TB_USER = os.getenv("TB_USER", "tenant@thingsboard.org")
TB_PASS = os.getenv("TB_PASS", "tenant")
DEVICE_ID = os.getenv("TB_DEVICE_ID", "c05d99c0-923f-11f0-afdb-3f761b513728")
AI_TOKEN = os.getenv("TB_TOKEN", "vhVhvkNetzkPMecjVp65")

# ---- Ollama Config ----
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
MODEL_NAME = os.getenv("OLLAMA_MODEL", "qwen:7b")

# ---- Custom Agriculture Prompt ----
SYSTEM_PROMPT = (
    "You are an expert agriculture and smart-farming assistant. "
    "Provide precise, practical advice on crop management, soil health, "
    "irrigation, fertilizers, and analysis of sensor data such as "
    "temperature, humidity, soil nutrients, and water availability. "
    "When a user provides sensor readings, interpret them and give "
    "clear recommendations for improving yield and sustainability."
)


def login():
    r = requests.post(f"{TB_HOST}/api/auth/login",
                      json={"username": TB_USER, "password": TB_PASS}, timeout=10)
    r.raise_for_status()
    return r.json()["token"]


def fetch_latest_question(jwt):
    keys = "ai_question"
    url = f"{TB_HOST}/api/plugins/telemetry/DEVICE/{DEVICE_ID}/values/timeseries?keys={keys}"
    r = requests.get(
        url, headers={"Authorization": f"Bearer {jwt}"}, timeout=10)
    r.raise_for_status()
    data = r.json()
    if "ai_question" in data and data["ai_question"]:
        return data["ai_question"][-1]["value"]
    return None


def query_qwen(user_question: str) -> str:
    """
    Prepend the domain-specific system prompt so the model specializes in agriculture.
    """
    prompt = f"{SYSTEM_PROMPT}\n\nUser Question: {user_question}\n\nExpert Answer:"
    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False
    }
    r = requests.post(OLLAMA_URL, json=payload, timeout=300)
    r.raise_for_status()
    return r.json().get("response", "").strip()


def send_answer(answer):
    payload = {"ai_answer": answer}
    r = requests.post(f"{TB_HOST}/api/v1/{AI_TOKEN}/telemetry",
                      json=payload, timeout=10)
    r.raise_for_status()


def main():
    jwt = login()
    logger.info("Connected to ThingsBoard")
    last_question = None
    while True:
        try:
            logger.info("Polling for ai_question…")
            q = fetch_latest_question(jwt)
            logger.info("Fetched: %s", q)
            if q and q != last_question:
                logger.info("New question: %s", q)
                ans = query_qwen(q)
                logger.info("Answer: %s", ans)
                send_answer(ans)
                last_question = q
        except requests.HTTPError as e:
            if e.response.status_code == 401:
                logger.warning("JWT expired; re-login")
                jwt = login()
            else:
                logger.error("HTTP error: %s", e)
        except Exception as e:
            logger.error("Error: %s", e)
        time.sleep(5)


if __name__ == "__main__":
    main()
