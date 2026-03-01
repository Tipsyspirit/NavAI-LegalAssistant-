@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion

cls
echo.
echo  ███╗   ██╗ █████╗ ██╗   ██╗ █████╗ ██╗
echo  ████╗  ██║██╔══██╗██║   ██║██╔══██╗██║
echo  ██╔██╗ ██║███████║██║   ██║███████║██║
echo  ██║╚██╗██║██╔══██║╚██╗ ██╔╝██╔══██║██║
echo  ██║ ╚████║██║  ██║ ╚████╔╝ ██║  ██║██║
echo  ╚═╝  ╚═══╝╚═╝  ╚═╝  ╚═══╝  ╚═╝  ╚═╝╚═╝
echo.
echo  Legal Information Assistant — MGNREGA Specialist
echo  ─────────────────────────────────────────────────
echo.

:: ─── Always run from the folder this .bat file lives in ─────────────────────
cd /d "%~dp0"

:: ─── 1. Check Python ─────────────────────────────────────────────────────────
echo [1/7] Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo  ERROR: Python is not installed or not in PATH.
    echo  Install Python 3.10+ from: https://www.python.org/downloads/
    echo  IMPORTANT: Check "Add Python to PATH" during installation!
    echo.
    pause
    exit /b 1
)
for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PY_VER=%%v
echo  OK — Python %PY_VER%

:: ─── 2. Check / Install Ollama ───────────────────────────────────────────────
echo.
echo [2/7] Checking Ollama...
ollama --version >nul 2>&1
if errorlevel 1 (
    echo  Ollama not found. Downloading installer...
    echo  (This is ~100 MB and only happens once.)
    powershell -Command "& { $ProgressPreference='SilentlyContinue'; Invoke-WebRequest -Uri 'https://ollama.com/download/OllamaSetup.exe' -OutFile '%TEMP%\OllamaSetup.exe' }"
    if errorlevel 1 (
        echo  ERROR: Could not download Ollama. Check your internet connection.
        echo  Or download manually from: https://ollama.com/download
        pause
        exit /b 1
    )
    echo  Installing Ollama...
    start /wait "%TEMP%\OllamaSetup.exe" /S
    timeout /t 5 /nobreak > nul
    echo  Ollama installed.
) else (
    for /f "tokens=*" %%v in ('ollama --version 2^>^&1') do set OL_VER=%%v
    echo  OK — !OL_VER!
)

:: ─── 3. Start Ollama service ─────────────────────────────────────────────────
echo.
echo [3/7] Starting Ollama service...
taskkill /f /im ollama.exe >nul 2>&1
timeout /t 2 /nobreak > nul
start /B "" ollama serve > "%TEMP%\ollama_serve.log" 2>&1
timeout /t 4 /nobreak > nul
echo  OK — Ollama service running

:: ─── 4. Pull LLM model ───────────────────────────────────────────────────────
echo.
echo [4/7] Checking llama3.2:3b model...
echo  (First-time download is ~2 GB. Subsequent runs are instant.)
echo.
ollama pull llama3.2:3b
if errorlevel 1 (
    echo  ERROR: Failed to pull llama3.2:3b. Check your internet connection.
    pause
    exit /b 1
)
echo.
echo  OK — llama3.2:3b ready

:: ─── 5. Set up Python venv ───────────────────────────────────────────────────
echo.
echo [5/7] Setting up Python environment...

if not exist "venv" (
    echo  Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo  ERROR: Failed to create virtual environment.
        pause
        exit /b 1
    )
)
call venv\Scripts\activate.bat

echo  Step 5a — upgrading pip...
pip install --upgrade pip
if errorlevel 1 (
    echo  WARNING: pip upgrade failed, continuing anyway...
)

echo  Step 5b — installing gradio first...
pip install "gradio>=4.20.0"
if errorlevel 1 (
    echo  ERROR: Failed to install gradio.
    pause
    exit /b 1
)

echo  Step 5c — installing remaining packages...
pip install -r requirements.txt
if errorlevel 1 (
    echo  ERROR: Package installation failed. See errors above.
    pause
    exit /b 1
)

echo  Verifying gradio is importable...
python -c "import gradio as gr; print('  OK — gradio', gr.__version__)"
if errorlevel 1 (
    echo  ERROR: gradio still not importable after install. 
    echo  Try: pip install --force-reinstall gradio
    pause
    exit /b 1
)
echo  OK — All packages installed

:: ─── 6. Download embedding model ─────────────────────────────────────────────
echo.
echo [6/7] Checking embedding model...
echo  (First-time download is ~130 MB. Subsequent runs are instant.)
echo.
python utils\download_model.py
if errorlevel 1 (
    echo  WARNING: Embedding model download encountered an issue.
    echo  NavAI will attempt to use the cached version.
)

:: ─── 7. Build / rebuild ChromaDB index ───────────────────────────────────────
echo.
echo [7/7] Building search index...
if not exist "chroma_db" (
    echo  No index found — building from data\chunks.json ...
    python utils\rebuild_index.py
    if errorlevel 1 (
        echo  ERROR: Index build failed. Check data\chunks.json exists.
        pause
        exit /b 1
    )
) else (
    echo  Index already exists — skipping rebuild.
    echo  (To force a full rebuild, delete the chroma_db folder and re-run.)
)

:: ─── Copy .env if missing ─────────────────────────────────────────────────────
if not exist ".env" (
    if exist ".env.example" (
        copy ".env.example" ".env" > nul
        echo  Created .env from .env.example
    )
)

:: ─── Launch! ──────────────────────────────────────────────────────────────────
echo.
echo ═══════════════════════════════════════════════════
echo   NavAI is starting...
echo   Browser will open automatically in 5 seconds.
echo   URL: http://localhost:7860
echo   Press Ctrl+C in this window to stop NavAI.
echo ═══════════════════════════════════════════════════
echo.
timeout /t 5 /nobreak > nul
start http://localhost:7860
python app.py

pause
