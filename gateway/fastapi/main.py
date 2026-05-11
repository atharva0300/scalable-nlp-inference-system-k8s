import anyio
import torch
import time
import json
import logging
import os
import uuid
import httpx
import random
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

app = FastAPI(title=f"Distributed Research Platform - {ROLE}")

class ToxicityRequest(BaseModel):
    text: str
    model: str = "auto"

class RoutingModeRequest(BaseModel):
    mode: str 

ROUTING_MODE = "adaptive"

# Production Stabilization State
last_selected_model = "baseline"
last_switch_time = 0.0

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

if ROLE == "router":
    SERVICES = {
        "baseline": "http://toxic-baseline-service:8000/infer",
        "bert": "http://toxic-bert-service:8000/infer",
        "roberta": "http://toxic-roberta-service:8000/infer"
    }
    
    class ModelStats:
        def __init__(self):
            self.active_requests = 0
            self.ewma_latency = 0.5
            self.alpha = 0.2
            self.total_requests = 0
            self.timeouts = 0
            self.failures = 0
            self.circuit_open = False
            self.circuit_open_time = 0

        def update_latency(self, current_latency):
            self.ewma_latency = (self.alpha * current_latency) + ((1 - self.alpha) * self.ewma_latency)
            
        def get_score(self):
            if self.circuit_open:
                if time.time() - self.circuit_open_time > 10:
                    self.circuit_open = False
                    self.ewma_latency = 0.5
                else:
                    return 9999.0
                    
            # Decay penalties naturally so they don't permanently inflate the score
            self.timeouts *= 0.95
            self.failures *= 0.95
            
            failure_penalty = (self.timeouts * 2.0) + (self.failures * 1.0)
            return (self.ewma_latency * 0.7) + (self.active_requests * 0.3) + failure_penalty

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

    def log_request(latency, req_id, req_text, toxicity, confidence, model_name, path_taken, reason, score, queue_depth, mode, ewma):
        log_data = {
            "endpoint": "toxicity",
            "request_id": req_id,
            "routing_strategy": mode,
            "model": model_name,
            "latency_sec": latency,
            "ewma_latency": ewma,
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

    @app.post("/routing-mode")
    async def set_routing_mode(req: RoutingModeRequest):
        global ROUTING_MODE
        if req.mode in ["adaptive", "static"]:
            ROUTING_MODE = req.mode
            return {"status": "success", "mode": ROUTING_MODE}
        return {"error": "Mode must be 'adaptive' or 'static'"}

    @app.post("/toxicity")
    async def toxicity(req: ToxicityRequest):
        global last_selected_model, last_switch_time
        
        start = time.time()
        req_id = str(uuid.uuid4())
        
        async with httpx.AsyncClient() as client:
            try:
                model_used = req.model
                reason = "direct_request"
                score = 0.0
                prev_model = last_selected_model
                
                if req.model == "auto":
                    if ROUTING_MODE == "adaptive":
                        scores = {m: stats[m].get_score() for m in SERVICES.keys()}
                        best_model = min(scores, key=scores.get)
                        best_score = scores[best_model]
                        
                        current_model = last_selected_model
                        current_score = scores.get(current_model, 9999.0)
                        
                        time_since_switch = time.time() - last_switch_time
                        
                        if time_since_switch < 3.0:
                            model_used = current_model
                            score = current_score
                            reason = "adaptive_cooldown_active"
                        else:
                            if current_model == best_model:
                                model_used = best_model
                                score = best_score
                                reason = "adaptive_best_unchanged"
                            else:
                                diff_ratio = (current_score - best_score) / max(current_score, 0.001)
                                if diff_ratio > 0.15:
                                    model_used = best_model
                                    score = best_score
                                    reason = "adaptive_hysteresis_switch"
                                    last_selected_model = model_used
                                    last_switch_time = time.time()
                                else:
                                    model_used = current_model
                                    score = current_score
                                    reason = "adaptive_hysteresis_keep"
                    else:
                        rand_val = random.random()
                        if rand_val < 0.5:
                            model_used = "baseline"
                        elif rand_val < 0.8:
                            model_used = "bert"
                        else:
                            model_used = "roberta"
                        score = stats[model_used].get_score()
                        reason = "static_weighted_round_robin"
                        last_selected_model = model_used
                    
                if model_used in SERVICES:
                    try:
                        res = await call_worker(client, model_used, req.text)
                    except Exception as e:
                        if req.model == "auto":
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
                    
                    log_request(lat, req_id, req.text, tox_level, res["confidence"], model_used, [res["replica_id"]], reason, score, stats[model_used].active_requests, ROUTING_MODE, stats[model_used].ewma_latency)
                    
                    return {
                        "request_id": req_id,
                        "routing_mode": ROUTING_MODE,
                        "routing_reason": reason,
                        "routing_score": round(score, 4),
                        "previous_model": prev_model,
                        "final_model": model_used,
                        "ewma_latency": round(stats[model_used].ewma_latency, 4),
                        "toxicity": tox_level,
                        "confidence": round(res["confidence"], 4),
                        "replica_path": [res["replica_id"]],
                        "active_requests_on_model": stats[model_used].active_requests,
                        "latency_sec": lat
                    }
                else:
                    return {"error": "Invalid model."}
            except Exception as e:
                return {"error": str(e)}

    @app.get("/routing-stats")
    async def get_routing_stats():
        payload = {}
        for m, st in stats.items():
            payload[m] = {
                "routing_score": round(st.get_score(), 4),
                "active_requests": st.active_requests,
                "ewma_latency": round(st.ewma_latency, 4),
                "total_requests": st.total_requests,
                "timeouts": st.timeouts,
                "failures": st.failures,
                "circuit_open": st.circuit_open
            }
        return {"mode": ROUTING_MODE, "stats": payload, "last_switch_time": last_switch_time, "last_selected_model": last_selected_model}

@app.get("/health")
async def health():
    return {"status": "healthy", "pod": POD_NAME}