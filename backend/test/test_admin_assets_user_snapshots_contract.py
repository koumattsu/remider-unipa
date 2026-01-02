from datetime import datetime, timezone

from app.core.security import get_current_user
from app.db.session import get_db

from app.models.user import User
from app.models.task import Task
from app.models.in_app_notification import InAppNotification
from app.models.task_outcome_log import TaskOutcomeLog
from app.models.suggested_action_applied_event import SuggestedActionAppliedEvent


class _DummyUser:
    def __init__(self, user_id: int):
        self.id = user_id


def test_admin_assets_user_snapshots_contract(client):
    """
    User Asset Snapshots 契約テスト（最小）
    - POST run で user別 snapshot を保存できる
    - GET list で user別 items が返る
    - キー固定 / 型固定
    - user_id でフィルタされる
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

    # --- 資産を作る ---
    u1 = User(id=1, line_user_id=None, display_name="u1", university=None, plan="free")
    u2 = User(id=2, line_user_id=None, display_name="u2", university=None, plan="free")
    session.add(u1)
    session.add(u2)

    # user1: task 2 (1 done)
    t1 = Task(
        user_id=1, title="t1", course_name="c1", deadline=now,
        memo=None, is_done=False, completed_at=None,
        should_notify=True, auto_notify_disabled_by_done=False,
        weekly_task_id=None, deleted_at=None,
    )
    t2 = Task(
        user_id=1, title="t2", course_name="c1", deadline=now,
        memo=None, is_done=True, completed_at=now,
        should_notify=False, auto_notify_disabled_by_done=True,
        weekly_task_id=None, deleted_at=None,
    )
    # user2: task 1
    t3 = Task(
        user_id=2, title="t3", course_name="c2", deadline=now,
        memo=None, is_done=False, completed_at=None,
        should_notify=True, auto_notify_disabled_by_done=False,
        weekly_task_id=None, deleted_at=None,
    )
    session.add(t1)
    session.add(t2)
    session.add(t3)

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

    session.commit()

    out = TaskOutcomeLog(
        user_id=1,
        task_id=t1.id,
        deadline=now,
        outcome="missed",
        evaluated_at=now,
    )
    session.add(out)

    ev = SuggestedActionAppliedEvent(
        user_id=2,
        action_id="demo-action",
        bucket="week",
        applied_at=now,
        payload={},
    )
    session.add(ev)

    session.commit()

    # --- POST run（user1） ---
    r = client.post("/api/v1/admin/assets/users/1/snapshots/run")
    assert r.status_code == 200
    d = r.json()
    assert isinstance(d, dict)
    assert set(d.keys()) == {"ok", "snapshot_id"}
    assert d["ok"] is True
    assert isinstance(d["snapshot_id"], int)

    # --- GET list（user1） ---
    r2 = client.get("/api/v1/admin/assets/users/1/snapshots", params={"limit": 10})
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

    assert item["kind"] == "user"
    assert item["user_id"] == 1

    # 型固定
    assert isinstance(item["id"], int)
    for k in [
        "users", "tasks", "completed_tasks",
        "notification_runs", "in_app_notifications",
        "outcome_logs", "action_applied_events",
    ]:
        assert isinstance(item[k], int)

    # user1資産の最低限反映（user1には action event 入れてない）
    assert item["tasks"] >= 2
    assert item["completed_tasks"] >= 1
    assert item["in_app_notifications"] >= 1
    assert item["outcome_logs"] >= 1
    assert item["action_applied_events"] == 0

    # --- GET list（user2）は 0 件（user2 run してない） ---
    r3 = client.get("/api/v1/admin/assets/users/2/snapshots", params={"limit": 10})
    assert r3.status_code == 200
    d3 = r3.json()
    assert isinstance(d3, dict)
    assert set(d3.keys()) == {"items"}
    assert isinstance(d3["items"], list)
    assert len(d3["items"]) == 0

    app.dependency_overrides.pop(get_current_user, None)