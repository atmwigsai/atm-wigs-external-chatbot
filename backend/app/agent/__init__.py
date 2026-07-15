"""Agentic RAG orchestrator (Phase 2).

An OpenAI Responses-API tool-calling loop that answers ATM Wigs support questions by deciding
when to call the `vector_search` tool (app/rag). Wired into /api/chat behind the USE_AGENT flag.
"""
from app.agent.loop import run_agent

__all__ = ["run_agent"]
