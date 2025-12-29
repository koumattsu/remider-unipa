def test_outcome_analytics_training_contract(client):
    res = client.get(
        "/api/v1/analytics/outcomes/training",
        params={"version": "v1", "limit": 10},
    )
    assert res.status_code == 200

    data = res.json()
    assert isinstance(data, dict)
    assert set(data.keys()) == {"range", "items"}

    r = data["range"]
    assert isinstance(r, dict)
    assert set(r.keys()) == {"timezone", "version", "from", "to", "limit"}
    assert r["timezone"] == "Asia/Tokyo"
    assert r["version"] in ("v1", None)
    assert isinstance(r["limit"], int)

    items = data["items"]
    assert isinstance(items, list)

    if items:
        it0 = items[0]
        assert set(it0.keys()) == {"task_id", "deadline", "outcome", "feature_version", "features"}
        assert isinstance(it0["task_id"], int)
        assert isinstance(it0["outcome"], str)
        assert isinstance(it0["feature_version"], str)
        assert isinstance(it0["features"], dict)
