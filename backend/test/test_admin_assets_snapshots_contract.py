# backend/test/test_admin_assets_snapshots_contract.py

from datetime import datetime, timezone
from app.core.security import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.models.task import Task

class _DummyUser:
    def __init__(self, user_id: int):
        self.id = user_id


def test_admin_assets_snapshots_contract(client):
    """
    Asset Snapshots 契約テスト（最小）
    - POST run で snapshot を保存できる
    - GET list で items が返る
    - キー固定 / 型固定
    """

    app = client.app
    now = datetime.now(timezone.utc)

    async def _user1():
        return _DummyUser(1)

    app.dependency_overrides[get_current_user] = _user1

    # FakeSession を取り出す
    override_get_db = app.dependency_overrides[get_db]
    gen = override_get_db()
    session = next(gen)

    # 資産を最低限入れる（users>=2 を満たすため taskを2ユーザで作る）
    u1 = User(id=1, line_user_id=None, display_name="u1", university=None, plan="free")
    u2 = User(id=2, line_user_id=None, display_name="u2", university=None, plan="free")
    session.add(u1)
    session.add(u2)

    t1 = Task(
        user_id=1, title="t1", course_name="c1", deadline=now,
        memo=None, is_done=False, completed_at=None,
        should_notify=True, auto_notify_disabled_by_done=False,
        weekly_task_id=None, deleted_at=None,
    )
    t2 = Task(
        user_id=2, title="t2", course_name="c2", deadline=now,
        memo=None, is_done=True, completed_at=now,
        should_notify=False, auto_notify_disabled_by_done=True,
        weekly_task_id=None, deleted_at=None,
    )
    session.add(t1)
    session.add(t2)
    session.commit()

    # 1) snapshot run
    r = client.post("/api/v1/admin/assets/snapshots/run")
    assert r.status_code == 200
    d = r.json()
    assert isinstance(d, dict)
    assert set(d.keys()) == {"ok", "snapshot_id"}
    assert d["ok"] is True
    assert isinstance(d["snapshot_id"], int)

    # 2) list
    r2 = client.get("/api/v1/admin/assets/snapshots", params={"limit": 10})
    assert r2.status_code == 200
    d2 = r2.json()
    assert isinstance(d2, dict)
    assert set(d2.keys()) == {"items"}
    assert isinstance(d2["items"], list)
    assert len(d2["items"]) >= 1

    item = d2["items"][0]
    expected_keys = {
        "id", "kind", "user_id",
        "users", "tasks", "completed_tasks",
        "notification_runs", "in_app_notifications",
        "outcome_logs", "action_applied_events",
        "created_at",
    }
    assert set(item.keys()) == expected_keys

    # 型固定
    assert isinstance(item["id"], int)
    assert isinstance(item["kind"], str)
    assert (item["user_id"] is None) or isinstance(item["user_id"], int)
    for k in [
        "users", "tasks", "completed_tasks",
        "notification_runs", "in_app_notifications",
        "outcome_logs", "action_applied_events",
    ]:
        assert isinstance(item[k], int)

    # 最低限反映
    assert item["users"] >= 2
    assert item["tasks"] >= 2
    assert item["completed_tasks"] >= 1

    app.dependency_overrides.pop(get_current_user, None)
