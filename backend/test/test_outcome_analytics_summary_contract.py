def test_outcome_analytics_summary_contract(client):
    res = client.get("/api/v1/analytics/outcomes/summary", params={"bucket": "week"})
    assert res.status_code == 200

    data = res.json()
    assert isinstance(data, dict)
    assert set(data.keys()) == {"range", "items"}

    r = data["range"]
    assert isinstance(r, dict)
    assert set(r.keys()) == {"timezone", "bucket", "from", "to"}
    assert r["timezone"] == "Asia/Tokyo"
    assert r["bucket"] in ("week", "month")

    items = data["items"]
    assert isinstance(items, list)

    # ✅ shape 固定（空配列でもOK）
    if items:
        it0 = items[0]
        assert set(it0.keys()) == {"period_start", "total", "done", "missed", "done_rate"}
        assert isinstance(it0["period_start"], str)
        assert isinstance(it0["total"], int)
        assert isinstance(it0["done"], int)
        assert isinstance(it0["missed"], int)
        assert isinstance(it0["done_rate"], float)
