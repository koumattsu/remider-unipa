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

    # ✅ 高価値契約: stats は SSOT ではないため payload は自由に進化できる
    # 固定するのはヘッダのみ（破壊的変更の検知 + 進化の阻害を避ける）
    if isinstance(run["stats"], dict):
        for k in ["v", "kind", "generated_at", "payload"]:
            assert k in run["stats"]

        assert isinstance(run["stats"]["v"], int)
        assert isinstance(run["stats"]["kind"], str)
        assert isinstance(run["stats"]["generated_at"], str)
        assert isinstance(run["stats"]["payload"], dict)

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

    # top-level keys（summary_v を導入して進化を許容）
    assert set(data.keys()) == {"summary_v", "run", "inapp", "run_counters"}
    assert data["summary_v"] == 1

    # run
    run = data["run"]
    for k in ["id", "status", "started_at", "finished_at", "stats"]:
        assert k in run
    assert isinstance(run["id"], int)
    assert isinstance(run["status"], str)
    assert run["started_at"] is None or isinstance(run["started_at"], str)
    assert run["finished_at"] is None or isinstance(run["finished_at"], str)
    assert run["stats"] is None or isinstance(run["stats"], dict)

    # ✅ 高価値契約: stats は補助データ。ヘッダのみ固定し、payloadは自由に進化可能
    if isinstance(run["stats"], dict):
        for k in ["v", "kind", "generated_at", "payload"]:
            assert k in run["stats"]

        assert isinstance(run["stats"]["v"], int)
        assert isinstance(run["stats"]["kind"], str)
        assert isinstance(run["stats"]["generated_at"], str)
        assert isinstance(run["stats"]["payload"], dict)

    # inapp
    inapp = data["inapp"]
    assert set(inapp.keys()) == {"total", "dismissed_count", "dismiss_rate", "webpush"}
    assert isinstance(inapp["total"], int) and inapp["total"] >= 0
    assert isinstance(inapp["dismissed_count"], int) and inapp["dismissed_count"] >= 0
    assert 0 <= inapp["dismissed_count"] <= inapp["total"]
    assert isinstance(inapp["dismiss_rate"], int)
    assert 0 <= inapp["dismiss_rate"] <= 100

    wp = inapp["webpush"]

    # ✅ 契約：必須キーは固定（後方互換）
    required = {"delivered", "failed", "deactivated", "unknown", "events"}

    # ✅ 進化：追加キーは許容（ただし whitelist で監査価値を守る）
    optional = {"sent_messages", "opened_messages", "open_rate"}

    assert required.issubset(set(wp.keys()))
    assert set(wp.keys()).issubset(required | optional)

    # required types
    assert isinstance(wp["delivered"], int) and wp["delivered"] >= 0
    assert isinstance(wp["failed"], int) and wp["failed"] >= 0
    assert isinstance(wp["deactivated"], int) and wp["deactivated"] >= 0
    assert isinstance(wp["unknown"], int) and wp["unknown"] >= 0
    assert isinstance(wp["events"], dict)

    # optional types（存在する場合のみチェック）
    if "sent_messages" in wp:
        assert isinstance(wp["sent_messages"], int) and wp["sent_messages"] >= 0
    if "opened_messages" in wp:
        assert isinstance(wp["opened_messages"], int) and wp["opened_messages"] >= 0
    if "open_rate" in wp:
        assert isinstance(wp["open_rate"], (int, float))

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

    # ✅ 追加契約: summary 内のカウンタ整合性（監査耐性）
    assert counters["webpush_sent"] == events["sent"]
    assert counters["webpush_failed"] == events["failed"]
    assert counters["webpush_deactivated"] == events["deactivated"]

    # ✅ 追加契約: inapp total と events の弱い整合（将来拡張を殺さない）
    events_sum = sum(events.values())
    assert events_sum <= inapp["total"]

    # ✅ 追加契約: dismiss_rate は概ね整合（丸め誤差 ±1 を許容）
    if inapp["total"] == 0:
        assert inapp["dismiss_rate"] == 0
    else:
        expected = round(inapp["dismissed_count"] / inapp["total"] * 100)
        assert abs(inapp["dismiss_rate"] - expected) <= 1

    # stats.payload.snapshot.webpush_events のキー集合は固定（SSOTと一致）
    if isinstance(run["stats"], dict):
        payload = run["stats"].get("payload") or {}
        snapshot = payload.get("snapshot") or {}
        events = snapshot.get("webpush_events")

        if isinstance(events, dict):
            assert set(events.keys()) == {
                "sent",
                "failed",
                "deactivated",
                "skipped",
                "unknown",
            }

        # ✅ 追加契約: webpush_source は監査の説明に必須（delivery / inapp_extra）
        src = snapshot.get("webpush_source")
        assert src in ("delivery", "inapp_extra")

        # ✅ FakeSession 契約: delivery 集計が使えないため fallback になる
        assert src == "inapp_extra"