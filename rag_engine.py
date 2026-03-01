"""
NavAI RAG Engine  (improved)
-----------------------------
Core backend: loads chunks.json (with metadata), builds/loads vector index,
handles queries, and processes new uploaded PDFs.

Key improvements over original:
  • Properly loads chunks.json dict format — preserves title/section_ref/category/keywords
  • Metadata stored in ChromaDB — enables category filtering
  • TOP_K=8 retrieval then score-filtered to top 4 for better accuracy without slowdown
  • Clean plain-language response prompt (no QUOTE/ANSWER markers)
  • Nuclear response output is parsed before returning to app
  • Source display uses chunk title + section_ref from metadata
  • Consistent query path (no bypass of query engine)
"""

import os
import json
import shutil
import re
import logging
import time
from pathlib import Path
from typing import Optional, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("NavAI")

# ── Optional imports ──────────────────────────────────────────────────────────
try:
    from pypdf import PdfReader
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False
    logger.warning("pypdf not installed – PDF upload will be disabled.")

try:
    import pytesseract
    from PIL import Image
    import pdf2image
    OCR_SUPPORT = True
except ImportError:
    OCR_SUPPORT = False
    logger.warning("OCR dependencies not installed – install: pip install pytesseract pillow pdf2image")

try:
    from llama_index.core import Document, VectorStoreIndex, Settings, StorageContext
    from llama_index.core import PromptTemplate
    from llama_index.vector_stores.chroma import ChromaVectorStore
    from llama_index.embeddings.huggingface import HuggingFaceEmbedding
    from llama_index.llms.ollama import Ollama
    import chromadb
    LLAMA_OK = True
except ImportError as e:
    LLAMA_OK = False
    logger.error(f"LlamaIndex / ChromaDB import failed: {e}")

try:
    from llama_index.postprocessor.cohere_rerank import CohereRerank
    COHERE_AVAILABLE = True
except ImportError:
    COHERE_AVAILABLE = False

# ── Configuration ─────────────────────────────────────────────────────────────
EMBED_MODEL_PATH = os.getenv("NAVAI_EMBED_MODEL",  "./models/bge_model")
OLLAMA_MODEL     = os.getenv("NAVAI_LLM_MODEL",    "llama3.2:3b")
CHROMA_PATH      = os.getenv("NAVAI_CHROMA_PATH",  "./chroma_db")
COLLECTION_NAME  = os.getenv("NAVAI_COLLECTION",   "navai_docs")
CHUNKS_FILE      = os.getenv("NAVAI_CHUNKS_FILE",  "./data/chunks.json")   # fixed: was chunks_improved.json
TOP_K_RETRIEVE   = int(os.getenv("NAVAI_TOP_K",    "8"))   # retrieve more, filter after
TOP_K_FINAL      = int(os.getenv("NAVAI_TOP_K_FINAL", "4")) # final context sent to LLM
OLLAMA_TIMEOUT   = float(os.getenv("NAVAI_TIMEOUT","45.0"))
MAX_CHUNK_WORDS  = int(os.getenv("NAVAI_CHUNK_WORDS", "500"))
CHUNK_OVERLAP    = int(os.getenv("NAVAI_CHUNK_OVERLAP", "50"))
TESSERACT_CMD    = os.getenv("TESSERACT_CMD", "tesseract")
OCR_LANGUAGES    = os.getenv("OCR_LANGUAGES", "hin+eng")
OCR_DPI          = int(os.getenv("OCR_DPI", "300"))
COHERE_API_KEY   = os.getenv("COHERE_API_KEY", "")
COHERE_TOP_N     = int(os.getenv("COHERE_TOP_N", "4"))

# Allowed metadata value types for ChromaDB
_CHROMA_TYPES = (str, int, float, bool)


# ── Helpers ───────────────────────────────────────────────────────────────────

def sanitize_metadata(meta: dict) -> dict:
    """ChromaDB only accepts str/int/float/bool values — serialize lists etc."""
    clean = {}
    for k, v in meta.items():
        if isinstance(v, _CHROMA_TYPES):
            clean[k] = v
        elif isinstance(v, list):
            clean[k] = ", ".join(str(i) for i in v)
        elif v is None:
            pass  # skip None values
        else:
            clean[k] = str(v)
    return clean


def load_chunks_file(path: str) -> list[dict]:
    """
    Load chunks.json. Supports two formats:
      {"chunks": [...], "metadata": {...}}   ← our chunk_mgnrega.py format
      [...]                                  ← plain list
    Each item must be a dict with at least a 'content' key.
    Returns list of dicts.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Chunks file not found: {p.resolve()}")
    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        chunks = data.get("chunks", [])
    elif isinstance(data, list):
        chunks = data
    else:
        raise ValueError("chunks.json must be a list or a dict with a 'chunks' key.")
    if not chunks:
        raise ValueError("No chunks found in file.")
    return chunks


def chunks_to_documents(chunks, source_tag: str = "") -> list:
    """
    Convert chunks to LlamaIndex Documents.
    Accepts two chunk formats:
      • dict  — from chunks.json  (has 'text', 'title', 'act', etc.)
      • str   — from improved_chunking() used during PDF ingestion
    """
    docs = []
    for i, c in enumerate(chunks):
        if isinstance(c, str):
            # Plain-text chunk from PDF ingestion pipeline
            doc = Document(
                text=c,
                metadata={
                    "chunk_id":    f"{source_tag}_{i}" if source_tag else str(i),
                    "title":       "",
                    "act":         source_tag,
                    "chapter":     "",
                    "source_pages": "",
                    "word_count":  str(len(c.split())),
                }
            )
        else:
            # Rich dict chunk from chunks.json
            doc = Document(
                text=c["text"],
                metadata={
                    "chunk_id":       c.get("chunk_id", ""),
                    "title":          c.get("title", ""),
                    "act":            c.get("act", ""),
                    "chapter":        c.get("chapter", ""),
                    "sections_covered": str(c.get("sections_covered", [])),
                    "source_pages":   c.get("source_pages", ""),
                    "word_count":     str(c.get("word_count", "")),
                }
            )
        docs.append(doc)
    return docs


def parse_llm_response(raw: str) -> str:
    """
    If the LLM returns QUOTE/ANSWER format, extract just the ANSWER part.
    Otherwise return the full response cleaned up.
    """
    # Handle QUOTE: ... ANSWER: ... format
    if "ANSWER:" in raw:
        answer_part = raw.split("ANSWER:", 1)[-1].strip()
        return answer_part
    # Handle "I don't have information" passthrough
    if "don't have information" in raw.lower() or "not in the context" in raw.lower():
        return raw.strip()
    return raw.strip()


# ── Text extraction & chunking ────────────────────────────────────────────────

def extract_text_from_pdf(pdf_path: str) -> str:
    """Return all text from a PDF file, using OCR fallback if needed."""
    if not PDF_SUPPORT and not OCR_SUPPORT:
        raise RuntimeError("Neither pypdf nor OCR dependencies installed.")

    if PDF_SUPPORT:
        try:
            reader = PdfReader(pdf_path)
            pages = [page.extract_text() or "" for page in reader.pages]
            direct_text = "\n".join(pages)
            if len(direct_text.strip()) > 100:
                logger.info("✅ Text extracted directly from PDF.")
                return direct_text
            logger.info("ℹ️  Direct extraction yielded little text — trying OCR.")
        except Exception as e:
            logger.warning(f"Direct PDF extraction failed: {e} — trying OCR.")

    if OCR_SUPPORT:
        return _extract_text_with_ocr(pdf_path)
    raise RuntimeError("OCR support is not installed and direct PDF extraction failed.")


def _extract_text_with_ocr(pdf_path: str) -> str:
    if TESSERACT_CMD != "tesseract":
        pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD
    logger.info(f"🖼️  Converting PDF to images (DPI={OCR_DPI}, lang={OCR_LANGUAGES}) …")
    images = pdf2image.convert_from_path(pdf_path, dpi=OCR_DPI)
    extracted = []
    for i, img in enumerate(images):
        logger.info(f"🔍 OCR page {i+1}/{len(images)}")
        if img.mode != "L":
            img = img.convert("L")
        try:
            text = pytesseract.image_to_string(img, lang=OCR_LANGUAGES, config="--psm 6")
        except pytesseract.TesseractError:
            text = pytesseract.image_to_string(img, lang="eng")
        extracted.append(f"[Page {i+1}]\n{text}")
    return "\n\n".join(extracted)


def improved_chunking(text: str, max_words: int = MAX_CHUNK_WORDS,
                      overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text at legal section boundaries, enforce max word ceiling with overlap."""
    text = re.sub(r"\n+", "\n", text)
    text = re.sub(r"Page \d+", "", text, flags=re.IGNORECASE)
    text = re.sub(r"पृष्ठ \d+", "", text)

    sections = re.split(
        r"(?=\n\s*\d+\.|\n\s*Section\s+\d+|\n\s*CHAPTER\s+[IVX]+|\n\s*SCHEDULE\s+[IVX]+"
        r"|\n\s*खंड\s+\d+|\n\s*अध्याय\s+[IVX]+)",
        text,
    )

    chunks, current_chunk, current_wc = [], "", 0
    for sec in sections:
        sec = sec.strip()
        if not sec:
            continue
        words = sec.split()
        if current_wc + len(words) > max_words and current_wc > 0:
            chunks.append(current_chunk.strip())
            overlap_words = current_chunk.split()[-overlap:]
            current_chunk = " ".join(overlap_words)
            current_wc = len(overlap_words)
        current_chunk += " " + sec
        current_wc += len(words)

    if current_chunk.strip():
        chunks.append(current_chunk.strip())
    return chunks


# ── Prompt ────────────────────────────────────────────────────────────────────

QA_PROMPT = PromptTemplate(
    "You are NavAI, a plain-language specialist for the MGNREGA Act 2005.\n"
    "Answer the question using ONLY the CONTEXT below.\n"
    "Be direct and specific — include section numbers, amounts, and timeframes if present.\n"
    "If the answer is not in the context, say: 'That information is not available in the loaded documents.'\n\n"
    "CONTEXT:\n{context_str}\n\n"
    "QUESTION: {query_str}\n\n"
    "ANSWER:"
) if LLAMA_OK else None


# ── Main Engine ───────────────────────────────────────────────────────────────

class NavAIEngine:
    """
    Full RAG pipeline:
      • Local HuggingFace BGE embeddings
      • ChromaDB persistent vector store  (with metadata)
      • Ollama LLM (local, zero temperature)
      • Optional Cohere reranker
      • PDF ingestion with OCR fallback
    """

    def __init__(self):
        self.index         = None
        self.embed_model   = None
        self.llm           = None
        self.collection    = None
        self.reranker      = None
        self.ready         = False
        self._status_log   = []

        if OCR_SUPPORT:
            self._verify_tesseract()

    # ── internal ──────────────────────────────────────────────────────────────

    def _log(self, msg: str):
        logger.info(msg)
        self._status_log.append(msg)

    def _verify_tesseract(self):
        try:
            if TESSERACT_CMD != "tesseract":
                pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD
            langs = pytesseract.get_languages()
            logger.info(f"✅ Tesseract found. Languages: {langs}")
            if "hin" not in langs:
                logger.warning("⚠️  Hindi pack missing. Install: sudo apt install tesseract-ocr-hin")
        except Exception as e:
            logger.error(f"❌ Tesseract check failed: {e}")

    def _load_embed_model(self):
        self._log(f"Loading embedding model from {EMBED_MODEL_PATH} …")
        if not Path(EMBED_MODEL_PATH).exists():
            raise FileNotFoundError(
                f"Embedding model not found at '{EMBED_MODEL_PATH}'.\n"
                "Run:  python utils/download_model.py"
            )
        self.embed_model = HuggingFaceEmbedding(model_name=EMBED_MODEL_PATH)
        Settings.embed_model = self.embed_model
        self._log("✅ Embedding model loaded.")

    def _load_llm(self):
        self._log(f"Connecting to Ollama ({OLLAMA_MODEL}) …")
        self.llm = Ollama(
            model=OLLAMA_MODEL,
            request_timeout=OLLAMA_TIMEOUT,
            temperature=0.0,
            context_window=4096,
        )
        Settings.llm = self.llm
        self._log("✅ LLM connected.")

    def _setup_reranker(self):
        if not COHERE_AVAILABLE:
            self._log("ℹ️  Cohere reranker not installed.")
            return
        if not COHERE_API_KEY:
            self._log("ℹ️  COHERE_API_KEY not set — skipping reranker.")
            return
        try:
            self.reranker = CohereRerank(api_key=COHERE_API_KEY, top_n=COHERE_TOP_N)
            self._log(f"✅ Cohere reranker ready (top_n={COHERE_TOP_N}).")
        except Exception as e:
            self._log(f"⚠️  Cohere reranker failed: {e}")

    def _connect_chroma(self):
        db = chromadb.PersistentClient(path=CHROMA_PATH)
        self.collection = db.get_or_create_collection(name=COLLECTION_NAME)
        self._log(f"✅ ChromaDB ready — {self.collection.count()} items in '{COLLECTION_NAME}'.")
        return db

    def _build_index(self):
        """Build VectorStoreIndex from existing ChromaDB collection."""
        vs = ChromaVectorStore(chroma_collection=self.collection)
        self.index = VectorStoreIndex.from_vector_store(vs, embed_model=self.embed_model)
        self._log("✅ Index built from existing collection.")

    # ── public API ────────────────────────────────────────────────────────────

    def initialize(self) -> tuple[bool, str]:
        if not LLAMA_OK:
            return False, "❌ Required libraries missing. See requirements.txt."
        try:
            start = time.time()
            self._load_embed_model()
            self._load_llm()
            self._setup_reranker()
            self._connect_chroma()

            if self.collection.count() == 0:
                self._log(f"Collection empty — seeding from {CHUNKS_FILE} …")
                self._ingest_chunks_file(CHUNKS_FILE)
            else:
                self._build_index()

            self.ready = True
            self._log(f"✅ Ready in {time.time() - start:.1f}s")
            return True, "\n".join(self._status_log)
        except Exception as e:
            msg = f"❌ Initialization failed: {e}"
            self._log(msg)
            return False, msg

    def query(self, question: str) -> dict:
        """
        RAG query:
          1. Embed the question
          2. Retrieve TOP_K_RETRIEVE candidates from ChromaDB
          3. Keep TOP_K_FINAL highest-scoring nodes
          4. Generate answer with LLM using clean QA prompt
          5. Return answer + rich source metadata
        """
        if not self.ready or self.index is None:
            return {"answer": "", "sources": [], "error": "Engine not initialized."}
        try:
            start = time.time()

            # Retrieve more than needed, then trim to best
            retriever = self.index.as_retriever(similarity_top_k=TOP_K_RETRIEVE)
            nodes = retriever.retrieve(question)

            # Optional: apply Cohere reranker
            if self.reranker:
                from llama_index.core.schema import QueryBundle
                nodes = self.reranker.postprocess_nodes(
                    nodes, query_bundle=QueryBundle(query_str=question)
                )

            # Keep top final nodes
            top_nodes = nodes[:TOP_K_FINAL]

            # Build context from node texts
            context = "\n\n---\n\n".join(n.node.text for n in top_nodes)

            # Generate answer
            formatted_prompt = QA_PROMPT.format(
                context_str=context,
                query_str=question,
            )
            raw_answer = str(self.llm.complete(formatted_prompt))
            answer = parse_llm_response(raw_answer)

            # Build rich source list using stored metadata
            sources = []
            for node in top_nodes:
                meta = node.node.metadata or {}
                sources.append({
                    "text":         node.node.text[:400] + ("…" if len(node.node.text) > 400 else ""),
                    "score":        round(node.score, 3) if node.score else 0,
                    # Rich fields from our chunks.json
                    "title":        meta.get("title", ""),
                    "chapter":      meta.get("chapter", ""),
                    "act":          meta.get("act", ""),
                    "source_pages": meta.get("source_pages", ""),
                })

            elapsed = time.time() - start
            logger.info(f"⏱️  Query in {elapsed:.2f}s  |  nodes={len(top_nodes)}")
            return {"answer": answer, "sources": sources, "error": None}

        except Exception as e:
            logger.exception("Query error")
            return {"answer": "", "sources": [], "error": str(e)}

    # ── ingestion ─────────────────────────────────────────────────────────────

    def _ingest_chunks_file(self, path: str):
        """Seed ChromaDB from a pre-built chunks JSON file (preserves all metadata)."""
        try:
            chunks = load_chunks_file(path)
        except (FileNotFoundError, ValueError) as e:
            self._log(f"⚠️  {e} — starting with empty collection.")
            self._build_index()
            return

        self._log(f"📂 Loaded {len(chunks)} chunks from {path}.")
        docs = chunks_to_documents(chunks, source_tag="preloaded")
        self._index_documents(docs)

    def _index_documents(self, docs: list[Document]):
        """Embed and store documents into ChromaDB, then rebuild the index."""
        vs = ChromaVectorStore(chroma_collection=self.collection)
        sc = StorageContext.from_defaults(vector_store=vs)
        self._log(f"🔨 Indexing {len(docs)} documents …")
        self.index = VectorStoreIndex.from_documents(
            docs,
            storage_context=sc,
            embed_model=self.embed_model,
            show_progress=True,
        )
        self._log(f"✅ Indexed {len(docs)} docs. Collection size: {self.collection.count()}")

    def ingest_pdf(self, pdf_path: str) -> tuple[bool, str]:
        """Full pipeline: PDF → text (OCR fallback) → chunks → embed → store."""
        if not self.ready:
            return False, "Engine not ready."
        try:
            self._log(f"📄 Processing {pdf_path} …")
            raw_text = extract_text_from_pdf(pdf_path)
            if not raw_text.strip():
                return False, "No text extracted from PDF."

            chunks = improved_chunking(raw_text)
            self._log(f"✂️  Created {len(chunks)} chunks.")
            docs = chunks_to_documents(chunks, source_tag=Path(pdf_path).name)
            self._index_documents(docs)
            return True, f"✅ Ingested '{Path(pdf_path).name}' → {len(chunks)} chunks added."
        except Exception as e:
            logger.exception("PDF ingestion error")
            return False, f"❌ Ingestion failed: {e}"

    def set_ocr_language(self, languages: str):
        global OCR_LANGUAGES
        OCR_LANGUAGES = languages
        self._log(f"🔤 OCR language set to: {languages}")

    def get_stats(self) -> dict:
        return {
            "ready":            self.ready,
            "collection":       COLLECTION_NAME,
            "doc_count":        self.collection.count() if self.collection else 0,
            "llm_model":        OLLAMA_MODEL,
            "embed_model":      EMBED_MODEL_PATH,
            "top_k":            f"{TOP_K_RETRIEVE} retrieve → {TOP_K_FINAL} to LLM",
            "reranker":         "Cohere" if self.reranker else "None",
            "ocr_supported":    OCR_SUPPORT,
            "ocr_languages":    OCR_LANGUAGES if OCR_SUPPORT else "N/A",
            "pdf_direct":       PDF_SUPPORT,
        }
