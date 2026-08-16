"""Config drift detection and classification, with the running config faked."""

from datetime import UTC, datetime, timedelta

import pytest

from app import jobs as jobs_module
from app.models.audit import AuditEvent
from app.models.change import Change
from app.models.device import Device
from app.models.drift import DriftEvent
from app.models.job import Job
from app.models.user import User
from tests.test_auth_users import bearer, make_user

BASE_CONFIG = "hostname leaf1\ninterface Ethernet1\n   description uplink\n"
EDITED_CONFIG = "hostname leaf1\ninterface Ethernet1\n   description HAND-EDITED\n"


@pytest.fixture
def device_id(test_db):
    with test_db.session_factory() as db:
        device = Device(
            hostname="leaf1", ip_address="172.20.20.12", site="LAB", device_type="arista_eos"
        )
        db.add(device)
        db.commit()
        return device.id


def sweep(test_db, monkeypatch, config_text) -> int:
    monkeypatch.setattr(jobs_module, "SessionLocal", test_db.session_factory)
    monkeypatch.setattr(jobs_module, "_get_running_config", lambda device: config_text)
    with test_db.session_factory() as db:
        job = Job(type="config_backup", params={}, requested_by="scheduler")
        db.add(job)
        db.commit()
        job_id = job.id
    jobs_module.run_job(job_id)
    return job_id


def seed_change(test_db, device_ids, *, status="succeeded", minutes_ago=0) -> int:
    when = datetime.now(UTC) - timedelta(minutes=minutes_ago)
    with test_db.session_factory() as db:
        author = db.query(User).filter(User.username == "olivia").first()
        if author is None:
            author = User(username="olivia", password_hash="x", role="operator")
            db.add(author)
            db.flush()
        change = Change(
            title="Rename uplink description",
            config_snippet=EDITED_CONFIG,
            device_ids=device_ids,
            author_id=author.id,
            status=status,
            approved_at=when,
            executed_at=None if status == "executing" else when,
        )
        db.add(change)
        db.commit()
        return change.id


def events(test_db) -> list[DriftEvent]:
    with test_db.session_factory() as db:
        return db.query(DriftEvent).order_by(DriftEvent.id).all()


# --- detection ---


def test_first_snapshot_is_a_baseline_not_drift(client, test_db, monkeypatch, device_id):
    sweep(test_db, monkeypatch, BASE_CONFIG)
    assert events(test_db) == []


def test_unchanged_config_produces_no_event(client, test_db, monkeypatch, device_id):
    sweep(test_db, monkeypatch, BASE_CONFIG)
    sweep(test_db, monkeypatch, BASE_CONFIG)
    assert events(test_db) == []


def test_unexplained_edit_is_unauthorized_and_open(client, test_db, monkeypatch, device_id):
    sweep(test_db, monkeypatch, BASE_CONFIG)
    sweep(test_db, monkeypatch, EDITED_CONFIG)

    (event,) = events(test_db)
    assert event.classification == "unauthorized"
    assert event.status == "open"
    assert event.change_id is None
    assert event.previous_hash != event.current_hash


def test_diff_shows_the_changed_lines(client, test_db, monkeypatch, device_id):
    sweep(test_db, monkeypatch, BASE_CONFIG)
    sweep(test_db, monkeypatch, EDITED_CONFIG)
    event_id = events(test_db)[0].id

    viewer = make_user(test_db, username="vic", role="viewer")
    diff = client.get(f"/v1/drift/{event_id}/diff", headers=bearer(client, viewer)).text
    assert "-   description uplink" in diff
    assert "+   description HAND-EDITED" in diff


def test_drift_job_reports_the_count(client, test_db, monkeypatch, device_id):
    sweep(test_db, monkeypatch, BASE_CONFIG)
    job_id = sweep(test_db, monkeypatch, EDITED_CONFIG)
    with test_db.session_factory() as db:
        assert db.get(Job, job_id).result["drifted"] == 1


# --- correlation with the change workflow ---


def test_executed_change_explains_the_drift(client, test_db, monkeypatch, device_id):
    sweep(test_db, monkeypatch, BASE_CONFIG)
    change_id = seed_change(test_db, [device_id])
    sweep(test_db, monkeypatch, EDITED_CONFIG)

    (event,) = events(test_db)
    assert event.classification == "authorized"
    assert event.change_id == change_id
    assert event.status == "acknowledged"
    assert event.acknowledged_by == "change-workflow"
    assert str(change_id) in event.note


def test_in_flight_change_explains_the_drift(client, test_db, monkeypatch, device_id):
    """The post-change snapshot is taken while the change is still 'executing'."""
    sweep(test_db, monkeypatch, BASE_CONFIG)
    seed_change(test_db, [device_id], status="executing")
    sweep(test_db, monkeypatch, EDITED_CONFIG)

    assert events(test_db)[0].classification == "authorized"


def test_change_targeting_another_device_does_not_excuse_drift(
    client, test_db, monkeypatch, device_id
):
    sweep(test_db, monkeypatch, BASE_CONFIG)
    seed_change(test_db, [device_id + 500])
    sweep(test_db, monkeypatch, EDITED_CONFIG)

    assert events(test_db)[0].classification == "unauthorized"


def test_change_outside_the_window_does_not_excuse_drift(client, test_db, monkeypatch, device_id):
    sweep(test_db, monkeypatch, BASE_CONFIG)
    seed_change(test_db, [device_id], minutes_ago=24 * 60)
    sweep(test_db, monkeypatch, EDITED_CONFIG)

    assert events(test_db)[0].classification == "unauthorized"


def test_proposed_change_does_not_excuse_drift(client, test_db, monkeypatch, device_id):
    sweep(test_db, monkeypatch, BASE_CONFIG)
    seed_change(test_db, [device_id], status="proposed")
    sweep(test_db, monkeypatch, EDITED_CONFIG)

    assert events(test_db)[0].classification == "unauthorized"


# --- API ---


def test_list_filters_to_the_alerting_query(client, test_db, monkeypatch, device_id):
    sweep(test_db, monkeypatch, BASE_CONFIG)
    sweep(test_db, monkeypatch, EDITED_CONFIG)
    sweep(test_db, monkeypatch, EDITED_CONFIG + "ntp server 10.0.0.1\n")

    assert client.get("/v1/drift").json()["total"] == 2
    operator = make_user(test_db, username="opal", role="operator")
    client.post(
        f"/v1/drift/{events(test_db)[0].id}/acknowledge",
        json={"note": "console fix, ticket NET-412"},
        headers=bearer(client, operator),
    )

    alerting = client.get("/v1/drift?status=open&classification=unauthorized").json()
    assert alerting["total"] == 1
    assert alerting["items"][0]["classification"] == "unauthorized"
    assert client.get(f"/v1/drift?device_id={device_id + 500}").json()["total"] == 0


def test_diff_requires_an_identity(client, test_db, monkeypatch, device_id):
    sweep(test_db, monkeypatch, BASE_CONFIG)
    sweep(test_db, monkeypatch, EDITED_CONFIG)
    event_id = events(test_db)[0].id

    assert client.get(f"/v1/drift/{event_id}").status_code == 200
    assert client.get(f"/v1/drift/{event_id}/diff").status_code == 401


def test_unknown_event_is_404(client, test_db):
    assert client.get("/v1/drift/4242").status_code == 404


def test_acknowledge_records_who_and_why(client, test_db, monkeypatch, device_id):
    sweep(test_db, monkeypatch, BASE_CONFIG)
    sweep(test_db, monkeypatch, EDITED_CONFIG)
    event_id = events(test_db)[0].id

    operator = make_user(test_db, username="opal", role="operator")
    resp = client.post(
        f"/v1/drift/{event_id}/acknowledge",
        json={"note": "Console fix during the outage, ticket NET-412"},
        headers=bearer(client, operator),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "acknowledged"
    assert resp.json()["acknowledged_by"] == "opal"

    with test_db.session_factory() as db:
        assert "drift.acknowledge" in [e.action for e in db.query(AuditEvent).all()]


def test_acknowledge_requires_operator_and_a_note(client, test_db, monkeypatch, device_id):
    sweep(test_db, monkeypatch, BASE_CONFIG)
    sweep(test_db, monkeypatch, EDITED_CONFIG)
    event_id = events(test_db)[0].id

    viewer = make_user(test_db, username="vic", role="viewer")
    operator = make_user(test_db, username="opal", role="operator")
    body = {"note": "explained"}
    assert client.post(f"/v1/drift/{event_id}/acknowledge", json=body).status_code == 401
    denied = client.post(
        f"/v1/drift/{event_id}/acknowledge", json=body, headers=bearer(client, viewer)
    )
    assert denied.status_code == 403
    empty = client.post(
        f"/v1/drift/{event_id}/acknowledge", json={"note": ""}, headers=bearer(client, operator)
    )
    assert empty.status_code == 422


def test_acknowledging_twice_conflicts(client, test_db, monkeypatch, device_id):
    sweep(test_db, monkeypatch, BASE_CONFIG)
    sweep(test_db, monkeypatch, EDITED_CONFIG)
    event_id = events(test_db)[0].id

    operator = make_user(test_db, username="opal", role="operator")
    headers = bearer(client, operator)
    body = {"note": "same as before"}
    first = client.post(f"/v1/drift/{event_id}/acknowledge", json=body, headers=headers)
    assert first.status_code == 200
    second = client.post(f"/v1/drift/{event_id}/acknowledge", json=body, headers=headers)
    assert second.status_code == 409
