"""
Shared HuggingFace NLP Inference Microservice.
The exact model is selected via the MODEL_NAME environment variable.
All four model tiers (DistilBERT, BERT, RoBERTa, DeBERTa) run this same code.
"""
import os
import time
import logging
from fastapi import FastAPI
from transformers import pipeline

MODEL_NAME = os.getenv("MODEL_NAME", "typeform/distilbert-base-uncased-mnli")
SERVICE_TIER = os.getenv("SERVICE_TIER", "distilbert")

CANDIDATE_LABELS = [
    "positive", "negative", "technology", "sports",
    "politics", "science", "entertainment", "business"
]

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(SERVICE_TIER)

app = FastAPI(title=f"NLP Inference — {SERVICE_TIER}")

classifier = None
pipeline_type = None  # "zero-shot" or "nli"

@app.on_event("startup")
def load_model():
    global classifier, pipeline_type
    logger.info(f"Loading model: {MODEL_NAME}")
    try:
        # Try zero-shot first (works for typeform/distilbert-base-uncased-mnli)
        classifier = pipeline(
            "zero-shot-classification",
            model=MODEL_NAME,
            device=-1
        )
        pipeline_type = "zero-shot"
    except Exception:
        # Fall back to NLI text-classification (cross-encoder models)
        from transformers import AutoTokenizer, AutoModelForSequenceClassification
        import torch
        classifier = pipeline(
            "text-classification",
            model=MODEL_NAME,
            device=-1,
            top_k=None
        )
        pipeline_type = "nli"
    logger.info(f"Model {MODEL_NAME} ready. Pipeline type: {pipeline_type}")

@app.post("/infer")
def infer(body: dict):
    text = body.get("prompt", "")
    if not text:
        return {"response": "No prompt provided.", "label": "unknown", "score": 0.0}

    start = time.time()

    if pipeline_type == "zero-shot":
        result = classifier(text, CANDIDATE_LABELS)
        top_label = result["labels"][0]
        top_score = result["scores"][0]
    else:
        # NLI cross-encoder: score each label independently via entailment
        best_label, best_score = "unknown", 0.0
        for lbl in CANDIDATE_LABELS:
            hypothesis = f"This text is about {lbl}."
            out = classifier(f"{text}</s></s>{hypothesis}")
            # NLI labels: ENTAILMENT score is relevance
            for item in out[0]:
                if item["label"].lower() in ("entailment", "label_1"):
                    if item["score"] > best_score:
                        best_score = item["score"]
                        best_label = lbl
        top_label, top_score = best_label, best_score

    elapsed = round(time.time() - start, 3)
    return {
        "response": f"[{SERVICE_TIER.upper()}] Topic: {top_label} — confidence {top_score:.1%}",
        "label": top_label,
        "score": round(top_score, 4),
        "inference_latency_sec": elapsed
    }

@app.get("/health")
def health():
    return {"status": "healthy", "model": MODEL_NAME, "tier": SERVICE_TIER}
