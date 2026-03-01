"""
NavAI – Pre-flight Installation Checker
Validates that all required components are present before launching.
Prints a human-readable health report and exits with code 1 if critical items are missing.
"""

import sys
import subprocess
import importlib
from pathlib import Path

REQUIRED_PACKAGES = [
    ("gradio",            "gradio"),
    ("llama_index.core",  "llama-index"),
    ("chromadb",          "chromadb"),
    ("sentence_transformers", "sentence-transformers"),
    ("pypdf",             "pypdf"),
    ("dotenv",            "python-dotenv"),
]

EMBED_MODEL_PATH = Path(__file__).parent.parent / "models" / "bge_model"
CHUNKS_FILE      = Path(__file__).parent.parent / "data" / "chunks_improved.json"

ok = True

print("=" * 52)
print("  NavAI Pre-flight Check")
print("=" * 52)

# Python version
ver = sys.version_info
if ver.major == 3 and ver.minor >= 10:
    print(f"✅  Python {ver.major}.{ver.minor}.{ver.micro}")
else:
    print(f"⚠️  Python {ver.major}.{ver.minor}.{ver.micro}  (3.10+ recommended)")

# Python packages
print("\n── Python packages ──────────────────────────")
for module, pkg in REQUIRED_PACKAGES:
    try:
        importlib.import_module(module)
        print(f"✅  {pkg}")
    except ImportError:
        print(f"❌  {pkg}  ← missing (run: pip install {pkg})")
        ok = False

# Ollama
print("\n── Ollama ────────────────────────────────────")
try:
    result = subprocess.run(["ollama", "--version"], capture_output=True, text=True, timeout=5)
    if result.returncode == 0:
        ver_str = result.stdout.strip() or result.stderr.strip()
        print(f"✅  Ollama installed  ({ver_str})")
    else:
        print("❌  Ollama not found — download from https://ollama.com")
        ok = False
except FileNotFoundError:
    print("❌  Ollama not found — download from https://ollama.com")
    ok = False
except Exception as e:
    print(f"⚠️  Ollama check failed: {e}")

# Llama model
print("\n── LLM model ─────────────────────────────────")
try:
    result = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=10)
    if "llama3.2" in result.stdout:
        print("✅  llama3.2:3b is pulled")
    else:
        print("⚠️  llama3.2:3b not found — will be pulled automatically on first run")
except Exception:
    print("⚠️  Could not check Ollama model list")

# Embedding model
print("\n── Embedding model ───────────────────────────")
if (EMBED_MODEL_PATH / "config.json").exists():
    print(f"✅  BGE model at {EMBED_MODEL_PATH}")
else:
    print(f"⚠️  BGE model not found — will be downloaded automatically on first run")

# Knowledge base
print("\n── Knowledge base ────────────────────────────")
if CHUNKS_FILE.exists():
    import json
    with open(CHUNKS_FILE, encoding="utf-8") as f:
        chunks = json.load(f)
    print(f"✅  chunks_improved.json  ({len(chunks)} chunks)")
else:
    print(f"⚠️  {CHUNKS_FILE} not found — index will be empty until a PDF is uploaded")

print("\n" + "=" * 52)
if ok:
    print("🚀  All critical checks passed — ready to launch!")
else:
    print("❌  Some components are missing. Run the launcher script to fix them automatically.")
print("=" * 52 + "\n")

sys.exit(0 if ok else 1)
