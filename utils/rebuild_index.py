"""
rebuild_index.py — Wipe and rebuild ChromaDB from data/chunks.json
Run from project root:  python utils/rebuild_index.py
"""

import json
import shutil
import argparse
from pathlib import Path

from llama_index.core import Document, VectorStoreIndex, StorageContext, Settings
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
import chromadb

# ── Defaults (all relative to project root, not utils/) ──────────────────────
CHUNKS_FILE  = "./data/chunks.json"
EMBED_MODEL  = "./models/bge_model"
CHROMA_PATH  = "./chroma_db"
COLLECTION   = "navai_docs"
BATCH_SIZE   = 64


# ── Load chunks ───────────────────────────────────────────────────────────────

def load_chunks(path: str) -> list[dict]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Chunks file not found: {p.resolve()}")
    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)
    # Support both formats: {"chunks": [...]} or plain [...]
    if isinstance(data, dict):
        chunks = data.get("chunks", [])
    elif isinstance(data, list):
        chunks = data
    else:
        raise ValueError("chunks.json must be a list or a dict with a 'chunks' key.")
    if not chunks:
        raise ValueError("No chunks found in file.")
    return chunks


# ── Convert to LlamaIndex Documents ──────────────────────────────────────────

def chunks_to_documents(chunks: list[dict]) -> list[Document]:
    docs = []
    skipped = 0
    for i, c in enumerate(chunks):
        # The text field in our chunks.json is "text" (not "content")
        text = c.get("text", "").strip()
        if not text:
            print(f"  ⚠️  Skipping chunk {i} ('{c.get('chunk_id', i)}') — empty text field.")
            skipped += 1
            continue

        doc = Document(
            text=text,
            metadata={
                "chunk_id":        c.get("chunk_id", str(i)),
                "title":           c.get("title", ""),
                "act":             c.get("act", ""),
                "chapter":         c.get("chapter", ""),
                "sections_covered": str(c.get("sections_covered", [])),
                "source_pages":    c.get("source_pages", ""),
                "word_count":      str(c.get("word_count", len(text.split()))),
            }
        )
        docs.append(doc)

    if skipped:
        print(f"  ⚠️  Skipped {skipped} chunks with empty text.")
    return docs


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Rebuild NavAI ChromaDB index")
    parser.add_argument("--chunks",  default=CHUNKS_FILE, help="Path to chunks.json")
    parser.add_argument("--model",   default=EMBED_MODEL, help="Path to BGE embedding model")
    parser.add_argument("--chroma",  default=CHROMA_PATH, help="ChromaDB output directory")
    parser.add_argument("--collection", default=COLLECTION, help="ChromaDB collection name")
    args = parser.parse_args()

    # 1. Load chunks
    print(f"📂 Loading chunks from {args.chunks} …")
    chunks = load_chunks(args.chunks)
    print(f"   Loaded {len(chunks)} chunks.")

    # 2. Convert to Documents
    docs = chunks_to_documents(chunks)
    print(f"   Converted to {len(docs)} Document objects.")

    if not docs:
        print("❌ No documents to index — check that your chunks.json has a 'text' field in each chunk.")
        return

    # 3. Load embedding model
    print(f"🧠 Loading embedding model: {args.model} …")
    if not Path(args.model).exists():
        raise FileNotFoundError(
            f"Embedding model not found at '{args.model}'.\n"
            "Run:  python utils/download_model.py"
        )
    embed_model = HuggingFaceEmbedding(model_name=args.model)
    Settings.embed_model = embed_model

    # 4. Wipe old index
    print(f"🗑  Clearing old ChromaDB at '{args.chroma}' …")
    shutil.rmtree(args.chroma, ignore_errors=True)

    # 5. Build new index
    db         = chromadb.PersistentClient(path=args.chroma)
    collection = db.get_or_create_collection(name=args.collection)
    vs         = ChromaVectorStore(chroma_collection=collection)
    sc         = StorageContext.from_defaults(vector_store=vs)

    print(f"🔨 Building index (batch size={BATCH_SIZE}) …")
    VectorStoreIndex.from_documents(
        docs,
        storage_context=sc,
        embed_model=embed_model,
        show_progress=True,
    )

    count = collection.count()
    print(f"✅ Done! Collection '{args.collection}' now has {count} items.")
    print(f"   ChromaDB saved to: {Path(args.chroma).resolve()}")

    if count == 0:
        print("⚠️  WARNING: 0 items indexed. Check your chunks.json 'text' fields.")
    elif count < len(chunks):
        print(f"⚠️  NOTE: {len(chunks) - count} chunks were skipped (empty text).")
    else:
        print("🎉 All chunks indexed successfully — ready to run app.py!")


if __name__ == "__main__":
    main()
