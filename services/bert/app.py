from fastapi import FastAPI
from transformers import pipeline
import time
import logging

app = FastAPI()

logging.basicConfig(level=logging.INFO)

classifier = pipeline("sentiment-analysis", model="bert-base-uncased")

@app.post("/predict")
def predict(data: dict):
    text = data["text"]

    start = time.time()
    result = classifier(text)
    latency = time.time() - start

    logging.info(f"BERT | Input: {text} | Latency: {latency}")

    return {
        "model": "bert",
        "result": result,
        "latency": latency
    }
