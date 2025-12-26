# backend/tests/test_in_app_summary.py

def test_in_app_summary_contract_and_sanity(client):
    res = client.get(
        "/api/v1/notifications/in-app/summary",
        params={"from": "2025-01-01T00:00:00Z", "to": "2025-01-07T00:00:00Z"},
    )
    assert res.status_code == 200

    data = res.json()

    # 契約（schema）キー
    assert "range" in data
    assert "total" in data
    assert "dismissed" in data
    assert "dismiss_rate" in data
    assert "webpush_events" in data

    # range
    assert "from" in data["range"]
    assert "to" in data["range"]

    # 数値の健全性
    total = data["total"]
    dismissed = data["dismissed"]
    rate = data["dismiss_rate"]
    assert isinstance(total, int)
    assert isinstance(dismissed, int)
    assert isinstance(rate, int)

    assert total >= 0
    assert 0 <= dismissed <= total
    assert 0 <= rate <= 100

    # webpush_events は5キー固定（破壊的変更を検知）
    ev = data["webpush_events"]
    for k in ["sent", "failed", "deactivated", "skipped", "unknown"]:
        assert k in ev
        assert isinstance(ev[k], int)
        assert ev[k] >= 0
