"""
cli_query.py – Interactive CLI for querying NavAI without the Gradio UI.
Run:  python utils/cli_query.py
"""

import os, sys
for k in ("OPENAI_API_KEY", "COHERE_API_KEY", "ANYSCALE_API_KEY"):
    os.environ.pop(k, None)

sys.path.insert(0, ".")
from rag_engine import NavAIEngine

print("=" * 60)
print("🔧 NavAI CLI – Initializing…")
print("=" * 60)

engine = NavAIEngine()
success, status = engine.initialize()
if not success:
    print(status)
    sys.exit(1)
print(status)

print("\n" + "=" * 60)
print("💬 NavAI ready. Type 'quit' to exit.")
print("=" * 60)

while True:
    print("\n" + "-" * 60)
    question = input("❓ Your question: ").strip()
    if question.lower() in ("quit", "exit", "q"):
        print("👋 Goodbye!")
        break
    if not question:
        continue

    print("💭 Thinking…")
    result = engine.query(question)

    if result["error"]:
        print(f"❌ Error: {result['error']}")
    else:
        print(f"\n📝 Answer:\n{result['answer']}")
        if result["sources"]:
            print("\n📚 Sources:")
            for i, s in enumerate(result["sources"][:3], 1):
                print(f"\n  [{i}] score={s['score']:.3f}\n  {s['text'][:200]}…")
