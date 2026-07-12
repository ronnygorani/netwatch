def test_list_devices_empty(client):
    response = client.get("/v1/devices")
    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0, "limit": 100, "offset": 0}


def test_create_device(create_device):
    data = create_device(hostname="SW-01", ip_address="10.0.0.1", site="HQ")
    assert data["hostname"] == "SW-01"
    assert data["site"] == "HQ"
    assert data["device_type"] == "cisco_ios"
    assert data["is_active"] is True


def test_create_duplicate_ip_returns_409(client, create_device, auth_headers):
    create_device(ip_address="10.0.0.1")
    response = client.post(
        "/v1/devices",
        json={"hostname": "SW-DUPE", "ip_address": "10.0.0.1", "site": "HQ"},
        headers=auth_headers,
    )
    assert response.status_code == 409


def test_get_device(client, create_device):
    device = create_device(hostname="SW-01")
    response = client.get(f"/v1/devices/{device['id']}")
    assert response.status_code == 200
    assert response.json()["hostname"] == "SW-01"


def test_get_nonexistent_device(client):
    response = client.get("/v1/devices/999")
    assert response.status_code == 404


def test_update_device(client, create_device, auth_headers):
    device = create_device()
    response = client.patch(
        f"/v1/devices/{device['id']}", json={"site": "Branch-A"}, headers=auth_headers
    )
    assert response.status_code == 200
    assert response.json()["site"] == "Branch-A"


def test_update_rejects_empty_strings(client, create_device, auth_headers):
    """PATCH with an empty hostname must 422, not blank the device (FM-A8)."""
    device = create_device(hostname="SW-01")
    response = client.patch(
        f"/v1/devices/{device['id']}", json={"hostname": ""}, headers=auth_headers
    )
    assert response.status_code == 422
    assert client.get(f"/v1/devices/{device['id']}").json()["hostname"] == "SW-01"


def test_filter_devices_by_site(client, create_device):
    create_device(hostname="SW-01", ip_address="10.0.0.1", site="HQ")
    create_device(hostname="SW-02", ip_address="10.0.0.2", site="Branch-B")
    response = client.get("/v1/devices?site=Branch-B")
    assert response.status_code == 200
    page = response.json()
    assert page["total"] == 1
    assert all(d["site"] == "Branch-B" for d in page["items"])


def test_pagination(client, create_device):
    for n in range(3):
        create_device(hostname=f"SW-{n}", ip_address=f"10.0.0.{n + 1}")
    first = client.get("/v1/devices?limit=2&offset=0").json()
    second = client.get("/v1/devices?limit=2&offset=2").json()
    assert first["total"] == 3 and second["total"] == 3
    assert len(first["items"]) == 2 and len(second["items"]) == 1
    ids = {d["id"] for d in first["items"]} | {d["id"] for d in second["items"]}
    assert len(ids) == 3  # no overlap, nothing missed


def test_delete_device(client, create_device, auth_headers):
    device = create_device(ip_address="10.0.0.99")
    assert client.delete(f"/v1/devices/{device['id']}", headers=auth_headers).status_code == 204
    assert client.get(f"/v1/devices/{device['id']}").status_code == 404


def test_delete_cascades_metrics(client, create_device, auth_headers):
    """Deleting a device destroys its metric history (documented CASCADE contract)."""
    device = create_device()
    client.post(
        "/v1/metrics", json={"device_id": device["id"], "status": "up"}, headers=auth_headers
    )
    assert client.delete(f"/v1/devices/{device['id']}", headers=auth_headers).status_code == 204
    assert client.get(f"/v1/devices/{device['id']}/metrics").status_code == 404
