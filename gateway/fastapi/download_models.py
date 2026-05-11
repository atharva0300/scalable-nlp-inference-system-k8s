from transformers import pipeline

print("Downloading toxicity models...")
pipeline("text-classification", model="martin-ha/toxic-comment-model")
pipeline("text-classification", model="unitary/toxic-bert")
pipeline("text-classification", model="unitary/unbiased-toxic-roberta")
print("Models downloaded!")
