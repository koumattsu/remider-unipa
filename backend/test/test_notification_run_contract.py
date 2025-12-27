# backend/test/test_notification_run_contract.py

def test_notification_run_latest_contract(client):
    """
    契約テスト: /admin/notification-runs/latest の最低限のキーが壊れていないか
    - found/run 形式を契約として固定する（破壊的変更検知）
    - 初期状態（runが無い）も契約として固定する
    """
    res = client.get("/api/v1/admin/notification-runs/latest")
    assert res.status_code in (200, 404)

    # 初期状態は 404（実装契約）
    if res.status_code == 404:
        body = res.json()
        assert body.get("detail") == "not found"
        return

    data = res.json()
    assert isinstance(data, dict)
    assert "found" in data
    assert isinstance(data["found"], bool)

    if not data["found"]:
        return

    run = data["run"]
    assert isinstance(run, dict)

    # 監査として最低限必要なキー（破壊的変更検知）
    for k in [
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
    ]:
        assert k in run

    assert isinstance(run["id"], int)
    assert isinstance(run["status"], str)
    assert run["error_summary"] is None or isinstance(run["error_summary"], str)

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
        assert isinstance(run[k], int)
        assert run[k] >= 0

    # started_at/finished_at は ISO 文字列 or None（実装契約）
    assert run["started_at"] is None or isinstance(run["started_at"], str)
    assert run["finished_at"] is None or isinstance(run["finished_at"], str)

def test_notification_run_snapshot_contract(client):
    """
    契約テスト: found/run 形式において、run.stats の型が壊れていないか
    - stats を載せる/載せないは破壊的変更なので、現状（載せている）を契約として固定
    """
    res = client.get("/api/v1/admin/notification-runs/latest")
    assert res.status_code in (200, 404)
    if res.status_code == 404:
        return

    data = res.json()
    if not data.get("found"):
        return

    run = data["run"]

    # ✅ 現行契約: stats キーが存在する（None も許容）
    assert "stats" in run
    assert run["stats"] is None or isinstance(run["stats"], dict)

def test_notification_run_summary_contract(client):
    """
    契約テスト: /admin/notification-runs/{run_id}/summary の shape を固定する
    - M&A耐性: 監査用の「要約」が破壊的変更されないこと
    """
    run_id = 1  # FakeSession 側の NotificationRun を 1 としている前提

    res = client.get(f"/api/v1/admin/notification-runs/{run_id}/summary")
    assert res.status_code in (200, 404)

    if res.status_code == 404:
        # run not found が契約（runが存在しないケース）
        body = res.json()
        assert body.get("detail") == "run not found"
        return

    data = res.json()
    assert isinstance(data, dict)

    # top-level keys
    assert set(data.keys()) == {"run", "inapp", "run_counters"}

    # run
    run = data["run"]
    for k in ["id", "status", "started_at", "finished_at", "stats"]:
        assert k in run
    assert isinstance(run["id"], int)
    assert isinstance(run["status"], str)
    assert run["started_at"] is None or isinstance(run["started_at"], str)
    assert run["finished_at"] is None or isinstance(run["finished_at"], str)
    assert run["stats"] is None or isinstance(run["stats"], dict)

    # inapp
    inapp = data["inapp"]
    assert set(inapp.keys()) == {"total", "dismissed_count", "dismiss_rate", "webpush"}
    assert isinstance(inapp["total"], int) and inapp["total"] >= 0
    assert isinstance(inapp["dismissed_count"], int) and inapp["dismissed_count"] >= 0
    assert 0 <= inapp["dismissed_count"] <= inapp["total"]
    assert isinstance(inapp["dismiss_rate"], int)
    assert 0 <= inapp["dismiss_rate"] <= 100

    wp = inapp["webpush"]
    assert set(wp.keys()) == {"delivered", "failed", "deactivated", "unknown", "events"}
    for k in ["delivered", "failed", "deactivated", "unknown"]:
        assert isinstance(wp[k], int)
        assert wp[k] >= 0

    events = wp["events"]
    expected_event_keys = {"sent", "failed", "deactivated", "skipped", "unknown"}
    assert set(events.keys()) == expected_event_keys
    for k in expected_event_keys:
        assert isinstance(events[k], int)
        assert events[k] >= 0

    # run_counters
    counters = data["run_counters"]
    assert set(counters.keys()) == {
        "inapp_created",
        "webpush_sent",
        "webpush_failed",
        "webpush_deactivated",
    }
    for k in counters.keys():
        assert isinstance(counters[k], int)
        assert counters[k] >= 0
