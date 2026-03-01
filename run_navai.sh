#!/usr/bin/env bash
set -euo pipefail

# ─────────────────────────────────────────────────────────────────────────────
#  NavAI – One-Click Launcher  (Mac & Linux)
# ─────────────────────────────────────────────────────────────────────────────

# Always run from the directory this script lives in
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo "  ███╗   ██╗ █████╗ ██╗   ██╗ █████╗ ██╗"
echo "  ████╗  ██║██╔══██╗██║   ██║██╔══██╗██║"
echo "  ██╔██╗ ██║███████║██║   ██║███████║██║"
echo "  ██║╚██╗██║██╔══██║╚██╗ ██╔╝██╔══██║██║"
echo "  ██║ ╚████║██║  ██║ ╚████╔╝ ██║  ██║██║"
echo "  ╚═╝  ╚═══╝╚═╝  ╚═╝  ╚═══╝  ╚═╝  ╚═╝╚═╝"
echo ""
echo "  Legal Information Assistant — MGNREGA Specialist"
echo "  ─────────────────────────────────────────────────"
echo ""

# ─── Helper ──────────────────────────────────────────────────────────────────
open_browser() {
    if command -v xdg-open &>/dev/null; then
        xdg-open "$1" &
    elif command -v open &>/dev/null; then
        open "$1" &
    fi
}

# ─── 1. Python ───────────────────────────────────────────────────────────────
echo "[1/7] Checking Python..."
if ! command -v python3 &>/dev/null; then
    echo ""
    echo "  ERROR: python3 is not installed."
    echo "  Install from https://www.python.org/downloads/"
    echo "  or:  brew install python  /  sudo apt install python3"
    exit 1
fi
PY_VER=$(python3 --version 2>&1)
echo "  OK — $PY_VER"

# ─── 2. Ollama ───────────────────────────────────────────────────────────────
echo ""
echo "[2/7] Checking Ollama..."
if ! command -v ollama &>/dev/null; then
    echo "  Ollama not found. Installing via official script..."
    echo "  (This is ~100 MB and only happens once.)"
    echo ""
    if curl -fsSL https://ollama.com/install.sh | sh; then
        echo "  Ollama installed."
    else
        echo "  ERROR: Automatic install failed."
        echo "  Download manually from: https://ollama.com/download"
        exit 1
    fi
else
    OL_VER=$(ollama --version 2>&1 || true)
    echo "  OK — $OL_VER"
fi

# ─── 3. Ollama service ───────────────────────────────────────────────────────
echo ""
echo "[3/7] Starting Ollama service..."
pkill -f "ollama serve" 2>/dev/null || true
sleep 2
ollama serve > /tmp/ollama_serve.log 2>&1 &
OLLAMA_PID=$!
sleep 4
echo "  OK — Ollama service running (PID $OLLAMA_PID)"

# ─── 4. Pull LLM model ───────────────────────────────────────────────────────
echo ""
echo "[4/7] Checking llama3.2:3b model..."
echo "  (First-time download is ~2 GB. Subsequent runs are instant.)"
echo ""
if ollama pull llama3.2:3b; then
    echo ""
    echo "  OK — llama3.2:3b ready"
else
    echo "  ERROR: Failed to pull llama3.2:3b. Check your internet connection."
    exit 1
fi

# ─── 5. Python environment ───────────────────────────────────────────────────
echo ""
echo "[5/7] Setting up Python environment..."

if [ ! -d "venv" ]; then
    echo "  Creating virtual environment..."
    python3 -m venv venv
fi
# shellcheck disable=SC1091
source venv/bin/activate

echo "  Installing / verifying packages..."
pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet
echo "  OK — All packages installed"

# ─── 6. Embedding model ──────────────────────────────────────────────────────
echo ""
echo "[6/7] Checking embedding model..."
echo "  (First-time download is ~130 MB. Subsequent runs are instant.)"
echo ""
python3 utils/download_model.py || echo "  WARNING: Will retry at startup."

# ─── 7. Build / rebuild ChromaDB index ───────────────────────────────────────
echo ""
echo "[7/7] Building search index..."
if [ ! -d "chroma_db" ]; then
    echo "  No index found — building from data/chunks.json ..."
    python3 utils/rebuild_index.py
else
    echo "  Index already exists — skipping rebuild."
    echo "  (To force a full rebuild, delete the chroma_db folder and re-run.)"
fi

# ─── .env ────────────────────────────────────────────────────────────────────
if [ ! -f ".env" ] && [ -f ".env.example" ]; then
    cp ".env.example" ".env"
    echo "  Created .env from .env.example"
fi

# ─── Launch ──────────────────────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════"
echo "  NavAI is starting..."
echo "  Browser will open automatically in 5 seconds."
echo "  URL: http://localhost:7860"
echo "  Press Ctrl+C to stop NavAI."
echo "═══════════════════════════════════════════════════"
echo ""
sleep 5
open_browser "http://localhost:7860"
python3 app.py
