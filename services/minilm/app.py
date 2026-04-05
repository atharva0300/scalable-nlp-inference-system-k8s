from fastapi import FastAPI
from transformers import pipeline
import time
import logging

app = FastAPI()

logging.basicConfig(level=logging.INFO)

classifier = pipeline("sentiment-analysis", model="nlptown/bert-base-multilingual-uncased-sentiment")

@app.post("/predict")
def predict(data: dict):
    text = data["text"]

    start = time.time()
    result = classifier(text)
    latency = time.time() - start

    logging.info(f"MiniLM | Input: {text} | Latency: {latency}")

    return {
        "model": "minilm",
        "result": result,
        "latency": latency
    }
