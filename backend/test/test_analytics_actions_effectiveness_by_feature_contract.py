def test_actions_effectiveness_by_feature_contract(client):
    # まずイベントを1件作る
    r = client.post(
        "/api/v1/analytics/actions/applied",
        params={"action_id": "demo-action", "bucket": "week"},
    )
    assert r.status_code == 200

    # by-feature を叩く
    res = client.get("/api/v1/analytics/actions/effectiveness/by-feature", params={"version": "v1"})
    assert res.status_code == 200

    data = res.json()
    assert isinstance(data, dict)
    assert set(data.keys()) == {"range", "items"}

    rng = data["range"]
    assert isinstance(rng, dict)
    for k in ["timezone", "version", "from", "to", "window_days", "min_total", "limit_events", "limit_samples_per_event"]:
        assert k in rng

    items = data["items"]
    assert isinstance(items, list)

    # demo-action が含まれること（評価不能でも出る）
    found = [x for x in items if x.get("action_id") == "demo-action"]
    assert len(found) == 1
    row = found[0]

    # row shape を固定（破壊的変更検知）
    assert set(row.keys()) == {
        "action_id",
        "feature_key",
        "feature_value",
        "total_events",
        "improved_events",
        "improved_rate",
    }

    assert isinstance(row["action_id"], str)
    assert isinstance(row["feature_key"], str)
    assert isinstance(row["feature_value"], str)
    assert isinstance(row["total_events"], int) and row["total_events"] >= 0
    assert isinstance(row["improved_events"], int) and row["improved_events"] >= 0
    assert isinstance(row["improved_rate"], float)
