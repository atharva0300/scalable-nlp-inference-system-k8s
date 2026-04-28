import os
from transformers import pipeline

model_name = os.getenv("MODEL_NAME")
print(f"Pre-downloading model: {model_name}")

try:
    print("Attempting zero-shot-classification pipeline...")
    pipeline("zero-shot-classification", model=model_name, device=-1)
except Exception as e:
    print(f"Zero-shot failed: {e}. Falling back to text-classification...")
    pipeline("text-classification", model=model_name, device=-1, top_k=None)

print("Pre-download complete.")
