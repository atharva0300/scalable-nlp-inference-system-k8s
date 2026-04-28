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

async def route_request(prompt: str) -> str:
    # SPE PATTERN: Adaptive Load Balancing
    active_reqs = QUEUE_LENGTH._value.get()
    
    if active_reqs > 10:
        return "tinyllama"
    elif active_reqs >= 5:
        return "phi3"
    else:
        return "mistral"

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

CACHE = {}
CACHE_LOCKS = {}

@app.post("/generate")
async def generate_text(request: Request):
    body = await request.json()
    prompt = body.get("prompt", "Hello")
    
    # Increment active requests gauge
    QUEUE_LENGTH.inc()
    start_time = time.time()
    
LLM_SEMAPHORE = asyncio.Semaphore(6)

@app.post("/generate")
async def generate_text(request: Request):
    data = await request.json()
    prompt = data.get("prompt", "")
    
    QUEUE_LENGTH.inc()
    start_time = time.time()
    
    # SPE PATTERN: Queue wait time tracking
    queue_enter_time = time.time()
    
    async with LLM_SEMAPHORE:
        queue_wait_sec = time.time() - queue_enter_time
        
        target_model = await route_request(prompt)
        target_url = MODELS[target_model]
        
        # Determine exact model constraints
        constrained_prompt = f"Answer in one short sentence only: {prompt}"
        
        payload = {
            "model": target_model, 
            "prompt": constrained_prompt,
            "stream": False,
            "options": {
                "num_predict": 8,
                "temperature": 0.1,
                "top_p": 0.3
            }
        }
        
        try:
            response = await http_client.post(target_url, json=payload)
            response.raise_for_status()
            result = response.json()
        except Exception as e:
            QUEUE_LENGTH.dec()
            logger.error(f"Error calling {target_model}: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
    
    QUEUE_LENGTH.dec()
    
    latency = time.time() - start_time
    LATENCY.labels(model=target_model).observe(latency)
    REQUEST_COUNT.labels(model=target_model).inc()
    
    # Log for ELK (Upgraded fields per user request)
    log_payload = {
        "event": "inference",
        "model": target_model,
        "latency_sec": round(latency, 3),
        "queue_length_at_request": QUEUE_LENGTH._value.get(),
        "queue_wait_sec": round(queue_wait_sec, 3),
        "active_requests": 6 - LLM_SEMAPHORE._value,
        "success": True,
        "request_id": str(time.time()),
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }
    logger.info(json.dumps(log_payload))
    
    # Send to Logstash synchronously to ensure Kibana receives it before request ends
    try:
        await http_client.post("http://logstash-service:5000", json=log_payload, timeout=2.0)
    except Exception as e:
        pass # Ignore logstash errors so it doesn't break inference
    
    return {
        "model_used": target_model,
        "latency_sec": round(latency, 2),
        "queue_wait_sec": round(queue_wait_sec, 2),
        "response": result.get("response", "")
    }


@app.get("/metrics")
def get_metrics():
    return Response(content=generate_latest(), media_type="text/plain")

@app.get("/health")
def health_check():
    return {"status": "healthy"}
