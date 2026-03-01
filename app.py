"""
NavAI – Frontend  (improved)
"""

import os
import re
import time
import threading
import gradio as gr
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
for _k in ("OPENAI_API_KEY", "ANYSCALE_API_KEY"):
    os.environ.pop(_k, None)

from rag_engine import NavAIEngine

# ── Engine init (background thread) ──────────────────────────────────────────
engine       = NavAIEngine()
_init_done   = False
_init_status = "⏳ Initializing…"

def _bg_init():
    global _init_done, _init_status
    success, msg = engine.initialize()
    _init_done   = True
    _init_status = msg if success else f"❌ {msg}"

threading.Thread(target=_bg_init, daemon=True).start()


# ── Text helpers ──────────────────────────────────────────────────────────────

# Only fix genuine OCR split-word artifacts — not whole words that could cause
# false replacements on clean text (e.g. "day", "rate", "fund" were previously
# in the list and would corrupt good content)
_OCR_FIXES = {
    "Goverrunent":  "Government",
    "Govemment":    "Government",
    "Gr ov ernment": "Government",
    "~10sehold":    "household",
    "da ted":       "dated",
    "wlder":        "under",
    "und er":       "under",
    "payme nt":     "payment",
    "allowan ce":   "allowance",
    "employm ent":  "employment",
    "unemp loyment":"unemployment",
    "entit lement": "entitlement",
    "entit led":    "entitled",
    "disbur sement":"disbursement",
    "implem entation": "implementation",
    "regis tration":"registration",
    "regi stration":"registration",
    "appli cant":   "applicant",
    "appli cation": "application",
    "guar ant ee":  "guarantee",
    "panch ayat":   "Panchayat",
    "panch ayats":  "Panchayats",
    "prog ramme":   "programme",
    "expen diture": "expenditure",
    "allo wance":   "allowance",
    "vulne rable":  "vulnerable",
    "auth orised":  "authorised",
    "auth orized":  "authorized",
    "auth ority":   "authority",
}

def clean_ocr(text: str) -> str:
    """Fix OCR split-word artifacts. Only targets known bad patterns."""
    for bad, good in _OCR_FIXES.items():
        text = text.replace(bad, good)
    text = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", text)   # hyphen line-breaks
    text = re.sub(r"(?<=[a-z])1(?=[a-z])", "l", text)    # '1' mistaken for 'l'
    text = re.sub(r"\s{2,}", " ", text)                   # collapse spaces
    return text.replace("\n", " ").strip()


def format_sources(sources: list) -> str:
    """
    Render source cards using rich metadata (title, chapter, act) when available,
    falling back to a text snippet if metadata is missing.
    """
    if not sources:
        return ""

    out = "\n\n---\n**Sources**\n"
    for i, src in enumerate(sources[:4], 1):
        score    = src.get("score", 0)
        title    = src.get("title", "")
        chapter  = src.get("chapter", "")
        act      = src.get("act", "")
        pages    = src.get("source_pages", "")
        raw_text = clean_ocr(src.get("text", ""))

        pct  = int(score * 100)
        fill = round(score * 8)
        bar  = "●" * fill + "○" * (8 - fill)

        # Heading: prefer title from metadata
        if title:
            heading = f"{chapter} — {title}" if chapter else title
        else:
            # Fall back to first sentence of text
            sentences = re.split(r"(?<=[.!?])\s", raw_text)
            first = sentences[0] if sentences else raw_text[:70]
            heading = first[:70].rstrip() + ("…" if len(first) > 70 else "")

        # Act badge and page badge
        act_badge  = f" `{act}`" if act else ""
        page_badge = f" · p.{pages}" if pages else ""

        # Preview: 200 chars of text
        preview = raw_text[:220].rstrip()
        if len(raw_text) > 220:
            preview += "…"

        out += f"\n`{bar} {pct}%`{act_badge}{page_badge} &nbsp; **{heading}**"
        if preview:
            out += f"  \n<sub>{preview}</sub>"
        out += "\n"

    return out


# ── UI text ───────────────────────────────────────────────────────────────────

DISCLAIMER = (
    "\n\n<sub>⚖️ NavAI provides general legal information for educational purposes only — "
    "not a substitute for professional legal advice.</sub>"
)

WELCOME = """\
## Welcome to NavAI

Your plain-language guide to the **MGNREGA Act, 2005** — rights, wages, job cards, complaints, and more.

Upload additional legal PDFs under **Documents** to expand my knowledge base instantly.

---
*Ask a question below to get started.*
"""

INITIAL = [{"role": "assistant", "content": WELCOME}]

SAMPLES = [
    "What is the unemployment allowance rate under MGNREGA?",
    "When can a Programme Officer reject an unemployment claim?",
    "How can I apply for work under MGNREGA?",
    "What documents are needed for a job card?",
    "What happens if wages are delayed?",
    "Can women apply for MGNREGA work?",
    "How to file a complaint under MGNREGA?",
    "What work is provided under the scheme?",
]


# ── Chat logic ────────────────────────────────────────────────────────────────

def chat(message: str, history: list):
    if not message.strip():
        return history, ""

    t0 = time.time()
    while not _init_done and time.time() - t0 < 180:
        time.sleep(0.5)

    if not engine.ready:
        reply = f"⚙️ Still starting up — please wait.\n\n`{_init_status}`"
    else:
        result = engine.query(message)
        if result["error"]:
            reply = f"❌ {result['error']}"
        else:
            answer = result["answer"].strip() or \
                "I couldn't find a specific answer. Please try rephrasing your question."
            reply  = answer
            reply += format_sources(result["sources"])
            reply += DISCLAIMER

    return history + [
        {"role": "user",      "content": message},
        {"role": "assistant", "content": reply},
    ], ""


def ingest_pdf(f):
    if f is None:
        return "Select a PDF first."
    if not engine.ready:
        return "⚙️ Engine still starting — try again in a moment."
    ok, msg = engine.ingest_pdf(f.name)
    return msg


def status():
    if not _init_done:
        return f"⏳ {_init_status}"
    s    = engine.get_stats()
    icon = "🟢" if s["ready"] else "🔴"
    return (
        f"{icon} **{'Operational' if s['ready'] else 'Offline'}**\n\n"
        f"| | |\n|---|---|\n"
        f"| LLM | `{s['llm_model']}` |\n"
        f"| Embeddings | `{Path(s['embed_model']).name}` |\n"
        f"| Collection | `{s['collection']}` |\n"
        f"| Chunks indexed | **{s['doc_count']}** |\n"
        f"| Retrieval | {s['top_k']} |\n"
        f"| Reranker | {s['reranker']} |"
    )


# ── CSS ───────────────────────────────────────────────────────────────────────
CSS = """@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Fraunces:opsz,wght@9..144,600&display=swap');
:root {
  --bg:       #08121e;
  --s1:       #0d1f33;
  --s2:       #112440;
  --s3:       #16304f;
  --teal:     #2dd4bf;
  --teal2:    #14b8a6;
  --teal-bg:  rgba(45,212,191,0.07);
  --teal-bdr: rgba(45,212,191,0.2);
  --white:    #e2eaf6;
  --muted:    #5d7a9a;
  --dim:      rgba(255,255,255,0.05);
  --r:        10px;
}
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body, .gradio-container { background: var(--bg) !important; font-family: 'Inter', sans-serif !important; color: var(--white) !important; }
* { scrollbar-width: thin; scrollbar-color: var(--s3) transparent; }
::-webkit-scrollbar { width: 4px; height: 4px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--s3); border-radius: 2px; }
.share-button, .flag-button, .like-button, .dislike-button,
button[title="Share"], button[title="Flag"], button[aria-label="Share"],
.copy-button, footer { display: none !important; }
.hdr {
  display: flex; align-items: center; gap: 16px;
  background: var(--s1);
  border: 1px solid var(--teal-bdr);
  border-radius: 14px;
  padding: 20px 26px;
  margin-bottom: 18px;
  position: relative; overflow: hidden;
}
.hdr::after {
  content: '';
  position: absolute; top: 0; left: 0; right: 0; height: 1px;
  background: linear-gradient(90deg, transparent 0%, var(--teal) 50%, transparent 100%);
}
.hdr-icon {
  width: 48px; height: 48px;
  background: linear-gradient(135deg, var(--teal2), var(--teal));
  border-radius: 12px;
  display: flex; align-items: center; justify-content: center;
  font-size: 1.5rem;
  box-shadow: 0 4px 16px rgba(45,212,191,0.3);
  flex-shrink: 0;
}
.hdr-name {
  font-family: 'Fraunces', serif !important;
  font-size: 1.75rem !important; font-weight: 600 !important;
  color: var(--white) !important; line-height: 1;
}
.hdr-name em { color: var(--teal); font-style: normal; }
.hdr-sub { color: var(--muted); font-size: 0.78rem; margin-top: 4px; }
.hdr-tags { display: flex; gap: 6px; margin-top: 8px; flex-wrap: wrap; }
.tag {
  background: var(--teal-bg); border: 1px solid var(--teal-bdr);
  color: var(--teal); font-size: 0.68rem; font-weight: 600;
  padding: 2px 9px; border-radius: 20px; letter-spacing: 0.4px; text-transform: uppercase;
}
.tabs > .tab-nav { border-bottom: 1px solid var(--dim) !important; }
.tabs > .tab-nav button {
  background: transparent !important; color: var(--muted) !important;
  border: none !important; border-bottom: 2px solid transparent !important;
  font-size: 0.85rem !important; font-weight: 500 !important;
  padding: 10px 18px !important; transition: all 0.15s !important;
}
.tabs > .tab-nav button:hover { color: var(--white) !important; }
.tabs > .tab-nav button.selected { color: var(--teal) !important; border-bottom-color: var(--teal) !important; }
.chatbot { border: 1px solid var(--dim) !important; border-radius: 12px !important; background: var(--s1) !important; overflow: hidden !important; }
.chatbot > div { background: transparent !important; }
.message.user > div { background: var(--s3) !important; border: 1px solid var(--dim) !important; border-radius: 10px 10px 2px 10px !important; color: var(--white) !important; }
.message.bot > div, .message.assistant > div {
  background: var(--s2) !important;
  border: 1px solid var(--dim) !important;
  border-left: 2px solid var(--teal) !important;
  border-radius: 2px 10px 10px 10px !important;
  color: var(--white) !important;
}
.inp-wrap {
  display: flex; align-items: flex-end; gap: 8px;
  background: var(--s1); border: 1px solid var(--dim);
  border-radius: 12px; padding: 10px 12px; margin-top: 8px;
  transition: border-color 0.2s;
}
.inp-wrap:focus-within { border-color: var(--teal-bdr) !important; }
.inp-wrap textarea {
  background: transparent !important; border: none !important;
  color: var(--white) !important; font-family: 'Inter', sans-serif !important;
  font-size: 0.92rem !important; resize: none !important; outline: none !important;
  box-shadow: none !important;
}
.inp-wrap textarea::placeholder { color: var(--muted) !important; }
.btn-main {
  background: var(--teal2) !important; color: #08121e !important;
  font-weight: 600 !important; font-size: 0.85rem !important;
  border: none !important; border-radius: 8px !important;
  padding: 9px 20px !important; cursor: pointer !important;
  transition: opacity 0.15s !important; white-space: nowrap !important;
  box-shadow: 0 2px 10px rgba(45,212,191,0.25) !important;
}
.btn-main:hover { opacity: 0.85 !important; }
.btn-clr {
  background: transparent !important; color: var(--muted) !important;
  border: 1px solid var(--dim) !important; border-radius: 8px !important;
  font-size: 0.8rem !important; padding: 7px 14px !important;
  transition: all 0.15s !important; cursor: pointer !important;
}
.btn-clr:hover { color: var(--white) !important; border-color: var(--teal-bdr) !important; }
.btn-sample {
  background: transparent !important; color: var(--muted) !important;
  border: 1px solid var(--dim) !important; border-radius: 7px !important;
  font-size: 0.76rem !important; font-weight: 400 !important;
  text-align: left !important; padding: 6px 10px !important;
  transition: all 0.15s !important; cursor: pointer !important; line-height: 1.4 !important;
  width: 100% !important;
}
.btn-sample:hover { color: var(--teal) !important; border-color: var(--teal-bdr) !important; background: var(--teal-bg) !important; }
.btn-ghost {
  background: transparent !important; color: var(--muted) !important;
  border: 1px solid var(--dim) !important; border-radius: 8px !important;
  font-size: 0.82rem !important; padding: 7px 14px !important;
  transition: all 0.15s !important; cursor: pointer !important;
}
.btn-ghost:hover { color: var(--teal) !important; border-color: var(--teal-bdr) !important; }
.btn-upload {
  background: var(--teal2) !important; color: #08121e !important;
  font-weight: 600 !important; border: none !important; border-radius: 8px !important;
  box-shadow: 0 2px 10px rgba(45,212,191,0.25) !important;
}
.panel {
  background: var(--s1); border: 1px solid var(--dim);
  border-radius: 12px; padding: 16px; height: 100%;
}
.panel-label {
  color: var(--teal); font-size: 0.68rem; font-weight: 600;
  letter-spacing: 1px; text-transform: uppercase; margin-bottom: 10px;
}
.divider { border: none; border-top: 1px solid var(--dim); margin: 14px 0; }
.card { background: var(--s1) !important; border: 1px solid var(--dim) !important; border-radius: 10px !important; padding: 16px !important; }
.upload { border: 2px dashed var(--teal-bdr) !important; border-radius: 10px !important; background: var(--teal-bg) !important; }
.upload:hover { border-color: var(--teal) !important; }
p, li { color: var(--white) !important; line-height: 1.7 !important; }
h1,h2,h3,h4 { color: var(--white) !important; font-family: 'Fraunces', serif !important; margin-bottom: 8px !important; }
strong { color: var(--teal) !important; }
code { background: var(--s3) !important; color: var(--teal) !important; padding: 1px 5px !important; border-radius: 4px !important; font-size: 0.84em !important; }
blockquote { border-left: 2px solid var(--teal-bdr) !important; padding: 8px 14px !important; color: var(--muted) !important; font-style: italic !important; background: var(--teal-bg) !important; border-radius: 0 6px 6px 0 !important; }
a { color: var(--teal) !important; }
hr { border-color: var(--dim) !important; }
sub { color: var(--muted) !important; font-size: 0.78rem !important; line-height: 1.5 !important; }
table { border-collapse: collapse !important; width: 100% !important; font-size: 0.86rem !important; }
th { background: var(--s3) !important; color: var(--teal) !important; font-weight: 600 !important; padding: 8px 12px !important; text-align: left !important; }
td { padding: 7px 12px !important; border-bottom: 1px solid var(--dim) !important; color: var(--white) !important; }
tr:hover td { background: var(--teal-bg) !important; }
.ftr { text-align: center; color: var(--muted); font-size: 0.7rem; padding: 14px; border-top: 1px solid var(--dim); margin-top: 16px; letter-spacing: 0.3px; }
.ftr span { color: var(--teal); }
"""


# ── UI ────────────────────────────────────────────────────────────────────────

with gr.Blocks(title="NavAI — Legal Assistant") as demo:

    gr.HTML("""
    <div class="hdr">
      <div class="hdr-icon">⚖️</div>
      <div>
        <div class="hdr-name">Nav<em>AI</em></div>
        <div class="hdr-sub">Legal Information Assistant · MGNREGA Specialist</div>
        <div class="hdr-tags">
          <span class="tag">🔒 On-Device</span>
          <span class="tag">📋 MGNREGA 2005</span>
          <span class="tag">⚡ Local RAG</span>
          <span class="tag">🌐 No Cloud</span>
        </div>
      </div>
    </div>
    """)

    with gr.Tabs(elem_classes="tabs"):

        # ── Chat ──────────────────────────────────────────────────────────────
        with gr.TabItem("💬  Assistant"):
            with gr.Row(equal_height=True):

                with gr.Column(scale=3):
                    chatbot = gr.Chatbot(
                        value=INITIAL,
                        label="",
                        height=500,
                        elem_classes="chatbot",
                    )
                    with gr.Row(elem_classes="inp-wrap"):
                        msg = gr.Textbox(
                            placeholder="Ask about wages, job cards, complaints, rights… (Enter to send)",
                            label="", lines=2, scale=5, container=False,
                        )
                        with gr.Column(scale=0, min_width=110):
                            send  = gr.Button("Send ➤",  elem_classes="btn-main")
                            clear = gr.Button("Clear",   elem_classes="btn-clr")

                with gr.Column(scale=1, min_width=190):
                    gr.HTML('<div class="panel">')
                    gr.HTML('<div class="panel-label">Quick Questions</div>')
                    for q in SAMPLES:
                        gr.Button(q, elem_classes="btn-sample", size="sm").click(
                            fn=lambda q=q: q, outputs=msg
                        )
                    gr.HTML('<hr class="divider">')
                    gr.HTML("""
                    <div class="panel-label">How it works</div>
                    <div style="color:#5d7a9a;font-size:0.73rem;line-height:2;">
                      🔍 Retrieves 8 candidates<br>
                      🎯 Filters to top 4 by score<br>
                      🧠 Local LLM synthesizes answer<br>
                      📚 Shows titled source sections<br>
                      🔒 Zero data sent externally
                    </div>
                    """)
                    gr.HTML('</div>')

            send.click(chat,  [msg, chatbot], [chatbot, msg])
            msg.submit(chat,  [msg, chatbot], [chatbot, msg])
            clear.click(lambda: (INITIAL, ""), outputs=[chatbot, msg])

        # ── Documents ─────────────────────────────────────────────────────────
        with gr.TabItem("📄  Documents"):
            gr.Markdown("""
### Upload Legal Documents

Drop any **legal PDF** and NavAI will extract, chunk, embed and index it instantly.
It becomes searchable in the Assistant tab immediately.

> 🔒 All processing is local. No file contents are transmitted anywhere.
""")
            with gr.Row():
                with gr.Column(scale=2):
                    f_in  = gr.File(label="PDF Document", file_types=[".pdf"], elem_classes="upload")
                    f_btn = gr.Button("⚡  Process & Index", elem_classes="btn-upload")
                with gr.Column(scale=2):
                    f_out = gr.Markdown("*Select a file and click Process.*", elem_classes="card")
            f_btn.click(ingest_pdf, [f_in], [f_out])

            gr.Markdown("""
---
| Step | Action |
|:--|:--|
| Extract | Text pulled from every page |
| Chunk | Split at legal section boundaries |
| Embed | Vectorised with local BGE model |
| Store | Saved to ChromaDB on-disk |
| Query | Immediately available in Assistant |
""")

        # ── System ────────────────────────────────────────────────────────────
        with gr.TabItem("⚙️  System"):
            gr.Markdown("### System Status")
            s_md  = gr.Markdown(value=_init_status, elem_classes="card")
            s_btn = gr.Button("Refresh", elem_classes="btn-ghost")
            s_btn.click(status, outputs=[s_md])
            gr.Markdown("""
---
| Layer | Technology |
|:--|:--|
| Frontend | Gradio |
| Embeddings | BGE-small-en (local HuggingFace) |
| Vector DB | ChromaDB (persistent, on-disk) |
| LLM | Ollama · llama3.2:3b (local) |
| Orchestration | LlamaIndex |
| Retrieval | Top-8 → filter → Top-4 to LLM |
""")

        # ── About ─────────────────────────────────────────────────────────────
        with gr.TabItem("ℹ️  About"):
            gr.Markdown("""
## NavAI

Built to make the rights guaranteed under MGNREGA accessible to the workers they protect — in plain language, instantly, and for free.

**Privacy by design** — no API keys, no cloud calls, no stored conversations.

**Extend it** — upload additional legal documents via the Documents tab.

---

> ⚖️ NavAI provides general legal information for educational purposes only.
> It is not a substitute for professional legal advice.
> For specific matters, consult a qualified advocate or legal aid service.
""")

    gr.HTML("""
    <div class="ftr">
      <span>NavAI</span> · Legal Information Assistant ·
      All processing is on-device · No data leaves your machine
    </div>
    """)

if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        show_error=True,
        css=CSS,
    )
