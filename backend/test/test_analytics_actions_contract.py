# backend/tests/test_analytics_actions_contract.py

def test_actions_applied_post_contract(client):
    """
    契約テスト: POST /api/v1/analytics/actions/applied の shape を固定
    """
    r = client.post(
        "/api/v1/analytics/actions/applied",
        params={"action_id": "demo-action", "bucket": "week"},
        json={"applied_at": None, "payload": {"k": "v"}},
    )
    assert r.status_code == 200

    data = r.json()
    assert isinstance(data, dict)
    assert set(data.keys()) == {"ok", "event"}

    assert data["ok"] is True

    ev = data["event"]
    assert isinstance(ev, dict)
    assert set(ev.keys()) == {
        "id",
        "action_id",
        "bucket",
        "applied_at",
        "payload",
        "created_at",
    }

    assert isinstance(ev["id"], int)
    assert ev["action_id"] == "demo-action"
    assert ev["bucket"] == "week"
    assert isinstance(ev["applied_at"], str)  # ISO string
    assert isinstance(ev["created_at"], str)  # ISO string
    assert isinstance(ev["payload"], dict)


def test_actions_effectiveness_contract(client):
    """
    契約テスト: GET /api/v1/analytics/actions/effectiveness の shape を固定
    - データが少なくても items は [] でもOK（shapeだけ固定）
    """
    # まずイベントを1件作る（itemsが空でも range の shape が安定する）
    r = client.post(
        "/api/v1/analytics/actions/applied",
        params={"action_id": "demo-action", "bucket": "week"},
        json={"applied_at": None, "payload": {}},
    )
    assert r.status_code == 200

    res = client.get("/api/v1/analytics/actions/effectiveness")
    assert res.status_code == 200

    data = res.json()
    assert isinstance(data, dict)
    assert set(data.keys()) == {"range", "items"}

    rng = data["range"]
    assert isinstance(rng, dict)
    assert set(rng.keys()) == {
        "timezone",
        "from",
        "to",
        "window_days",
        "min_total",
        "limit_events",
    }

    assert isinstance(rng["timezone"], str)
    # from/to は None or ISO
    assert (rng["from"] is None) or isinstance(rng["from"], str)
    assert (rng["to"] is None) or isinstance(rng["to"], str)
    assert isinstance(rng["window_days"], int)
    assert isinstance(rng["min_total"], int)
    assert isinstance(rng["limit_events"], int)

    items = data["items"]
    assert isinstance(items, list)
    for x in items:
        assert isinstance(x, dict)
        assert set(x.keys()) == {
            "action_id",
            "applied_count",
            "measured_count",
            "improved_count",
            "improved_rate",
            "avg_delta_missed_rate",
        }
        assert isinstance(x["action_id"], str)
        assert isinstance(x["applied_count"], int)
        assert isinstance(x["measured_count"], int)
        assert isinstance(x["improved_count"], int)
        assert isinstance(x["improved_rate"], (int, float))
        assert isinstance(x["avg_delta_missed_rate"], (int, float))


def test_actions_effectiveness_by_feature_contract(client):
    """
    契約テスト: GET /api/v1/analytics/actions/effectiveness/by-feature の shape を固定
    """
    r = client.post(
        "/api/v1/analytics/actions/applied",
        params={"action_id": "demo-action", "bucket": "week"},
        json={"applied_at": None, "payload": {}},
    )
    assert r.status_code == 200

    res = client.get("/api/v1/analytics/actions/effectiveness/by-feature", params={"version": "v1"})
    assert res.status_code == 200

    data = res.json()
    assert isinstance(data, dict)
    assert set(data.keys()) == {"range", "items"}

    rng = data["range"]
    assert isinstance(rng, dict)
    assert set(rng.keys()) == {
        "timezone",
        "version",
        "from",
        "to",
        "window_days",
        "min_total",
        "limit_events",
        "limit_samples_per_event",
    }

    assert isinstance(rng["timezone"], str)
    assert isinstance(rng["version"], str)
    assert (rng["from"] is None) or isinstance(rng["from"], str)
    assert (rng["to"] is None) or isinstance(rng["to"], str)
    assert isinstance(rng["window_days"], int)
    assert isinstance(rng["min_total"], int)
    assert isinstance(rng["limit_events"], int)
    assert isinstance(rng["limit_samples_per_event"], int)

    items = data["items"]
    assert isinstance(items, list)
    for x in items:
        assert isinstance(x, dict)
        assert set(x.keys()) == {
            "action_id",
            "feature_key",
            "feature_value",
            "total_events",
            "improved_events",
            "improved_rate",
        }
        assert isinstance(x["action_id"], str)
        assert isinstance(x["feature_key"], str)
        assert isinstance(x["feature_value"], str)
        assert isinstance(x["total_events"], int)
        assert isinstance(x["improved_events"], int)
        assert isinstance(x["improved_rate"], (int, float))

def test_actions_effectiveness_snapshots_contract(client):
    """
    契約テスト: GET /api/v1/analytics/actions/effectiveness/snapshots の shape を固定
    - items が空でもOK（shapeだけ固定）
    """
    res = client.get("/api/v1/analytics/actions/effectiveness/snapshots", params={"limit": 20})
    assert res.status_code == 200

    data = res.json()
    assert isinstance(data, dict)
    assert set(data.keys()) == {"range", "items"}

    rng = data["range"]
    assert isinstance(rng, dict)
    assert set(rng.keys()) == {"timezone", "from", "to", "limit", "action_id"}
    assert isinstance(rng["timezone"], str)
    assert (rng["from"] is None) or isinstance(rng["from"], str)
    assert (rng["to"] is None) or isinstance(rng["to"], str)
    assert isinstance(rng["limit"], int)
    assert (rng["action_id"] is None) or isinstance(rng["action_id"], str)

    items = data["items"]
    assert isinstance(items, list)
    for x in items:
        assert isinstance(x, dict)
        assert set(x.keys()) == {
            "id",
            "captured_at",
            "bucket",
            "window_days",
            "min_total",
            "limit_events",
            "action_id",
            "applied_count",
            "measured_count",
            "improved_count",
            "improved_rate",
            "avg_delta_missed_rate",
        }
        assert isinstance(x["id"], int)
        assert isinstance(x["captured_at"], str)
        assert isinstance(x["bucket"], str)
        assert isinstance(x["window_days"], int)
        assert isinstance(x["min_total"], int)
        assert isinstance(x["limit_events"], int)
        assert isinstance(x["action_id"], str)
        assert isinstance(x["applied_count"], int)
        assert isinstance(x["measured_count"], int)
        assert isinstance(x["improved_count"], int)
        assert isinstance(x["improved_rate"], (int, float))
        assert isinstance(x["avg_delta_missed_rate"], (int, float))
