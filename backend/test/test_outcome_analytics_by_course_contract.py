def test_outcome_analytics_by_course_contract(client):
    res = client.get("/api/v1/analytics/outcomes/by-course")
    assert res.status_code == 200

    data = res.json()
    assert isinstance(data, dict)
    assert set(data.keys()) == {"range", "items"}

    r = data["range"]
    assert isinstance(r, dict)
    assert set(r.keys()) == {"timezone", "from", "to"}
    assert r["timezone"] == "Asia/Tokyo"

    items = data["items"]
    assert isinstance(items, list)

    if items:
        it0 = items[0]
        assert set(it0.keys()) == {"course_name", "total", "missed", "missed_rate"}
        assert isinstance(it0["course_name"], str)
        assert isinstance(it0["total"], int)
        assert isinstance(it0["missed"], int)
        assert isinstance(it0["missed_rate"], float)
