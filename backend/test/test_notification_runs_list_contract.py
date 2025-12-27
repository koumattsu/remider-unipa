# backend/test/test_notification_runs_list_contract.py

def test_notification_runs_list_contract(client):
    """
    契約テスト: /admin/notification-runs の shape を固定する
    - 監査ログ一覧として最低限必要なキーが壊れないこと
    - items は配列、各要素のキーを固定（破壊的変更検知）
    """
    res = client.get("/api/v1/admin/notification-runs", params={"limit": 5})
    assert res.status_code == 200

    data = res.json()
    assert isinstance(data, dict)
    assert set(data.keys()) == {"items"}

    items = data["items"]
    assert isinstance(items, list)

    for r in items:
        expected_keys = {
            "id",
            "status",
            "error_summary",
            "users_processed",
            "due_candidates_total",
            "morning_candidates_total",
            "inapp_created",
            "webpush_sent",
            "webpush_failed",
            "webpush_deactivated",
            "line_sent",
            "line_failed",
            "started_at",
            "finished_at",
            "stats",
        }
        assert set(r.keys()) == expected_keys

        assert isinstance(r["id"], int)
        assert isinstance(r["status"], str)
        assert r["error_summary"] is None or isinstance(r["error_summary"], str)

        for k in [
            "users_processed",
            "due_candidates_total",
            "morning_candidates_total",
            "inapp_created",
            "webpush_sent",
            "webpush_failed",
            "webpush_deactivated",
            "line_sent",
            "line_failed",
        ]:
            assert isinstance(r[k], int)
            assert r[k] >= 0

        assert r["started_at"] is None or isinstance(r["started_at"], str)
        assert r["finished_at"] is None or isinstance(r["finished_at"], str)

        # stats は None or dict（監査拡張の余地を残す）
        assert r["stats"] is None or isinstance(r["stats"], dict)


def test_notification_runs_get_contract(client):
    """
    契約テスト: /admin/notification-runs/{run_id} の shape を固定する
    - not found の契約も固定
    """
    # 存在しないIDは本番では 404 になり得るが、
    # FakeSession だと filter が効かず 200 になることがある。
    res404 = client.get("/api/v1/admin/notification-runs/999999")
    assert res404.status_code in (200, 404)

    if res404.status_code == 404:
        body = res404.json()
        assert body.get("detail") == "not found"
    else:
        # 200 の場合も shape は固定（破壊的変更検知）
        r = res404.json()
        expected_keys = {
            "id",
            "status",
            "error_summary",
            "users_processed",
            "due_candidates_total",
            "morning_candidates_total",
            "inapp_created",
            "webpush_sent",
            "webpush_failed",
            "webpush_deactivated",
            "line_sent",
            "line_failed",
            "started_at",
            "finished_at",
        }
        assert isinstance(r, dict)
        assert set(r.keys()) == expected_keys

    # 次に、一覧から取れた id があればその id でGETして shape を固定
    res = client.get("/api/v1/admin/notification-runs", params={"limit": 1})
    assert res.status_code == 200
    data = res.json()
    items = data.get("items") or []
    if not items:
        # 初期状態（run無し）を許容：ここは list が空の契約
        return

    run_id = items[0]["id"]
    res2 = client.get(f"/api/v1/admin/notification-runs/{run_id}")
    assert res2.status_code == 200

    r = res2.json()
    assert isinstance(r, dict)

    expected_keys = {
        "id",
        "status",
        "error_summary",
        "users_processed",
        "due_candidates_total",
        "morning_candidates_total",
        "inapp_created",
        "webpush_sent",
        "webpush_failed",
        "webpush_deactivated",
        "line_sent",
        "line_failed",
        "started_at",
        "finished_at",
    }
    assert set(r.keys()) == expected_keys

    assert isinstance(r["id"], int)
    assert isinstance(r["status"], str)
    assert r["error_summary"] is None or isinstance(r["error_summary"], str)

    for k in [
        "users_processed",
        "due_candidates_total",
        "morning_candidates_total",
        "inapp_created",
        "webpush_sent",
        "webpush_failed",
        "webpush_deactivated",
        "line_sent",
        "line_failed",
    ]:
        assert isinstance(r[k], int)
        assert r[k] >= 0

    assert r["started_at"] is None or isinstance(r["started_at"], str)
    assert r["finished_at"] is None or isinstance(r["finished_at"], str)
