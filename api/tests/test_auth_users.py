"""Human authentication: login, tokens, roles."""

from app.models.user import User
from app.security import hash_password


def make_user(test_db, username="alice", password="s3cretpass", role="admin", active=True):
    with test_db.session_factory() as db:
        db.add(
            User(
                username=username,
                password_hash=hash_password(password),
                role=role,
                is_active=active,
            )
        )
        db.commit()
    return {"username": username, "password": password}


def login(client, creds):
    return client.post("/v1/auth/login", data=creds)


def bearer(client, creds) -> dict:
    token = login(client, creds).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_login_returns_token(client, test_db):
    creds = make_user(test_db)
    resp = login(client, creds)
    assert resp.status_code == 200
    assert resp.json()["token_type"] == "bearer"
    assert resp.json()["access_token"]


def test_login_wrong_password_401(client, test_db):
    make_user(test_db)
    resp = login(client, {"username": "alice", "password": "wrong"})
    assert resp.status_code == 401
    # Same message whether the user exists or not: no username enumeration.
    assert resp.json()["detail"] == "Incorrect username or password"


def test_login_unknown_user_401(client, test_db):
    resp = login(client, {"username": "nobody", "password": "whatever"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Incorrect username or password"


def test_deactivated_user_cannot_login(client, test_db):
    creds = make_user(test_db, username="bob", active=False)
    assert login(client, creds).status_code == 401


def test_me_requires_token(client, test_db):
    creds = make_user(test_db)
    assert client.get("/v1/auth/me").status_code == 401
    resp = client.get("/v1/auth/me", headers=bearer(client, creds))
    assert resp.status_code == 200
    assert resp.json()["username"] == "alice"
    assert "password_hash" not in resp.json()


def test_garbage_token_rejected(client, test_db):
    make_user(test_db)
    resp = client.get("/v1/auth/me", headers={"Authorization": "Bearer not.a.token"})
    assert resp.status_code == 401


def test_role_hierarchy_enforced(client, test_db):
    """viewer < operator < approver < admin; user creation needs admin."""
    viewer = make_user(test_db, username="vic", role="viewer")
    admin = make_user(test_db, username="adm", role="admin")
    payload = {"username": "new", "password": "password123", "role": "viewer"}

    denied = client.post("/v1/auth/users", json=payload, headers=bearer(client, viewer))
    assert denied.status_code == 403
    assert "admin" in denied.json()["detail"]

    allowed = client.post("/v1/auth/users", json=payload, headers=bearer(client, admin))
    assert allowed.status_code == 201


def test_password_is_hashed_not_stored(test_db):
    make_user(test_db, username="carol", password="plaintext123")
    with test_db.session_factory() as db:
        stored = db.query(User).filter(User.username == "carol").first().password_hash
    assert "plaintext123" not in stored
    assert stored.startswith("pbkdf2_sha256$")
