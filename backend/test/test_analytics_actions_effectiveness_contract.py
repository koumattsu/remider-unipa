def test_actions_effectiveness_contract(client):
    # まずイベントを1件作る
    r = client.post(
        "/api/v1/analytics/actions/applied",
        params={"action_id": "demo-action", "bucket": "week"},
    )
    assert r.status_code == 200

    # effectiveness を叩く
    res = client.get("/api/v1/analytics/actions/effectiveness")
    assert res.status_code == 200

    data = res.json()
    assert isinstance(data, dict)
    assert set(data.keys()) == {"range", "items"}

    rng = data["range"]
    assert isinstance(rng, dict)
    for k in ["timezone", "from", "to", "window_days", "min_total", "limit_events"]:
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
        "applied_count",
        "measured_count",
        "improved_count",
        "improved_rate",
        "avg_delta_missed_rate",
    }

    assert isinstance(row["action_id"], str)
    assert isinstance(row["applied_count"], int) and row["applied_count"] >= 1
    assert isinstance(row["measured_count"], int) and row["measured_count"] >= 0
    assert isinstance(row["improved_count"], int) and row["improved_count"] >= 0
    assert isinstance(row["improved_rate"], float)
    assert isinstance(row["avg_delta_missed_rate"], float)
