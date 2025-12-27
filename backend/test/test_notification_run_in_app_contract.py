# backend/test/test_notification_run_in_app_contract.py

def test_notification_run_in_app_contract(client):
    """
    契約テスト:
    /admin/notification-runs/{run_id}/in-app
    - 監査耐性: 通知の「事実」が説明可能であること
    """
    run_id = 1

    res = client.get(f"/api/v1/admin/notification-runs/{run_id}/in-app")
    assert res.status_code in (200, 404)

    if res.status_code == 404:
        body = res.json()
        assert body.get("detail") == "run not found"
        return

    data = res.json()
    assert set(data.keys()) == {"run_id", "items"}
    assert data["run_id"] == run_id

    items = data["items"]
    assert isinstance(items, list)

    for n in items:
        # 🔒 shape 固定（破壊的変更検知）
        expected_keys = {
            "id",
            "run_id",
            "kind",
            "title",
            "body",
            "deep_link",
            "task_id",
            "deadline_at_send",
            "offset_hours",
            "created_at",
            "dismissed_at",
            "extra",
        }
        assert set(n.keys()) == expected_keys

        assert isinstance(n["id"], int)
        assert isinstance(n["run_id"], int)
        assert n["run_id"] == run_id

        assert isinstance(n["kind"], str)
        assert isinstance(n["title"], str)
        assert isinstance(n["body"], str)

        # ✅ deep_link 契約固定：通知タップで Today に飛べること
        assert isinstance(n["deep_link"], str)
        assert n["deep_link"].startswith("/dashboard")
        assert "tab=today" in n["deep_link"]

        assert n["deadline_at_send"] is None or isinstance(n["deadline_at_send"], str)
        assert n["created_at"] is None or isinstance(n["created_at"], str)
        assert n["dismissed_at"] is None or isinstance(n["dismissed_at"], str)

        # extra は拡張可だが dict 固定
        assert n["extra"] is None or isinstance(n["extra"], dict)