"""Config templating: variable inheritance, per-site differences, rendering."""

from app.models.config_template import ConfigTemplate
from app.models.device import Device
from app.templating import deep_merge, render_for_device, resolve_variables
from tests.test_auth_users import bearer, make_user

VLAN_TEMPLATE = """{% for vlan in vlans %}
vlan {{ vlan.id }}
   name {{ vlan.name }}
{% endfor %}
"""


def _operator(test_db):
    return make_user(test_db, username="opal", role="operator")


def _device(test_db, hostname="sw1", ip="10.0.0.1", site="HQ") -> int:
    with test_db.session_factory() as db:
        device = Device(hostname=hostname, ip_address=ip, site=site, device_type="arista_eos")
        db.add(device)
        db.commit()
        return device.id


# --- merge semantics ---


def test_deep_merge_overlay_wins_and_nests():
    base = {"ntp": {"servers": ["a"], "timezone": "UTC"}, "mtu": 1500}
    overlay = {"ntp": {"servers": ["b"]}, "banner": "hi"}
    assert deep_merge(base, overlay) == {
        # Nested dict merged key by key: timezone survives.
        "ntp": {"servers": ["b"], "timezone": "UTC"},
        "mtu": 1500,
        "banner": "hi",
    }


def test_lists_replace_rather_than_append():
    """Ansible's default, and the predictable choice: a site that declares
    vlans gets exactly those, not the union with global."""
    assert deep_merge({"vlans": [1, 2]}, {"vlans": [9]}) == {"vlans": [9]}


# --- inheritance ---


def set_vars(client, creds, scope, ref, data):
    return client.put(
        "/v1/variables",
        json={"scope": scope, "scope_ref": ref, "data": data},
        headers=bearer(client, creds),
    )


def test_device_inherits_global_then_site(client, test_db):
    creds = _operator(test_db)
    device_id = _device(test_db, site="HQ")
    set_vars(client, creds, "global", None, {"mtu": 1500, "vlans": [{"id": 10, "name": "MGMT"}]})
    set_vars(client, creds, "site", "HQ", {"vlans": [{"id": 20, "name": "HQ-USERS"}]})

    resolved = client.get(f"/v1/devices/{device_id}/variables").json()["variables"]
    assert resolved["mtu"] == 1500  # inherited from global
    assert resolved["vlans"] == [{"id": 20, "name": "HQ-USERS"}]  # site overrides


def test_two_sites_get_different_config(client, test_db):
    """The point of the feature: one template, per-site results."""
    creds = _operator(test_db)
    hq = _device(test_db, hostname="hq-sw", ip="10.0.0.1", site="HQ")
    branch = _device(test_db, hostname="br-sw", ip="10.0.0.2", site="Branch-B")

    set_vars(client, creds, "global", None, {"vlans": [{"id": 10, "name": "MGMT"}]})
    set_vars(
        client,
        creds,
        "site",
        "Branch-B",
        {"vlans": [{"id": 10, "name": "MGMT"}, {"id": 99, "name": "BRANCH-ONLY"}]},
    )
    client.put(
        "/v1/templates/vlans",
        json={"name": "vlans", "body": VLAN_TEMPLATE},
        headers=bearer(client, creds),
    )

    out = {
        r["hostname"]: r["rendered"]
        for r in client.post("/v1/templates/vlans/render", json=[hq, branch]).json()
    }
    assert "vlan 10" in out["hq-sw"] and "vlan 99" not in out["hq-sw"]
    assert "vlan 99" in out["br-sw"]  # site-specific VLAN only where declared


def test_device_override_beats_site(client, test_db):
    creds = _operator(test_db)
    device_id = _device(test_db, site="HQ")
    set_vars(client, creds, "global", None, {"mtu": 1500})
    set_vars(client, creds, "site", "HQ", {"mtu": 9000})
    set_vars(client, creds, "device", str(device_id), {"mtu": 1400})

    with test_db.session_factory() as db:
        device = db.get(Device, device_id)
        assert resolve_variables(db, device)["mtu"] == 1400


def test_device_scope_requires_known_device(client, test_db):
    creds = _operator(test_db)
    assert set_vars(client, creds, "device", "4242", {"x": 1}).status_code == 422


def test_global_scope_rejects_ref(client, test_db):
    creds = _operator(test_db)
    assert set_vars(client, creds, "global", "HQ", {"x": 1}).status_code == 422


# --- rendering ---


def test_template_can_use_device_facts(client, test_db):
    creds = _operator(test_db)
    device_id = _device(test_db, hostname="edge-1", site="HQ")
    set_vars(client, creds, "global", None, {})
    client.put(
        "/v1/templates/host",
        json={"name": "host", "body": "hostname {{ device.hostname }}\n"},
        headers=bearer(client, creds),
    )
    out = client.post("/v1/templates/host/render", json=[device_id]).json()
    assert out[0]["rendered"].strip() == "hostname edge-1"


def test_missing_variable_is_an_error_not_a_blank(client, test_db):
    """StrictUndefined: a typo must fail loudly, never render empty into a switch."""
    creds = _operator(test_db)
    device_id = _device(test_db)
    client.put(
        "/v1/templates/oops",
        json={"name": "oops", "body": "mtu {{ mtuu }}\n"},
        headers=bearer(client, creds),
    )
    resp = client.post("/v1/templates/oops/render", json=[device_id])
    assert resp.status_code == 422


def test_sandbox_blocks_python_internals(test_db):
    """Server-side template injection: templates must not reach the runtime."""
    device_id = _device(test_db)
    with test_db.session_factory() as db:
        device = db.get(Device, device_id)
        evil = ConfigTemplate(
            name="evil", body="{{ device.__class__.__mro__[1].__subclasses__() }}"
        )
        try:
            render_for_device(db, evil, device)
            raise AssertionError("sandbox should have blocked attribute access")
        except ValueError:
            pass


def test_template_write_requires_operator(client, test_db):
    viewer = make_user(test_db, username="vera", role="viewer")
    resp = client.put(
        "/v1/templates/x",
        json={"name": "x", "body": "hi"},
        headers=bearer(client, viewer),
    )
    assert resp.status_code == 403


# --- change workflow integration ---


def test_change_from_template_renders_per_device_at_proposal(client, test_db):
    creds = _operator(test_db)
    hq = _device(test_db, hostname="hq-sw", ip="10.0.0.1", site="HQ")
    branch = _device(test_db, hostname="br-sw", ip="10.0.0.2", site="Branch-B")
    set_vars(client, creds, "global", None, {"vlans": [{"id": 10, "name": "MGMT"}]})
    set_vars(client, creds, "site", "Branch-B", {"vlans": [{"id": 99, "name": "BRANCH"}]})
    client.put(
        "/v1/templates/vlans",
        json={"name": "vlans", "body": VLAN_TEMPLATE},
        headers=bearer(client, creds),
    )

    resp = client.post(
        "/v1/changes",
        json={"title": "VLANs", "template_name": "vlans", "device_ids": [hq, branch]},
        headers=bearer(client, creds),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["template_name"] == "vlans"
    # Frozen per-device output: the approver sees exactly what will be pushed.
    assert "vlan 10" in body["rendered"][str(hq)]
    assert "vlan 99" in body["rendered"][str(branch)]


def test_change_requires_exactly_one_source(client, test_db):
    creds = _operator(test_db)
    device_id = _device(test_db)
    both = client.post(
        "/v1/changes",
        json={
            "title": "x",
            "config_snippet": "vlan 5",
            "template_name": "vlans",
            "device_ids": [device_id],
        },
        headers=bearer(client, creds),
    )
    neither = client.post(
        "/v1/changes",
        json={"title": "x", "device_ids": [device_id]},
        headers=bearer(client, creds),
    )
    assert both.status_code == 422
    assert neither.status_code == 422


def test_change_rejects_unknown_template(client, test_db):
    creds = _operator(test_db)
    device_id = _device(test_db)
    resp = client.post(
        "/v1/changes",
        json={"title": "x", "template_name": "nope", "device_ids": [device_id]},
        headers=bearer(client, creds),
    )
    assert resp.status_code == 422
