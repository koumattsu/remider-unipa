def test_actions_applied_create_and_list_contract(client):
    # create
    res = client.post(
        "/api/v1/analytics/actions/applied",
        params={"action_id": "demo-action", "bucket": "week"},
        json={"payload": {"example": 1}},
    )
    assert res.status_code == 200
    data = res.json()
    assert data.get("ok") is True
    ev = data.get("event")
    assert isinstance(ev, dict)
    for k in ["id", "action_id", "bucket", "applied_at", "payload", "created_at"]:
        assert k in ev
    assert isinstance(ev["id"], int)
    assert ev["action_id"] == "demo-action"
    assert ev["bucket"] == "week"
    assert isinstance(ev["payload"], dict)

    # list
    res2 = client.get("/api/v1/analytics/actions/applied", params={"limit": 10})
    assert res2.status_code == 200
    body = res2.json()
    assert isinstance(body, dict)
    assert "items" in body
    assert isinstance(body["items"], list)
