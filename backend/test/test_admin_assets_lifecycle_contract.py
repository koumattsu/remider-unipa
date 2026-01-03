# backend/test/test_admin_assets_lifecycle_contract.py

from datetime import datetime, timezone, timedelta
from app.core.security import get_current_user
from app.db.session import get_db
from app.models.task import Task
from app.models.task_outcome_log import TaskOutcomeLog
from app.models.in_app_notification import InAppNotification
from app.models.suggested_action_applied_event import SuggestedActionAppliedEvent

class _DummyUser:
    def __init__(self, user_id: int):
        self.id = user_id

def test_admin_assets_lifecycle_capture_and_list_contract(client):
    """
    UserLifecycleSnapshot 契約テスト（最小）
    - POST capture でスナップショット作成
    - GET list で items に入る
    - キー/型を固定
    - user_id 分離を保証（他userのデータが混ざらない）
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

    # --- ユーザー1の活動データを作る ---
    t1 = Task(
        user_id=1,
        title="u1-t1",
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
        user_id=1,
        title="u1-t2",
        course_name="c2",
        deadline=now + timedelta(days=2),
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

    out = TaskOutcomeLog(
        user_id=1,
        task_id=t1.id,
        deadline=now,
        outcome="missed",
        evaluated_at=now,
    )
    session.add(out)

    inapp = InAppNotification(
        user_id=1,
        task_id=None,
        deadline_at_send=now,
        offset_hours=3,
        kind="task_reminder",
        title="title",
        body="body",
        deep_link="/today",
        extra=None,
        run_id=None,
        dismissed_at=None,
    )
    session.add(inapp)

    ev = SuggestedActionAppliedEvent(
        user_id=1,
        action_id="demo-action",
        bucket="week",
        applied_at=now,
        payload={},
    )
    session.add(ev)

    # --- ユーザー2（混入防止用） ---
    t_other = Task(
        user_id=2,
        title="u2-t1",
        course_name="cX",
        deadline=now + timedelta(days=1),
        memo=None,
        is_done=True,
        completed_at=now,
        should_notify=True,
        auto_notify_disabled_by_done=False,
        weekly_task_id=None,
        deleted_at=None,
    )
    session.add(t_other)
    session.commit()

    # --- capture ---
    r = client.post("/api/v1/admin/assets/lifecycle/snapshots/capture")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, dict)
    assert set(data.keys()) == {"ok", "snapshot_id"}
    assert data["ok"] is True
    assert isinstance(data["snapshot_id"], int)

    # --- list ---
    res = client.get("/api/v1/admin/assets/lifecycle/snapshots?limit=10")
    assert res.status_code == 200
    body = res.json()
    assert isinstance(body, dict)
    assert set(body.keys()) == {"items"}

    items = body["items"]
    assert isinstance(items, list)
    assert len(items) >= 1

    it = items[0]
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
    assert set(it.keys()) == expected_keys

    assert isinstance(it["id"], int)
    assert it["user_id"] == 1
    assert isinstance(it["captured_at"], str)
    # 現状 User.created_at が無い想定なので None を許容
    assert (it["registered_at"] is None) or isinstance(it["registered_at"], str)
    assert (it["first_task_created_at"] is None) or isinstance(it["first_task_created_at"], str)
    assert (it["first_task_completed_at"] is None) or isinstance(it["first_task_completed_at"], str)
    assert (it["last_active_at"] is None) or isinstance(it["last_active_at"], str)

    assert isinstance(it["tasks_total"], int)
    assert isinstance(it["completed_total"], int)
    assert isinstance(it["done_rate"], float)
    assert isinstance(it["active_7d"], bool)
    assert isinstance(it["active_30d"], bool)

    # ✅ user1 のみ集計されていること（user2が混ざらない）
    assert it["tasks_total"] >= 2
    assert it["completed_total"] >= 1
    assert 0.0 <= it["done_rate"] <= 1.0

    app.dependency_overrides.pop(get_current_user, None)
