"""Query embedding via OpenAI.

The `documents` table was embedded with OpenAI's text-embedding-3-small (1536 dimensions) via
n8n. This was VERIFIED empirically (scripts/test_retrieval.py): embedding a stored chunk with
3-small yields self-similarity 1.0, while ada-002 / 3-large give ~0.05 (orthogonal). Queries
MUST use the same model or vector similarity is meaningless. See docs/DATA_MODEL.md.
"""
from app.database import get_openai

# Must match how the stored document vectors were produced. Verified: text-embedding-3-small.
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIM = 1536


def embed_query(text: str) -> list[float]:
    """Return the embedding vector for `text`. Raises if OpenAI isn't configured."""
    client = get_openai()
    if client is None:
        raise RuntimeError(
            "OpenAI client not configured — set OPENAI_API_KEY in the environment/.env"
        )
    text = (text or "").replace("\n", " ").strip()
    resp = client.embeddings.create(model=EMBEDDING_MODEL, input=text)
    return resp.data[0].embedding
