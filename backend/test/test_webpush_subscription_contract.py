# backend/tests/test_webpush_subscription_contract.py

def test_webpush_public_key_contract(client):
    res = client.get("/api/v1/notifications/webpush/public-key")
    assert res.status_code == 200

    data = res.json()
    assert "publicKey" in data
    assert isinstance(data["publicKey"], str)

def test_webpush_list_subscriptions_contract(client):
    res = client.get("/api/v1/notifications/webpush/subscriptions")
    assert res.status_code == 200

    items = res.json()
    assert isinstance(items, list)

    if not items:
        return

    row = items[0]
    assert isinstance(row["id"], int)
    assert isinstance(row["endpoint"], str)
    assert isinstance(row["is_active"], bool)
    assert isinstance(row["created_at"], str)


def test_webpush_upsert_subscription_contract(client):
    payload = {
        "endpoint": "https://example.com/endpoint/123",
        "keys": {
            "p256dh": "dummy-p256dh",
            "auth": "dummy-auth",
        },
        "device_label": "MacBook Chrome",
    }

    res = client.post(
        "/api/v1/notifications/webpush/subscriptions",
        json=payload,
    )
    assert res.status_code == 201

    data = res.json()
    assert isinstance(data["id"], int)
    assert data["endpoint"] == payload["endpoint"]
    assert data["is_active"] is True
    assert isinstance(data["created_at"], str)


def test_webpush_deactivate_by_endpoint_contract(client):
    endpoint = "https://example.com/endpoint/123"

    res = client.delete(
        "/api/v1/notifications/webpush/subscriptions/by-endpoint",
        params={"endpoint": endpoint},
    )
    assert res.status_code == 204
