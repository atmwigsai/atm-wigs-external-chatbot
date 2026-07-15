"""Agent tool definitions (OpenAI Responses API function tools) + dispatch.

Phase 2 exposes one tool, `vector_search`, backed by app/rag. The Phase-3 web tool
(`web_search_atmwigs`) will be added here as a second entry.
"""
from app.rag.search import search_documents, DOC_TYPES

# OpenAI Responses API function-tool format (flat: type/name/description/parameters).
VECTOR_SEARCH_TOOL = {
    "type": "function",
    "name": "vector_search",
    "description": (
        "Search the ATM Wigs internal knowledge base (product catalog, master price list, "
        "policies, technical FAQ, and website content). Returns relevant text chunks with their "
        "source_document and doc_type. Use for any question about ATM Wigs products, prices, "
        "policies, shipping, returns, or technical details."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Natural-language search query; prefer specific product names/codes.",
            },
            "doc_type": {
                "type": "string",
                "enum": sorted(DOC_TYPES),
                "description": "Optional filter to one category. Omit to search all.",
            },
            "top_k": {
                "type": "integer",
                "description": "How many chunks to return (default 5).",
            },
        },
        "required": ["query"],
    },
}

TOOLS = [VECTOR_SEARCH_TOOL]


def dispatch_tool(name: str, args: dict):
    """Execute a tool call by name. Returns a JSON-serializable result."""
    if name == "vector_search":
        return search_documents(
            query=args["query"],
            doc_type=args.get("doc_type"),
            top_k=int(args.get("top_k", 5) or 5),
        )
    raise ValueError(f"unknown tool: {name}")
