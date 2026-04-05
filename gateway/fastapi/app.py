from fastapi import FastAPI, HTTPException
import requests

app = FastAPI()

SERVICES = {
    "bert": "http://bert-service:8000/predict",
    "distilbert": "http://distilbert-service:8000/predict",
    "minilm": "http://minilm-service:8000/predict"
}

@app.post("/{model}")
def route(model: str, data: dict):
    if model not in SERVICES:
        raise HTTPException(status_code=400, detail="Invalid model")

    try:
        response = requests.post(SERVICES[model], json=data)
        return response.json()
    except Exception as e:
        return {"error": str(e)}
