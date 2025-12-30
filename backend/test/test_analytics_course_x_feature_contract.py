def test_analytics_course_x_feature_contract(client):
    """
    契約テスト: /analytics/outcomes/course-x-feature の shape を固定する
    - read-only 集計
    - range / items を固定
    - items の各要素キーを固定（破壊的変更検知）
    """
    res = client.get(
        "/api/v1/analytics/outcomes/course-x-feature",
        params={"version": "v1", "limit": 2000},
    )
    assert res.status_code == 200

    data = res.json()
    assert isinstance(data, dict)
    assert set(data.keys()) == {"range", "items"}

    r = data["range"]
    assert isinstance(r, dict)

    expected_range_keys = {"timezone", "version", "from", "to", "limit", "course_hash"}
    assert set(r.keys()) == expected_range_keys

    assert isinstance(r["timezone"], str)
    assert isinstance(r["version"], str)
    assert r["from"] is None or isinstance(r["from"], str)
    assert r["to"] is None or isinstance(r["to"], str)
    assert isinstance(r["limit"], int)
    assert r["course_hash"] is None or isinstance(r["course_hash"], str)

    items = data["items"]
    assert isinstance(items, list)

    for row in items:
        expected_keys = {
            "course_hash",
            "feature_key",
            "feature_value",
            "total",
            "missed",
            "missed_rate",
        }
        assert isinstance(row, dict)
        assert set(row.keys()) == expected_keys

        assert isinstance(row["course_hash"], str)
        assert isinstance(row["feature_key"], str)
        assert isinstance(row["feature_value"], str)

        assert isinstance(row["total"], int) and row["total"] >= 0
        assert isinstance(row["missed"], int) and row["missed"] >= 0
        assert isinstance(row["missed_rate"], (int, float))
