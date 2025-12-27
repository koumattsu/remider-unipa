# backend/tests/test_webpush_debug_contract.py

def test_webpush_debug_send_contract(client):
    """
    契約テスト: /notifications/webpush/debug-send
    - 返却キーを固定（sent/failed/deactivated）
    - すべて non-negative int
    - 余計なキー追加を検知
    """
    res = client.post("/api/v1/notifications/webpush/debug-send")
    assert res.status_code == 200

    data = res.json()
    assert isinstance(data, dict)

    expected_keys = {"sent", "failed", "deactivated"}
    assert set(data.keys()) == expected_keys

    for k in expected_keys:
        assert isinstance(data[k], int)
        assert data[k] >= 0
