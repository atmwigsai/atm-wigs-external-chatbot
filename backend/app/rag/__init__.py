"""Retrieval layer for the ATM Wigs chatbot.

Reads directly from the unified `documents` table in Supabase (pgvector + full-text),
independent of n8n. This is the backend for the `vector_search` agent tool (Phase 2).
"""
from app.rag.search import search_documents
from app.rag.embed import embed_query, EMBEDDING_MODEL, EMBEDDING_DIM

__all__ = ["search_documents", "embed_query", "EMBEDDING_MODEL", "EMBEDDING_DIM"]
