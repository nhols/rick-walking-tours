import argparse
import os
import subprocess
from io import StringIO
from pathlib import Path
from uuid import uuid4

from dotenv import dotenv_values, load_dotenv
from pydantic import BaseModel
from supabase import create_client


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class CreditDelta(BaseModel):
    delta: int


def main() -> None:
    parser = argparse.ArgumentParser(description="Grant tour credits to a user")
    parser.add_argument("email", help="Supabase Auth email address")
    parser.add_argument("amount", type=positive_integer, help="Credits to grant")
    args = parser.parse_args()

    load_dotenv(PROJECT_ROOT / ".env")
    url, service_key = supabase_credentials()
    client = create_client(url, service_key)

    user = None
    page = 1
    while user is None:
        users = client.auth.admin.list_users(page=page, per_page=1000)
        user = next(
            (candidate for candidate in users if candidate.email == args.email),
            None,
        )
        if user is not None or len(users) < 1000:
            break
        page += 1

    if user is None:
        raise SystemExit(f"No Supabase user found for {args.email}")

    client.table("credit_transactions").insert(
        {
            "user_id": str(user.id),
            "delta": args.amount,
            "reason": "manual_admin_grant",
            "idempotency_key": f"manual-grant:{uuid4()}",
        }
    ).execute()
    transactions = (
        client.table("credit_transactions")
        .select("delta")
        .eq("user_id", str(user.id))
        .execute()
    )
    balance = sum(CreditDelta.model_validate(item).delta for item in transactions.data)
    print(f"Granted {args.amount} credits to {args.email}. Balance: {balance}")


def positive_integer(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("amount must be greater than zero")
    return parsed


def supabase_credentials() -> tuple[str, str]:
    url = os.environ.get("SUPABASE_URL")
    service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if url and service_key:
        return url, service_key

    try:
        output = subprocess.check_output(
            ["npx", "supabase", "status", "-o", "env"],
            cwd=PROJECT_ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError as error:
        raise SystemExit(
            "Supabase is not running and production credentials are not set"
        ) from error
    local = dotenv_values(stream=StringIO(output))
    url = local.get("API_URL")
    service_key = local.get("SERVICE_ROLE_KEY")
    if not url or not service_key:
        raise SystemExit("Supabase status did not return local credentials")
    return url, service_key


if __name__ == "__main__":
    main()
