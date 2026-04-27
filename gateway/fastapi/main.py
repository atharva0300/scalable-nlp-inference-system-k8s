from fastapi import FastAPI, BackgroundTasks, Request, HTTPException
import httpx
import time
import asyncio
from prometheus_client import Counter, Histogram, Gauge, generate_latest
from fastapi.responses import Response
import logging
import json
import os

app = FastAPI(title="Adaptive LLM Inference Router")

# Configure Logging (JSON format for ELK/Logstash)
logger = logging.getLogger("LLMRouter")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter('{"time": "%(asctime)s", "level": "%(levelname)s", "message": "%(message)s"}')
handler.setFormatter(formatter)
logger.addHandler(handler)

# Prometheus Metrics
REQUEST_COUNT = Counter('request_count', 'Total generate requests', ['model'])
LATENCY = Histogram('request_latency_seconds', 'Request latency in seconds', ['model'])
QUEUE_LENGTH = Gauge('active_requests', 'Number of active requests being processed')

# Model Endpoints (These would be K8s service names)
MODELS = {
    "mistral": os.getenv("MISTRAL_URL", "http://ollama-tinyllama:11434/api/generate"),
    "phi3": os.getenv("PHI3_URL", "http://ollama-tinyllama:11434/api/generate"),
    "tinyllama": os.getenv("TINYLLAMA_URL", "http://ollama-tinyllama:11434/api/generate")
}

# Adaptive Routing Thresholds
HIGH_LOAD_THRESHOLD = int(os.getenv("HIGH_LOAD_THRESHOLD", "10"))
MEDIUM_LOAD_THRESHOLD = int(os.getenv("MEDIUM_LOAD_THRESHOLD", "3"))

async def route_request(prompt: str):
    active_reqs = QUEUE_LENGTH._value.get()
    
    if active_reqs >= HIGH_LOAD_THRESHOLD:
        target_model = "tinyllama"
        logger.info("High load detected. Routing to TinyLlama.")
    elif active_reqs >= MEDIUM_LOAD_THRESHOLD:
        target_model = "phi3"
        logger.info("Medium load detected. Routing to Phi-3 Mini.")
    else:
        target_model = "mistral"
        logger.info("Low load. Routing to Mistral 7B.")
        
    return target_model

# Global HTTP Client to reuse connections and prevent exhaustion
http_client = None

@app.on_event("startup")
async def startup_event():
    global http_client
    # Set high limits for concurrent load testing
    limits = httpx.Limits(max_keepalive_connections=200, max_connections=200)
    http_client = httpx.AsyncClient(timeout=300.0, limits=limits)

@app.on_event("shutdown")
async def shutdown_event():
    await http_client.aclose()

@app.post("/generate")
async def generate_text(request: Request):
    body = await request.json()
    prompt = body.get("prompt", "Hello")
    
    # Increment active requests gauge
    QUEUE_LENGTH.inc()
    start_time = time.time()
    
    target_model = await route_request(prompt)
    target_url = MODELS[target_model]
    
    payload = {
        "model": "tinyllama", # Hardcoded to tinyllama since we removed the other models to save RAM
        "prompt": prompt,
        "stream": False
    }
    
    try:
        response = await http_client.post(target_url, json=payload)
        response.raise_for_status()
        result = response.json()
        
        latency = time.time() - start_time
        LATENCY.labels(model=target_model).observe(latency)
        REQUEST_COUNT.labels(model=target_model).inc()
        
        # Log for ELK
        logger.info(json.dumps({
            "event": "inference",
            "model": target_model,
            "latency_sec": latency,
            "queue_length_at_request": QUEUE_LENGTH._value.get()
        }))
        
        return {
            "model_used": target_model,
            "latency_sec": round(latency, 2),
            "response": result.get("response", "")
        }
        
    except Exception as e:
        logger.error(f"Error calling {target_model}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        QUEUE_LENGTH.dec()

@app.get("/metrics")
def get_metrics():
    return Response(content=generate_latest(), media_type="text/plain")

@app.get("/health")
def health_check():
    return {"status": "healthy"}
