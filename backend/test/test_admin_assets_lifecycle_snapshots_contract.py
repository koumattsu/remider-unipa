# backend/test/test_admin_assets_lifecycle_snapshots_contract.py

from datetime import datetime, timezone, timedelta

from app.core.security import get_current_user
from app.db.session import get_db

from app.models.user import User
from app.models.task import Task


class _DummyUser:
    def __init__(self, user_id: int):
        self.id = user_id


def test_admin_assets_lifecycle_snapshots_contract(client):
    """
    Admin Lifecycle Snapshots 契約（最小）
    - capture が作成して id を返す
    - list が items を返し、キー/型が固定
    """

    app = client.app
    now = datetime.now(timezone.utc)

    async def _user1():
        return _DummyUser(1)

    app.dependency_overrides[get_current_user] = _user1

    override_get_db = app.dependency_overrides[get_db]
    gen = override_get_db()
    session = next(gen)

    # --- seed: user/tasks（Task.created_at/updated_at は FakeSession.add が補う想定） ---
    u1 = User(id=1, line_user_id=None, display_name="u1", university=None, plan="free")
    u2 = User(id=2, line_user_id=None, display_name="u2", university=None, plan="free")
    session.add(u1)
    session.add(u2)

    t1 = Task(
        user_id=1,
        title="t1",
        course_name="c1",
        deadline=now + timedelta(days=1),
        memo=None,
        is_done=False,
        completed_at=None,
        should_notify=True,
        auto_notify_disabled_by_done=False,
        weekly_task_id=None,
        deleted_at=None,
    )
    t2 = Task(
        user_id=2,
        title="t2",
        course_name="c2",
        deadline=now + timedelta(days=1),
        memo=None,
        is_done=True,
        completed_at=now,
        should_notify=False,
        auto_notify_disabled_by_done=True,
        weekly_task_id=None,
        deleted_at=None,
    )
    session.add(t1)
    session.add(t2)
    session.commit()

    # --- capture ---
    r = client.post("/api/v1/admin/assets/lifecycle/snapshots/capture")
    assert r.status_code == 200
    data = r.json()
    assert set(data.keys()) == {"ok", "created_ids"}
    assert data["ok"] is True
    assert isinstance(data["created_ids"], list)
    assert len(data["created_ids"]) >= 1

    # --- list ---
    r2 = client.get("/api/v1/admin/assets/lifecycle/snapshots", params={"limit": 50})
    assert r2.status_code == 200
    d2 = r2.json()
    assert set(d2.keys()) == {"items"}
    assert isinstance(d2["items"], list)

    if len(d2["items"]) >= 1:
        one = d2["items"][0]
        expected_keys = {
            "id",
            "user_id",
            "captured_at",
            "registered_at",
            "first_task_created_at",
            "first_task_completed_at",
            "last_active_at",
            "tasks_total",
            "completed_total",
            "done_rate",
            "active_7d",
            "active_30d",
        }
        assert set(one.keys()) == expected_keys
        assert isinstance(one["id"], int)
        assert isinstance(one["user_id"], int)
        assert isinstance(one["captured_at"], str)

        assert isinstance(one["tasks_total"], int)
        assert isinstance(one["completed_total"], int)
        assert isinstance(one["done_rate"], float)

        assert isinstance(one["active_7d"], bool)
        assert isinstance(one["active_30d"], bool)

    app.dependency_overrides.pop(get_current_user, None)
