def test_list_devices_empty(client):
    response = client.get("/devices")
    assert response.status_code == 200
    assert response.json() == []


def test_create_device(client):
    payload = {"hostname": "SW-01", "ip_address": "10.0.0.1", "site": "HQ"}
    response = client.post("/devices", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["hostname"] == "SW-01"
    assert data["site"] == "HQ"
    assert data["device_type"] == "cisco_ios"
    assert data["is_active"] is True


def test_create_duplicate_ip_returns_409(client):
    payload = {"hostname": "SW-DUPE", "ip_address": "10.0.0.1", "site": "HQ"}
    response = client.post("/devices", json=payload)
    assert response.status_code == 409


def test_get_device(client):
    response = client.get("/devices/1")
    assert response.status_code == 200
    assert response.json()["hostname"] == "SW-01"


def test_get_nonexistent_device(client):
    response = client.get("/devices/999")
    assert response.status_code == 404


def test_update_device(client):
    response = client.patch("/devices/1", json={"site": "Branch-A"})
    assert response.status_code == 200
    assert response.json()["site"] == "Branch-A"


def test_filter_devices_by_site(client):
    client.post("/devices", json={"hostname": "SW-02", "ip_address": "10.0.0.2", "site": "Branch-B"})
    response = client.get("/devices?site=Branch-B")
    assert response.status_code == 200
    assert all(d["site"] == "Branch-B" for d in response.json())


def test_delete_device(client):
    client.post("/devices", json={"hostname": "SW-DEL", "ip_address": "10.0.0.99", "site": "HQ"})
    dev_id = client.get("/devices").json()[-1]["id"]
    assert client.delete(f"/devices/{dev_id}").status_code == 204
    assert client.get(f"/devices/{dev_id}").status_code == 404
