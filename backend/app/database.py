import os
from supabase import create_client, Client

SUPABASE_URL = os.getenv("SUPABASE_URL")
# Backend uses the Supabase SERVICE_ROLE key: it bypasses RLS so the app keeps working with
# RLS enabled. This key must stay server-side ONLY — never expose it to the browser/frontend.
# Falls back to the legacy SUPABASE_KEY (anon) during the transition if the new var isn't set.
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")
N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# --- Agentic RAG feature flag & config (Phase 2) ---
# USE_AGENT defaults to FALSE: production keeps using n8n until this is explicitly turned on.
USE_AGENT = os.getenv("USE_AGENT", "false").strip().lower() in ("1", "true", "yes", "on")
AGENT_MODEL = os.getenv("AGENT_MODEL", "gpt-5.6-terra")        # main tool-calling loop
AGENT_SIDE_MODEL = os.getenv("AGENT_SIDE_MODEL", "gpt-5.6-luna")  # cheap side-tasks (later)
MAX_TOOL_ROUNDS = int(os.getenv("MAX_TOOL_ROUNDS", "3"))       # hard cap on tool rounds
MAX_HISTORY = int(os.getenv("AGENT_HISTORY_TURNS", "8"))       # prior messages fed as context
OPENAI_TIMEOUT = float(os.getenv("OPENAI_TIMEOUT", "60"))      # per-call timeout (SDK default is 600s!)
# Reasoning effort for gpt-5.6-terra (low|medium|high). medium ~ trims latency vs default.
AGENT_REASONING_EFFORT = os.getenv("AGENT_REASONING_EFFORT", "medium").strip().lower()
# Post-answer grounding check: if the answer isn't supported by retrieved snippets, replace it
# with the no-info reply (anti-confabulation). DEFAULT OFF — the LLM judge (luna or terra) proved
# unreliable, false-refusing legitimate synthesized answers (refund/company/MOQ) ~50% of the time.
# Kept behind the flag for future experimentation. Judge model configurable.
GROUNDING_CHECK = os.getenv("GROUNDING_CHECK", "false").strip().lower() in ("1", "true", "yes", "on")
AGENT_JUDGE_MODEL = os.getenv("AGENT_JUDGE_MODEL", AGENT_SIDE_MODEL)

# Khởi tạo Supabase
supabase: Client = None
if SUPABASE_URL and SUPABASE_KEY:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# OpenAI client is created lazily on first use, so a missing key or missing package can never
# break the existing app import / chat path. Used only by the retrieval + agent layers.
_openai_client = None

def get_supabase():
    return supabase

def get_n8n_url():
    return N8N_WEBHOOK_URL

def get_openai():
    global _openai_client
    if _openai_client is None:
        if not OPENAI_API_KEY:
            return None
        from openai import OpenAI
        _openai_client = OpenAI(api_key=OPENAI_API_KEY)
    return _openai_client
