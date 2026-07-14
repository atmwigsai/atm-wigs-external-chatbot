import os
from supabase import create_client, Client

SUPABASE_URL = os.getenv("SUPABASE_URL")
# Backend uses the Supabase SERVICE_ROLE key: it bypasses RLS so the app keeps working with
# RLS enabled. This key must stay server-side ONLY — never expose it to the browser/frontend.
# Falls back to the legacy SUPABASE_KEY (anon) during the transition if the new var isn't set.
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")
N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Khởi tạo Supabase
supabase: Client = None
if SUPABASE_URL and SUPABASE_KEY:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# OpenAI client is created lazily on first use, so a missing key or missing package can never
# break the existing app import / chat path. Used only by the retrieval layer (app/rag).
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
