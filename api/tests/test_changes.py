"""The change workflow: propose, approve (never your own), execute, audit."""

import pytest

from app import jobs as jobs_module
from app.models.audit import AuditEvent
from app.models.change import Change
from tests.test_auth_users import bearer, make_user

SNIPPET = "vlan 300\n   name TEST\n"


@pytest.fixture(autouse=True)
def no_redis(monkeypatch):
    from app.routers import changes as changes_router

    monkeypatch.setattr(changes_router, "enqueue_job", lambda job_id: None)


@pytest.fixture
def people(test_db):
    return {
        "author": make_user(test_db, username="olivia", role="operator"),
        "approver": make_user(test_db, username="adam", role="approver"),
        "viewer": make_user(test_db, username="vic", role="viewer"),
        "admin": make_user(test_db, username="root", role="admin"),
    }


def propose(client, people, create_device, **overrides):
    device = overrides.pop("device", None) or create_device()
    body = {
        "title": "Add VLAN 300",
        "config_snippet": SNIPPET,
        "device_ids": [device["id"]],
        **overrides,
    }
    return client.post("/v1/changes", json=body, headers=bearer(client, people["author"]))


def test_propose_requires_operator(client, people, create_device):
    device = create_device()
    body = {"title": "x", "config_snippet": SNIPPET, "device_ids": [device["id"]]}
    denied = client.post("/v1/changes", json=body, headers=bearer(client, people["viewer"]))
    assert denied.status_code == 403


def test_propose_creates_proposed_change(client, people, create_device):
    resp = propose(client, people, create_device)
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "proposed"
    assert body["approver_id"] is None


def test_propose_rejects_unknown_device(client, people):
    body = {"title": "x", "config_snippet": SNIPPET, "device_ids": [4242]}
    resp = client.post("/v1/changes", json=body, headers=bearer(client, people["author"]))
    assert resp.status_code == 422


def test_author_cannot_approve_own_change(client, people, create_device, test_db):
    """The two-person rule, the point of the whole workflow."""
    # Give the author approver rights: role alone must not let them self-approve.
    from app.models.user import User

    with test_db.session_factory() as db:
        db.query(User).filter(User.username == "olivia").update({"role": "approver"})
        db.commit()

    change_id = propose(client, people, create_device).json()["id"]
    resp = client.post(f"/v1/changes/{change_id}/approve", headers=bearer(client, people["author"]))
    assert resp.status_code == 403
    assert "your own" in resp.json()["detail"]


def test_approver_approves_and_it_is_audited(client, people, create_device, test_db):
    change_id = propose(client, people, create_device).json()["id"]
    resp = client.post(
        f"/v1/changes/{change_id}/approve", headers=bearer(client, people["approver"])
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"
    assert resp.json()["approved_at"] is not None

    with test_db.session_factory() as db:
        actions = [e.action for e in db.query(AuditEvent).all()]
    assert "change.propose" in actions
    assert "change.approve" in actions


def test_viewer_cannot_approve(client, people, create_device):
    change_id = propose(client, people, create_device).json()["id"]
    resp = client.post(f"/v1/changes/{change_id}/approve", headers=bearer(client, people["viewer"]))
    assert resp.status_code == 403


def test_reject_records_reason(client, people, create_device):
    change_id = propose(client, people, create_device).json()["id"]
    resp = client.post(
        f"/v1/changes/{change_id}/reject",
        json={"reason": "VLAN 300 is reserved"},
        headers=bearer(client, people["approver"]),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"
    assert resp.json()["rejection_reason"] == "VLAN 300 is reserved"


def test_cannot_execute_unapproved_change(client, people, create_device):
    change_id = propose(client, people, create_device).json()["id"]
    resp = client.post(f"/v1/changes/{change_id}/execute", headers=bearer(client, people["author"]))
    assert resp.status_code == 409


def test_cannot_approve_twice(client, people, create_device):
    change_id = propose(client, people, create_device).json()["id"]
    headers = bearer(client, people["approver"])
    assert client.post(f"/v1/changes/{change_id}/approve", headers=headers).status_code == 200
    assert client.post(f"/v1/changes/{change_id}/approve", headers=headers).status_code == 409


def test_execute_after_approval_queues_job(client, people, create_device):
    change_id = propose(client, people, create_device).json()["id"]
    client.post(f"/v1/changes/{change_id}/approve", headers=bearer(client, people["approver"]))
    resp = client.post(f"/v1/changes/{change_id}/execute", headers=bearer(client, people["author"]))
    assert resp.status_code == 202
    assert resp.json()["status"] == "executing"
    assert client.get(f"/v1/jobs/{resp.json()['job_id']}").json()["type"] == "execute_change"


def test_audit_trail_requires_approver_role(client, people):
    assert client.get("/v1/audit").status_code == 401
    assert client.get("/v1/audit", headers=bearer(client, people["viewer"])).status_code == 403
    assert client.get("/v1/audit", headers=bearer(client, people["approver"])).status_code == 200


# --- executor ---


def test_execute_applies_and_marks_succeeded(client, people, create_device, test_db, monkeypatch):
    monkeypatch.setattr(jobs_module, "SessionLocal", test_db.session_factory)
    monkeypatch.setattr(jobs_module, "_backup_one", lambda db, device: "backed_up")
    monkeypatch.setattr(
        jobs_module,
        "_apply_to_device",
        lambda device, snippet: {"status": "applied", "diff": "+ vlan 300"},
    )

    change_id = propose(client, people, create_device).json()["id"]
    client.post(f"/v1/changes/{change_id}/approve", headers=bearer(client, people["approver"]))
    job_id = client.post(
        f"/v1/changes/{change_id}/execute", headers=bearer(client, people["author"])
    ).json()["job_id"]

    jobs_module.run_job(job_id)

    with test_db.session_factory() as db:
        change = db.get(Change, change_id)
        assert change.status == "succeeded"
        assert change.diff  # per-device diffs captured
        assert change.executed_at is not None


def test_execute_rollback_marks_change_rolled_back(
    client, people, create_device, test_db, monkeypatch
):
    """A device that stops answering after commit gets reverted, and the change says so."""
    monkeypatch.setattr(jobs_module, "SessionLocal", test_db.session_factory)
    monkeypatch.setattr(jobs_module, "_backup_one", lambda db, device: "backed_up")
    monkeypatch.setattr(
        jobs_module,
        "_apply_to_device",
        lambda device, snippet: {
            "status": "rolled_back",
            "diff": "+ vlan 300",
            "error": "unreachable after commit",
        },
    )

    change_id = propose(client, people, create_device).json()["id"]
    client.post(f"/v1/changes/{change_id}/approve", headers=bearer(client, people["approver"]))
    job_id = client.post(
        f"/v1/changes/{change_id}/execute", headers=bearer(client, people["author"])
    ).json()["job_id"]

    jobs_module.run_job(job_id)

    with test_db.session_factory() as db:
        assert db.get(Change, change_id).status == "rolled_back"
