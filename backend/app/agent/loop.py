"""Agentic RAG loop over the OpenAI Responses API (gpt-5.6-terra).

The model decides which tools to call (0, 1, or many, across multiple rounds), we execute them
against app/rag, feed results back, and repeat up to MAX_TOOL_ROUNDS before producing the final
answer. Conversation state (incl. reasoning) is chained server-side via previous_response_id.

Two code-level guardrails (gpt-5.6-terra ignores prompt instructions for both):
- Citations: append a "Nguồn:" line from the source_documents the tools returned.
- Grounding gate: after answering, gpt-5.6-luna checks whether the answer is actually supported
  by the retrieved snippets; if not, we replace it with the no-info reply (anti-confabulation).
"""
import json
import re

from app.database import (
    get_openai,
    AGENT_MODEL,
    AGENT_JUDGE_MODEL,
    MAX_TOOL_ROUNDS,
    OPENAI_TIMEOUT,
    AGENT_REASONING_EFFORT,
    GROUNDING_CHECK,
)
from app.agent.prompts import SYSTEM_PROMPT, NO_INFO_VI, NO_INFO_EN
from app.agent.tools import TOOLS, dispatch_tool

MAX_TOOL_OUTPUT_CHARS = 6000   # cap each tool result payload sent back to the model
MAX_CITED_SOURCES = 5          # cap how many source_documents we list in the "Nguồn:" line
MAX_JUDGE_CONTEXT_CHARS = 12000
FALLBACK_REPLY = "Xin lỗi, hiện tại tôi chưa thể trả lời câu hỏi này."

# Phrases that indicate the answer found no relevant info -> don't cite retrieved-but-unused docs.
_NO_INFO_MARKERS = (
    "không thấy thông tin", "không có thông tin", "chưa thấy thông tin", "chưa có thông tin",
    "không tìm thấy", "no information", "don't have that information",
    "do not have that information", "don't have detailed information",
    "do not have detailed information", "couldn't find", "could not find",
)

_VN_CHARS = re.compile(
    r"[àáảãạăằắẳẵặâầấẩẫậđèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵ]", re.I
)


def _detect_lang(*texts):
    for t in texts:
        if t and _VN_CHARS.search(t):
            return "vi"
    return "en"


def _is_refusal(answer):
    low = answer.lower()
    return any(m in low for m in _NO_INFO_MARKERS)


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


def _run_tool_calls(resp, source_scores, snippets):
    """Execute function_calls; collect source scores + snippet text; return output items (or [])."""
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
                if isinstance(r, dict):
                    if r.get("source_document"):
                        sd, sc = r["source_document"], (r.get("score") or 0)
                        if sc > source_scores.get(sd, float("-inf")):
                            source_scores[sd] = sc
                    if r.get("content"):
                        snippets.append(r["content"])
            payload = json.dumps(result, ensure_ascii=False)[:MAX_TOOL_OUTPUT_CHARS]
        except Exception as e:  # a tool failure shouldn't crash the loop
            payload = json.dumps({"error": str(e)})
        outputs.append({
            "type": "function_call_output",
            "call_id": it.call_id,
            "output": payload,
        })
    return outputs


def _grounding_supported(client, question, answer, snippets):
    """Ask gpt-5.6-luna whether `answer` is grounded in `snippets`. Biased toward SUPPORTED;
    only flags clear confabulation (specific outside facts). Fail-open on error."""
    context = "\n\n---\n\n".join(snippets)[:MAX_JUDGE_CONTEXT_CHARS]
    instructions = (
        "You verify whether an ANSWER is grounded in the provided CONTEXT snippets from a "
        "knowledge base. Rules:\n"
        "- Rephrasing, summarizing, reorganizing, translating, or drawing straightforward "
        "conclusions from CONTEXT is SUPPORTED.\n"
        "- Respond UNSUPPORTED ONLY if the ANSWER asserts specific facts, figures, or step-by-step "
        "instructions that are absent from CONTEXT and clearly come from outside knowledge.\n"
        "- A refusal or 'I don't have this information' answer is SUPPORTED.\n"
        "- When uncertain, respond SUPPORTED.\n"
        "Respond with exactly one word: SUPPORTED or UNSUPPORTED."
    )
    payload = f"QUESTION:\n{question}\n\nCONTEXT:\n{context}\n\nANSWER:\n{answer}"
    try:
        resp = client.responses.create(
            model=AGENT_JUDGE_MODEL, instructions=instructions, input=payload,
            reasoning={"effort": "medium"},
        )
        verdict = (resp.output_text or "").strip().upper()
    except Exception:
        return True  # never let the judge break the request
    return "UNSUPPORTED" not in verdict


def _finalize(client, question, answer, source_scores, snippets):
    """Apply the grounding gate, then the citation line."""
    if GROUNDING_CHECK and snippets and not _is_refusal(answer):
        if not _grounding_supported(client, question, answer, snippets):
            answer = NO_INFO_VI if _detect_lang(question, answer) == "vi" else NO_INFO_EN
    return _with_citation(answer, source_scores)


def _with_citation(answer, source_scores):
    """Append a deterministic 'Nguồn:' line unless the model already cited or found nothing."""
    low = answer.lower()
    if "nguồn:" in low or "sources:" in low:
        return answer
    if not source_scores or any(m in low for m in _NO_INFO_MARKERS):
        return answer.rstrip() + "\n\nNguồn: (không có tài liệu phù hợp)"
    top = [s for s, _ in sorted(source_scores.items(), key=lambda kv: kv[1], reverse=True)]
    return answer.rstrip() + "\n\nNguồn: " + ", ".join(top[:MAX_CITED_SOURCES])


def run_agent(user_message, history=None, image_url=None):
    """Run the agentic RAG loop and return the final reply string (grounded + cited)."""
    client = get_openai()
    if client is None:
        raise RuntimeError("OpenAI client not configured — set OPENAI_API_KEY")
    # Explicit short timeout + bounded retries: the SDK default is 600s, which can hang requests.
    client = client.with_options(timeout=OPENAI_TIMEOUT, max_retries=1)
    rk = _reasoning_kwargs()
    source_scores, snippets = {}, []

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
        outputs = _run_tool_calls(resp, source_scores, snippets)
        if not outputs:
            return _finalize(client, user_message, resp.output_text or FALLBACK_REPLY,
                             source_scores, snippets)
        rounds += 1
        # Always return outputs for pending tool calls (OpenAI errors otherwise). On the final
        # allowed round, forbid new tool calls so the model must produce an answer.
        force_final = rounds >= MAX_TOOL_ROUNDS
        resp = client.responses.create(
            model=AGENT_MODEL, previous_response_id=resp.id, input=outputs, tools=TOOLS,
            tool_choice="none" if force_final else "auto", **rk,
        )
        if force_final:
            return _finalize(client, user_message, resp.output_text or FALLBACK_REPLY,
                             source_scores, snippets)
