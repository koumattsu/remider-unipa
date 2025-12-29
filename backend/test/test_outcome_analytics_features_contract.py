# backend/test/test_outcome_analytics_features_contract.py

def test_outcome_analytics_features_contract(client):
    from app.main import app
    analytics_paths = [r.path for r in app.routes if "/api/v1/analytics/" in r.path]
    print("ANALYTICS ROUTES:", sorted(analytics_paths))

    from app.api.v1.endpoints import analytics_outcomes as ao
    print("AO FILE:", ao.__file__)
    print("AO HAS FEATURES FUNC:", hasattr(ao, "list_outcome_feature_snapshots"))

    res = client.get("/api/v1/analytics/outcomes/features", params={"version": "v1", "limit": 10})
    assert res.status_code == 200

    data = res.json()
    assert isinstance(data, dict)
    assert set(data.keys()) == {"range", "items"}

    r = data["range"]
    assert isinstance(r, dict)
    assert set(r.keys()) == {"timezone", "version", "from", "to", "limit"}
    assert r["timezone"] == "Asia/Tokyo"
    assert r["version"] in (None, "v1")
    assert isinstance(r["limit"], int)

    items = data["items"]
    assert isinstance(items, list)

    if items:
        it0 = items[0]
        assert set(it0.keys()) == {"task_id", "deadline", "feature_version", "features", "created_at"}
        assert isinstance(it0["task_id"], int)
        assert isinstance(it0["feature_version"], str)
        assert isinstance(it0["features"], dict)
