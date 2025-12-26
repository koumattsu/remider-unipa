# backend/tests/test_in_app_summary.py

def test_in_app_summary_contract_and_sanity(client):
    req_from = "2025-01-01T00:00:00Z"
    req_to = "2025-01-07T00:00:00Z"

    res = client.get(
        "/api/v1/notifications/in-app/summary",
        params={"from": req_from, "to": req_to},
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
    # ✅ リクエスト値がそのまま返る（契約固定）
    assert data["range"]["from"] == req_from
    assert data["range"]["to"] == req_to

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
    expected_keys = {"sent", "failed", "deactivated", "skipped", "unknown"}
    for k in expected_keys:
        assert k in ev
        assert isinstance(ev[k], int)
        assert ev[k] >= 0
    # ✅ 余計なキー追加も検知（仕様膨張を止める）
    assert set(ev.keys()) == expected_keys
