# ⚖️ NavAI — Local RAG Legal Information Assistant

> **Fully local** · **No API keys** · **Privacy-first** · **MGNREGA specialist**

NavAI is a Retrieval-Augmented Generation (RAG) system that makes Indian legal information accessible to ordinary citizens. It runs entirely on your machine using local models — no data ever leaves your device.

---

## 🗂 Project Structure

```
NavAI/
├── app.py                   # 🖥  Gradio web frontend (run this)
├── rag_engine.py            # 🧠  Core RAG backend
├── requirements.txt         # 📦  Python dependencies
├── .env.example             # ⚙️  Environment variable template
│
├── data/
│   └── chunks_improved.json # 📄  Pre-chunked MGNREGA Act text
│       (place your chunks JSON here, or generate via utils/rechunk.py)
│
├── models/
│   └── bge_model/           # 🤖  BGE-small-en embedding model
│       (auto-downloaded by utils/download_model.py)
│
├── chroma_db/               # 💾  ChromaDB vector store (auto-created)
│
└── utils/
    ├── download_model.py    # ⬇️  One-time model download
    ├── rechunk.py           # ✂️  PDF → chunks JSON
    ├── rebuild_index.py     # 🔨  Rebuild ChromaDB from chunks
    ├── checkchunks.py       # 🔍  Debug: search chunks by keyword
    └── cli_query.py         # 💬  CLI interface (no Gradio)
```

---

## 🚀 Quick Start

### 1. Prerequisites

- Python 3.10+
- [Ollama](https://ollama.ai) installed and running

```bash
# Install Ollama then pull the LLM
ollama pull llama3.2:3b
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Download the embedding model

```bash
python utils/download_model.py
```

### 4. Prepare the knowledge base

**Option A — Use your pre-built `chunks_improved.json`:**

Copy your `chunks_improved.json` into the `data/` folder. Then build the index:
```bash
python utils/rebuild_index.py
```

**Option B — Start from a raw PDF:**

```bash
python utils/rechunk.py --pdf path/to/mgnrega_act.pdf
python utils/rebuild_index.py
```

### 5. Launch NavAI

```bash
python app.py
```

Open [http://localhost:7860](http://localhost:7860) in your browser.

---

## ⚙️ Configuration

Copy `.env.example` to `.env` and adjust as needed:

```env
NAVAI_EMBED_MODEL=./models/bge_model
NAVAI_LLM_MODEL=llama3.2:3b
NAVAI_CHROMA_PATH=./chroma_db
NAVAI_COLLECTION=navai_docs
NAVAI_CHUNKS_FILE=./data/chunks_improved.json
NAVAI_TOP_K=15
NAVAI_TIMEOUT=120.0
```

---

## 📄 Adding More Documents

Upload any legal PDF directly through the **Upload Documents** tab in the web UI.
NavAI will automatically:

1. Extract text from all pages
2. Split at legal section boundaries (max 500 words, 50-word overlap)
3. Embed each chunk using BGE-small-en
4. Store in ChromaDB
5. Make it queryable immediately

---

## 🏗 Architecture

```
User Question
     │
     ▼
Gradio Frontend (app.py)
     │
     ▼
NavAIEngine.query()  (rag_engine.py)
     │
     ├─► Embed question  ──► BGE-small-en (local)
     │
     ├─► Retrieve top-15 ──► ChromaDB (local)
     │       chunks
     │
     └─► Generate answer ──► Ollama / llama3.2:3b (local)
              │
              ▼
         Answer + Sources
              │
              ▼
     Gradio Chat Interface
```

---

## ⚠️ Legal Disclaimer

NavAI provides general legal **information** for educational and awareness purposes only. It is **not** a substitute for professional legal advice. For specific legal matters, consult a qualified advocate or legal aid service.

---

*Built for hackathon demonstration. All AI processing is local and private.*
