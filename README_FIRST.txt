╔══════════════════════════════════════════════════════════╗
║           NavAI — Legal Information Assistant            ║
║              MGNREGA Specialist · On-Device AI           ║
╚══════════════════════════════════════════════════════════╝

QUICK START  (3 steps, zero configuration)
──────────────────────────────────────────

  1. Extract this ZIP to your Desktop (or anywhere you like).

  2. Double-click the launcher for YOUR operating system:

       Windows  →  run_navai.bat      (double-click)
       Mac      →  run_navai.sh       (right-click → Open  OR  see note below)
       Linux    →  run_navai.sh       (chmod +x then ./run_navai.sh)

  3. Wait for the one-time setup to complete.
     Your browser will open automatically to http://localhost:7860

That's it! 🎉

────────────────────────────────────────────────────────────
FIRST-RUN SETUP (automatic, ~5–10 min depending on internet)
────────────────────────────────────────────────────────────
The launcher script will automatically:

  • Check for / install Python 3.10+
  • Check for / install Ollama  (local LLM runtime)
  • Download llama3.2:3b model  (~2 GB, once only)
  • Download BGE-small-en embedding model  (~130 MB, once only)
  • Create a Python virtual environment
  • Install all Python packages from requirements.txt
  • Open NavAI in your default browser

Subsequent launches take ~15–30 seconds.

────────────────────────────────────────────────────────────
MAC NOTE
────────────────────────────────────────────────────────────
If macOS blocks run_navai.sh, open Terminal and run:

    chmod +x run_navai.sh
    ./run_navai.sh

────────────────────────────────────────────────────────────
WHAT NAVAI DOES
────────────────────────────────────────────────────────────
NavAI is a fully offline RAG (Retrieval-Augmented Generation)
legal assistant trained on the MGNREGA Act, 2005.

  ✓ 100% on-device — no data ever leaves your machine
  ✓ No API keys required
  ✓ Upload additional PDFs to expand the knowledge base
  ✓ Answers questions in plain English with source citations

────────────────────────────────────────────────────────────
REQUIREMENTS
────────────────────────────────────────────────────────────
  • Python 3.10 or higher  (https://python.org/downloads)
  • Ollama                  (installed automatically)
  • ~4 GB free disk space
  • ~8 GB RAM recommended
  • Internet connection for first-time model download

────────────────────────────────────────────────────────────
SUPPORT
────────────────────────────────────────────────────────────
If the launcher fails, run the pre-flight check manually:

    cd app
    python utils/check_installation.py

This will diagnose exactly what is missing.

⚖️ NavAI provides general legal information for educational
   purposes only — not a substitute for professional legal advice.
