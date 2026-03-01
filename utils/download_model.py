"""
Download the BGE-small-en embedding model to ./models/bge_model
Run once before starting NavAI:  python utils/download_model.py
"""

from sentence_transformers import SentenceTransformer
from pathlib import Path

SAVE_PATH = "./models/bge_model"

print("⬇️  Downloading BAAI/bge-small-en embedding model …")
model = SentenceTransformer("BAAI/bge-small-en")
Path(SAVE_PATH).mkdir(parents=True, exist_ok=True)
model.save(SAVE_PATH)
print(f"✅ Model saved to {SAVE_PATH}")
