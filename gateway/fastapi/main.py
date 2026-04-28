from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import Response
import httpx
import time
import asyncio
from prometheus_client import Counter, Histogram, Gauge, generate_latest
import logging
import json
import os
from datetime import datetime

app = FastAPI(title="Adaptive NLP Inference Router")

# JSON Logging for ELK
logger = logging.getLogger("NLPRouter")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('{"time": "%(asctime)s", "level": "%(levelname)s", "message": "%(message)s"}'))
logger.addHandler(handler)

# Prometheus Metrics
REQUEST_COUNT = Counter('request_count', 'Total generate requests', ['model'])
LATENCY = Histogram('request_latency_seconds', 'Request latency in seconds', ['model'])
QUEUE_LENGTH = Gauge('active_requests', 'Active requests in flight')

# Four HuggingFace model tiers — separate K8s services
MODELS = {
    "distilbert": os.getenv("DISTILBERT_URL", "http://nlp-distilbert-service:8001/infer"),
    "bert":       os.getenv("BERT_URL",       "http://nlp-bert-service:8001/infer"),
    "deberta":    os.getenv("DEBERTA_URL",    "http://nlp-deberta-service:8001/infer"),
}
# Bounded semaphore — max 6 real concurrent model calls
LLM_SEMAPHORE = asyncio.Semaphore(6)

http_client: httpx.AsyncClient = None

@app.on_event("startup")
async def startup_event():
    global http_client
    limits = httpx.Limits(max_keepalive_connections=200, max_connections=200)
    http_client = httpx.AsyncClient(timeout=120.0, limits=limits)

@app.on_event("shutdown")
async def shutdown_event():
    await http_client.aclose()

def route_request() -> str:
    active = QUEUE_LENGTH._value.get()
    if active > 12:
        return "distilbert"   # fastest
    elif active > 5:
        return "bert"         # medium
    else:
        return "deberta"      # best quality

@app.post("/generate")
async def generate_text(request: Request):
    data = await request.json()
    prompt = data.get("prompt", "")

    QUEUE_LENGTH.inc()
    start_time = time.time()
    queue_enter_time = time.time()

    try:
        async with LLM_SEMAPHORE:
            queue_wait_sec = time.time() - queue_enter_time

            target_model = route_request()
            target_url = MODELS[target_model]

            try:
                response = await http_client.post(target_url, json={"prompt": prompt})
                response.raise_for_status()
                result = response.json()
            except Exception as e:
                logger.error(f"Error calling {target_model}: {e}")
                raise HTTPException(status_code=502, detail=f"Model {target_model} error: {e}")

        latency = time.time() - start_time
        LATENCY.labels(model=target_model).observe(latency)
        REQUEST_COUNT.labels(model=target_model).inc()

        log_payload = {
            "event": "inference",
            "model": target_model,
            "latency_sec": round(latency, 3),
            "queue_length_at_request": QUEUE_LENGTH._value.get(),
            "queue_wait_sec": round(queue_wait_sec, 3),
            "active_requests": 6 - LLM_SEMAPHORE._value,
            "success": True,
            "request_id": f"{target_model}-{int(time.time()*1000)}",
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
        logger.info(json.dumps(log_payload))

        try:
            await http_client.post("http://logstash-service:5000", json=log_payload, timeout=2.0)
        except Exception:
            pass

        return {
            "model_used": target_model,
            "latency_sec": round(latency, 2),
            "queue_wait_sec": round(queue_wait_sec, 2),
            "response": result.get("response", "")
        }
    finally:
        QUEUE_LENGTH.dec()

@app.get("/metrics")
def get_metrics():
    return Response(content=generate_latest(), media_type="text/plain")

@app.get("/health")
def health_check():
    return {"status": "healthy"}
