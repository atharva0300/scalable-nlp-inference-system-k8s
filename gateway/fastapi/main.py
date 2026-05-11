import anyio
import torch
import time
import json
import logging
import os
import uuid
import httpx
import asyncio
from fastapi import FastAPI
from pydantic import BaseModel
from transformers import pipeline

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("nlp-api")

torch.set_num_threads(1)

ROLE = os.environ.get("ROLE", "router")
MODEL_ID = os.environ.get("MODEL_ID", "") 
POD_NAME = os.environ.get("HOSTNAME", "unknown-pod")

app = FastAPI(title=f"Adaptive Toxicity Platform - {ROLE}")

class ToxicityRequest(BaseModel):
    text: str
    model: str = "adaptive"

def is_toxic_label(label: str) -> bool:
    label = label.lower()
    return label in ["toxic", "severe_toxic", "obscene", "threat", "insult", "identity_hate", "label_1"]

def get_contextual_metadata(text, labels_list):
    disagreement = len(set(labels_list)) > 1
    contextual = False
    if '"' in text or "'" in text:
        contextual = True
    if len(text.split()) > 30 and disagreement:
        contextual = True
    return {"possible_contextual_usage": contextual, "model_disagreement": disagreement}

# WORKER LOGIC
if ROLE == "worker":
    logger.info(f"Loading toxicity model {MODEL_ID} into memory...")
    model_pipeline = pipeline("text-classification", model=MODEL_ID)
    logger.info("Model loaded successfully.")

    class InferRequest(BaseModel):
        text: str

    @app.on_event("startup")
    async def startup_event():
        limiter = anyio.to_thread.current_default_thread_limiter()
        limiter.total_tokens = 2

    @app.post("/infer")
    def infer(req: InferRequest):
        res = model_pipeline(req.text)[0]
        is_tox = is_toxic_label(res["label"])
        return {
            "label": res["label"],
            "confidence": res["score"],
            "is_toxic": is_tox,
            "replica_id": POD_NAME
        }

# ROUTER LOGIC
if ROLE == "router":
    SERVICES = {
        "baseline": "http://toxic-baseline-service:8000/infer",
        "bert": "http://toxic-bert-service:8000/infer",
        "roberta": "http://toxic-roberta-service:8000/infer"
    }
    
    # Adaptive Metrics State
    class ModelStats:
        def __init__(self):
            self.active_requests = 0
            self.avg_latency = 0.5  # Bootstrap with nominal latency
            self.total_requests = 0
            self.timeouts = 0
            self.failures = 0
            self.circuit_open = False
            self.circuit_open_time = 0

        def update_latency(self, latency):
            # EMA for rolling average latency
            self.avg_latency = (self.avg_latency * 0.7) + (latency * 0.3)
            
        def get_score(self):
            if self.circuit_open:
                if time.time() - self.circuit_open_time > 10:  # 10s cooldown
                    self.circuit_open = False
                    self.avg_latency = 0.5 # reset penalty
                else:
                    return 9999.0 # Heavy penalty
            return (self.active_requests * 0.5) + (self.avg_latency * 0.5)

    stats = {
        "baseline": ModelStats(),
        "bert": ModelStats(),
        "roberta": ModelStats()
    }

    async def call_worker(client, model_name, text):
        st = stats[model_name]
        st.active_requests += 1
        st.total_requests += 1
        start_time = time.time()
        
        try:
            r = await client.post(SERVICES[model_name], json={"text": text}, timeout=15.0)
            r.raise_for_status()
            data = r.json()
            lat = time.time() - start_time
            st.update_latency(lat)
            st.active_requests -= 1
            return data
        except httpx.TimeoutException:
            st.timeouts += 1
            st.active_requests -= 1
            st.circuit_open = True
            st.circuit_open_time = time.time()
            raise Exception("Timeout")
        except Exception as e:
            st.failures += 1
            st.active_requests -= 1
            raise Exception(str(e))

    def log_request(latency, req_id, req_text, toxicity, confidence, model_name, path_taken, reason, score, queue_depth):
        log_data = {
            "endpoint": "toxicity",
            "request_id": req_id,
            "model": model_name,
            "latency_sec": latency,
            "text_preview": req_text[:50],
            "toxicity_prediction": toxicity,
            "confidence": confidence,
            "path_taken": path_taken,
            "routing_reason": reason,
            "routing_score": score,
            "queue_depth": queue_depth,
            "type": "nlp_inference_log"
        }
        print(json.dumps(log_data))

    @app.post("/toxicity")
    async def toxicity(req: ToxicityRequest):
        start = time.time()
        req_id = str(uuid.uuid4())
        
        async with httpx.AsyncClient() as client:
            try:
                model_used = req.model
                reason = "direct_request"
                score = 0.0
                
                if req.model == "adaptive":
                    # Find model with lowest routing score
                    scores = {m: stats[m].get_score() for m in SERVICES.keys()}
                    model_used = min(scores, key=scores.get)
                    score = scores[model_used]
                    reason = "adaptive_latency_aware"
                    
                if model_used in SERVICES:
                    try:
                        res = await call_worker(client, model_used, req.text)
                    except Exception as e:
                        # Fallback logic if circuit breaker opened
                        if req.model == "adaptive":
                            scores = {m: stats[m].get_score() for m in SERVICES.keys() if m != model_used}
                            if scores:
                                fallback_model = min(scores, key=scores.get)
                                reason = f"fallback_from_{model_used}"
                                model_used = fallback_model
                                res = await call_worker(client, model_used, req.text)
                            else:
                                raise Exception("All models overloaded")
                        else:
                            raise e

                    lat = round(time.time() - start, 4)
                    tox_level = "high" if res["is_toxic"] else "low"
                    
                    ctx = get_contextual_metadata(req.text, [res["is_toxic"]])
                    
                    log_request(lat, req_id, req.text, tox_level, res["confidence"], model_used, [res["replica_id"]], reason, score, stats[model_used].active_requests)
                    
                    return {
                        "request_id": req_id,
                        "routing": "adaptive" if req.model == "adaptive" else "direct",
                        "routing_reason": reason,
                        "routing_score": round(score, 4),
                        "final_model": model_used,
                        "toxicity": tox_level,
                        "confidence": round(res["confidence"], 4),
                        "possible_contextual_usage": ctx["possible_contextual_usage"],
                        "replica_path": [res["replica_id"]],
                        "active_requests_on_model": stats[model_used].active_requests,
                        "latency_sec": lat
                    }
                else:
                    return {"error": "Invalid model. Use adaptive, baseline, bert, roberta"}
            except Exception as e:
                return {"error": str(e)}

    @app.get("/routing-stats")
    async def get_routing_stats():
        payload = {}
        for m, st in stats.items():
            payload[m] = {
                "routing_score": round(st.get_score(), 4),
                "active_requests": st.active_requests,
                "avg_latency": round(st.avg_latency, 4),
                "total_requests": st.total_requests,
                "timeouts": st.timeouts,
                "failures": st.failures,
                "circuit_open": st.circuit_open
            }
        return {"stats": payload}

@app.get("/health")
async def health():
    return {"status": "healthy", "pod": POD_NAME}