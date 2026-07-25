import os

from supabase import Client, create_client


def create_supabase_client() -> Client:
    url = os.environ.get("SUPABASE_URL") or os.environ.get("API_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get(
        "SERVICE_ROLE_KEY"
    )
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required")
    return create_client(url, key)
