"""Mint a new API key. The raw key is printed once and never stored.

Usage:
    python -m app.create_api_key <name> "<scope1 scope2 ...>"
    docker compose exec api python -m app.create_api_key poller "metrics:write"
"""

import sys

from app.auth import generate_key, hash_key
from app.database import SessionLocal
from app.models.api_key import ApiKey


def create_key(name: str, scopes: str) -> str:
    raw_key = generate_key()
    with SessionLocal() as db:
        db.add(ApiKey(name=name, key_hash=hash_key(raw_key), scopes=scopes))
        db.commit()
    return raw_key


def main() -> None:
    if len(sys.argv) != 3:
        print('Usage: python -m app.create_api_key <name> "<scope1 scope2 ...>"')
        raise SystemExit(1)

    name, scopes = sys.argv[1], sys.argv[2]
    raw_key = create_key(name, scopes)
    print(f"API key created for '{name}' with scopes: {scopes}")
    print(f"\n  {raw_key}\n")
    print("Shown once only — store it in the consumer's environment.")


if __name__ == "__main__":
    main()
