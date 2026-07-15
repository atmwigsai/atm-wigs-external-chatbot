"""Agentic RAG loop over the OpenAI Responses API (gpt-5.6-terra).

The model decides which tools to call (0, 1, or many, across multiple rounds), we execute them
against app/rag, feed results back, and repeat up to MAX_TOOL_ROUNDS before producing the final
answer. Conversation state (incl. reasoning) is chained server-side via previous_response_id.

Citations: gpt-5.6-terra ignores prompt instructions to list sources, so we append a "Nguồn:"
line deterministically in code from the source_documents the tools actually returned (unless the
model already added one, or the answer is a "no relevant info" response).
"""
import json

from app.database import (
    get_openai,
    AGENT_MODEL,
    MAX_TOOL_ROUNDS,
    OPENAI_TIMEOUT,
    AGENT_REASONING_EFFORT,
)
from app.agent.prompts import SYSTEM_PROMPT
from app.agent.tools import TOOLS, dispatch_tool

MAX_TOOL_OUTPUT_CHARS = 6000   # cap each tool result payload sent back to the model
MAX_CITED_SOURCES = 5          # cap how many source_documents we list in the "Nguồn:" line
FALLBACK_REPLY = "Xin lỗi, hiện tại tôi chưa thể trả lời câu hỏi này."

# Phrases that indicate the answer found no relevant info -> don't cite retrieved-but-unused docs.
_NO_INFO_MARKERS = (
    "không thấy thông tin", "không có thông tin", "chưa thấy thông tin", "không tìm thấy",
    "no information", "don't have that information", "do not have that information",
    "couldn't find", "could not find",
)


def _reasoning_kwargs():
    return {"reasoning": {"effort": AGENT_REASONING_EFFORT}} if AGENT_REASONING_EFFORT else {}


def _build_input(history, user_message, image_url):
    """Build the Responses API `input` list from prior turns + the current message."""
    items = []
    for h in history or []:
        role = h.get("role")
        content = h.get("content") or ""
        if role in ("user", "assistant") and content:
            items.append({"role": role, "content": content})

    if image_url:
        items.append({
            "role": "user",
            "content": [
                {"type": "input_text", "text": user_message or ""},
                {"type": "input_image", "image_url": image_url},
            ],
        })
    else:
        items.append({"role": "user", "content": user_message or ""})
    return items


def _run_tool_calls(resp, source_scores):
    """Execute every function_call in `resp`; collect source scores; return output items (or [])."""
    outputs = []
    for it in getattr(resp, "output", []) or []:
        if getattr(it, "type", None) != "function_call":
            continue
        try:
            args = json.loads(it.arguments or "{}")
        except json.JSONDecodeError:
            args = {}
        try:
            result = dispatch_tool(it.name, args)
            for r in result:
                if isinstance(r, dict) and r.get("source_document"):
                    sd = r["source_document"]
                    sc = r.get("score") or 0
                    if sc > source_scores.get(sd, float("-inf")):
                        source_scores[sd] = sc
            payload = json.dumps(result, ensure_ascii=False)[:MAX_TOOL_OUTPUT_CHARS]
        except Exception as e:  # a tool failure shouldn't crash the loop
            payload = json.dumps({"error": str(e)})
        outputs.append({
            "type": "function_call_output",
            "call_id": it.call_id,
            "output": payload,
        })
    return outputs


def _with_citation(answer, source_scores):
    """Append a deterministic 'Nguồn:' line unless the model already cited or found nothing."""
    low = answer.lower()
    if "nguồn:" in low or "sources:" in low:
        return answer
    if not source_scores or any(m in low for m in _NO_INFO_MARKERS):
        return answer.rstrip() + "\n\nNguồn: (không có tài liệu phù hợp)"
    top = [s for s, _ in sorted(source_scores.items(), key=lambda kv: kv[1], reverse=True)]
    top = top[:MAX_CITED_SOURCES]
    return answer.rstrip() + "\n\nNguồn: " + ", ".join(top)


def run_agent(user_message, history=None, image_url=None):
    """Run the agentic RAG loop and return the final reply string (with a citation line)."""
    client = get_openai()
    if client is None:
        raise RuntimeError("OpenAI client not configured — set OPENAI_API_KEY")
    # Explicit short timeout + bounded retries: the SDK default is 600s, which can hang requests.
    client = client.with_options(timeout=OPENAI_TIMEOUT, max_retries=1)
    rk = _reasoning_kwargs()
    source_scores = {}

    # Initial turn. If an image is attached but the model rejects the vision format, degrade to
    # text-only rather than failing the whole request (vision support is being verified).
    try:
        resp = client.responses.create(
            model=AGENT_MODEL, instructions=SYSTEM_PROMPT,
            input=_build_input(history, user_message, image_url), tools=TOOLS, **rk,
        )
    except Exception:
        if not image_url:
            raise
        resp = client.responses.create(
            model=AGENT_MODEL, instructions=SYSTEM_PROMPT,
            input=_build_input(history, user_message, None), tools=TOOLS, **rk,
        )

    rounds = 0
    while True:
        outputs = _run_tool_calls(resp, source_scores)
        if not outputs:
            return _with_citation(resp.output_text or FALLBACK_REPLY, source_scores)
        rounds += 1
        # Always return outputs for pending tool calls (OpenAI errors otherwise). On the final
        # allowed round, forbid new tool calls so the model must produce an answer.
        force_final = rounds >= MAX_TOOL_ROUNDS
        resp = client.responses.create(
            model=AGENT_MODEL, previous_response_id=resp.id, input=outputs, tools=TOOLS,
            tool_choice="none" if force_final else "auto", **rk,
        )
        if force_final:
            return _with_citation(resp.output_text or FALLBACK_REPLY, source_scores)
