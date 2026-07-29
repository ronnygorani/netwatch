"""Job API and the config-backup executor.

Enqueue is patched so the API tests never need a live Redis; the executor is
driven directly through run_job with the queue step bypassed.
"""

import hashlib

import pytest

from app import jobs as jobs_module
from app.models.config_backup import ConfigBackup
from app.models.device import Device
from app.models.job import Job


@pytest.fixture(autouse=True)
def no_redis(monkeypatch):
    """Neutralize the enqueue call in the jobs router for every test here."""
    from app.routers import jobs as jobs_router

    monkeypatch.setattr(jobs_router, "enqueue_job", lambda job_id: None)


def test_create_job_requires_scope(client, make_api_key):
    key = make_api_key(name="reader", scopes="metrics:write")
    resp = client.post("/v1/jobs", json={"type": "config_backup"}, headers={"X-API-Key": key})
    assert resp.status_code == 403


def test_create_job_returns_202_and_queued(client, make_api_key):
    key = make_api_key(name="runner", scopes="jobs:run")
    resp = client.post("/v1/jobs", json={"type": "config_backup"}, headers={"X-API-Key": key})
    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "queued"
    assert body["requested_by"] == "runner"
    assert body["type"] == "config_backup"


def test_unknown_job_type_rejected(client, make_api_key):
    key = make_api_key(name="runner", scopes="jobs:run")
    resp = client.post("/v1/jobs", json={"type": "delete_everything"}, headers={"X-API-Key": key})
    assert resp.status_code == 422


def test_get_job_and_list(client, make_api_key):
    key = make_api_key(name="runner", scopes="jobs:run")
    created = client.post(
        "/v1/jobs", json={"type": "config_backup"}, headers={"X-API-Key": key}
    ).json()
    assert client.get(f"/v1/jobs/{created['id']}").json()["id"] == created["id"]
    assert client.get("/v1/jobs").json()["total"] == 1
    assert client.get("/v1/jobs/9999").status_code == 404


# --- executor, driven directly ---

FAKE_CONFIG = "hostname leaf1\ninterface Management0\n  ip address 172.20.20.12/24\n"


def _patch_config(monkeypatch, text=FAKE_CONFIG):
    monkeypatch.setattr(jobs_module, "_get_running_config", lambda device: text)


def _seed_job_and_device(test_db):
    with test_db.session_factory() as db:
        device = Device(
            hostname="leaf1", ip_address="172.20.20.12", site="LAB", device_type="arista_eos"
        )
        db.add(device)
        job = Job(type="config_backup", params={}, requested_by="runner")
        db.add(job)
        db.commit()
        return job.id, device.id


def test_backup_executor_stores_and_dedupes(client, test_db, monkeypatch):
    _patch_config(monkeypatch)
    monkeypatch.setattr(jobs_module, "SessionLocal", test_db.session_factory)
    job_id, device_id = _seed_job_and_device(test_db)

    jobs_module.run_job(job_id)
    with test_db.session_factory() as db:
        job = db.get(Job, job_id)
        assert job.status == "succeeded"
        assert job.result == {"devices": 1, "backed_up": 1, "unchanged": 0, "failed": 0}
        backups = db.query(ConfigBackup).filter(ConfigBackup.device_id == device_id).all()
        assert len(backups) == 1
        assert backups[0].content_hash == hashlib.sha256(FAKE_CONFIG.encode()).hexdigest()

    # Second run, identical config: stored once, reported unchanged.
    with test_db.session_factory() as db:
        db.add(Job(type="config_backup", params={}, requested_by="runner"))
        db.commit()
        job2_id = db.query(Job).order_by(Job.id.desc()).first().id
    jobs_module.run_job(job2_id)
    with test_db.session_factory() as db:
        assert db.get(Job, job2_id).result["unchanged"] == 1
        assert db.query(ConfigBackup).count() == 1


def test_backup_executor_stores_new_version_on_change(client, test_db, monkeypatch):
    monkeypatch.setattr(jobs_module, "SessionLocal", test_db.session_factory)
    job_id, device_id = _seed_job_and_device(test_db)

    _patch_config(monkeypatch, "config version A")
    jobs_module.run_job(job_id)

    with test_db.session_factory() as db:
        db.add(Job(type="config_backup", params={}, requested_by="runner"))
        db.commit()
        job2_id = db.query(Job).order_by(Job.id.desc()).first().id
    _patch_config(monkeypatch, "config version B")
    jobs_module.run_job(job2_id)

    with test_db.session_factory() as db:
        assert db.query(ConfigBackup).filter(ConfigBackup.device_id == device_id).count() == 2


def test_job_failure_is_recorded(client, test_db, monkeypatch):
    """Executor raising must leave the job 'failed' with an error, not stuck 'running'.

    Exercises the rollback-then-persist path in run_job.
    """
    monkeypatch.setattr(jobs_module, "SessionLocal", test_db.session_factory)

    def boom(db, job):
        raise RuntimeError("executor exploded")

    monkeypatch.setitem(jobs_module.EXECUTORS, "config_backup", boom)
    job_id, _ = _seed_job_and_device(test_db)

    jobs_module.run_job(job_id)
    with test_db.session_factory() as db:
        job = db.get(Job, job_id)
        assert job.status == "failed"
        assert "executor exploded" in job.error
        assert job.finished_at is not None


def test_run_job_ignores_already_started_job(test_db, monkeypatch):
    """A duplicate delivery must not re-run a job that already left 'queued'."""
    monkeypatch.setattr(jobs_module, "SessionLocal", test_db.session_factory)
    calls = []
    monkeypatch.setitem(
        jobs_module.EXECUTORS, "config_backup", lambda db, job: calls.append(1) or {}
    )
    with test_db.session_factory() as db:
        job = Job(type="config_backup", params={}, requested_by="r", status="succeeded")
        db.add(job)
        db.commit()
        job_id = job.id

    jobs_module.run_job(job_id)
    assert calls == []  # executor never invoked for a non-queued job


def test_backup_content_read_requires_scope(client, make_api_key, test_db):
    with test_db.session_factory() as db:
        device = Device(
            hostname="leaf1", ip_address="172.20.20.12", site="LAB", device_type="arista_eos"
        )
        db.add(device)
        db.commit()
        db.add(ConfigBackup(device_id=device.id, content_hash="abc", content="secret config"))
        db.commit()
        backup_id = db.query(ConfigBackup).first().id
        device_id = device.id

    # Metadata list is open; content is scoped.
    assert client.get(f"/v1/devices/{device_id}/backups").json()["total"] == 1
    assert client.get(f"/v1/backups/{backup_id}").status_code == 401

    key = make_api_key(name="auditor", scopes="backups:read")
    resp = client.get(f"/v1/backups/{backup_id}", headers={"X-API-Key": key})
    assert resp.status_code == 200
    assert resp.text == "secret config"
