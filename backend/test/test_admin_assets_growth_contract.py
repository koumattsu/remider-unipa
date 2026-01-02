from datetime import datetime, timezone, timedelta
from app.core.security import get_current_user
from app.db.session import get_db
from app.models.asset_snapshot import AssetSnapshot


class _DummyUser:
    def __init__(self, user_id: int):
        self.id = user_id


def test_admin_assets_growth_contract(client):
    """
    Asset Growth 契約テスト
    - AssetSnapshot だけをSSOTに差分を計算
    - キー固定 / 型固定
    """

    app = client.app
    now = datetime.now(timezone.utc)

    async def _user():
        return _DummyUser(1)

    app.dependency_overrides[get_current_user] = _user

    # FakeSession を取得
    override_get_db = app.dependency_overrides[get_db]
    gen = override_get_db()
    session = next(gen)

    # --- Snapshot を2つ作る ---
    s1 = AssetSnapshot(
        kind="global",
        user_id=None,
        users=1,
        tasks=2,
        completed_tasks=0,
        notification_runs=1,
        in_app_notifications=1,
        outcome_logs=1,
        action_applied_events=0,
        created_at=now - timedelta(days=8),
    )
    session.add(s1)

    s2 = AssetSnapshot(
        kind="global",
        user_id=None,
        users=1,
        tasks=5,
        completed_tasks=1,
        notification_runs=3,
        in_app_notifications=6,
        outcome_logs=3,
        action_applied_events=1,
        created_at=now,
    )
    session.add(s2)
    session.commit()

    # --- API ---
    r = client.get("/api/v1/admin/assets/snapshots/growth", params={"days": 7})
    assert r.status_code == 200

    data = r.json()
    assert isinstance(data, dict)

    assert set(data.keys()) == {
        "days",
        "from_snapshot_id",
        "to_snapshot_id",
        "delta",
    }

    assert data["days"] == 7
    assert isinstance(data["from_snapshot_id"], int)
    assert isinstance(data["to_snapshot_id"], int)

    delta = data["delta"]
    assert set(delta.keys()) == {
        "users",
        "tasks",
        "completed_tasks",
        "notification_runs",
        "in_app_notifications",
        "outcome_logs",
        "action_applied_events",
    }

    # 差分が正しい
    assert delta["tasks"] == 3
    assert delta["completed_tasks"] == 1
    assert delta["notification_runs"] == 2
    assert delta["in_app_notifications"] == 5
    assert delta["outcome_logs"] == 2
    assert delta["action_applied_events"] == 1
