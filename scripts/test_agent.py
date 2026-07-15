"""Offline end-to-end test of the agentic RAG loop (no website, no n8n).

Run from frontend_ui:  python scripts/test_agent.py  ["your question"]

Exercises app.agent.run_agent directly so you can see the full agentic answer (with tool use)
without touching /api/chat or production. Requires OPENAI_API_KEY + Supabase keys in .env.
"""
import os
import sys
import time

from dotenv import load_dotenv

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
load_dotenv(os.path.join(ROOT, ".env"))
sys.path.insert(0, ROOT)

from app.agent import run_agent  # noqa: E402

DEFAULT_QUESTIONS = [
    "What colors does the Shiraz style come in?",
    "What is your refund policy?",
    "Sự khác nhau giữa cap M2 và M3 là gì?",
    "Bạn có bán iPhone không?",  # out-of-scope -> should refuse gracefully
]


def main():
    questions = [" ".join(sys.argv[1:])] if len(sys.argv) > 1 else DEFAULT_QUESTIONS
    for q in questions:
        print("\n" + "=" * 80)
        print("Q:", q)
        t0 = time.time()
        try:
            answer = run_agent(q)
        except Exception as e:
            print("ERROR:", type(e).__name__, e)
            continue
        print(f"(took {time.time() - t0:.1f}s)\nA: {answer}")


if __name__ == "__main__":
    main()
