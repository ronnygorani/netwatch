"""Create a user account. Solves the bootstrap problem: the first admin cannot
be created through an endpoint that requires an admin.

Usage:
    python -m app.create_user <username> <password> <role>
    docker compose exec api python -m app.create_user alice s3cret admin
"""

import sys
from typing import get_args

from app.database import SessionLocal
from app.models.user import User
from app.schemas.user import Role
from app.security import hash_password


def main() -> None:
    if len(sys.argv) != 4:
        print("Usage: python -m app.create_user <username> <password> <role>")
        print(f"Roles: {', '.join(get_args(Role))}")
        raise SystemExit(1)

    username, password, role = sys.argv[1], sys.argv[2], sys.argv[3]
    if role not in get_args(Role):
        raise SystemExit(f"Invalid role '{role}'. Choose from: {', '.join(get_args(Role))}")

    with SessionLocal() as db:
        if db.query(User).filter(User.username == username).first():
            raise SystemExit(f"User '{username}' already exists")
        db.add(User(username=username, password_hash=hash_password(password), role=role))
        db.commit()
    print(f"Created user '{username}' with role '{role}'.")


if __name__ == "__main__":
    main()
