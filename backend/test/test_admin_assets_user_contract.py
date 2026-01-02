from datetime import datetime, timezone

from app.core.security import get_current_user
from app.db.session import get_db

from app.models.user import User
from app.models.task import Task
from app.models.notification_run import NotificationRun
from app.models.in_app_notification import InAppNotification
from app.models.task_outcome_log import TaskOutcomeLog
from app.models.suggested_action_applied_event import SuggestedActionAppliedEvent


class _DummyUser:
    def __init__(self, user_id: int):
        self.id = user_id


def test_admin_assets_user_contract(client):
    """
    Admin Asset User Snapshot 契約テスト（最小）
    - 返却キー固定
    - カウントが int
    - user_id ごとに資産が分離される（マルチテナント資産スナップショット）
    """

    app = client.app
    now = datetime.now(timezone.utc)

    async def _user1():
        return _DummyUser(1)

    app.dependency_overrides[get_current_user] = _user1

    # FakeSession を取り出す（既存テストと同じ）
    override_get_db = app.dependency_overrides[get_db]
    gen = override_get_db()
    session = next(gen)

    # --- 資産を作る ---
    u1 = User(id=1, line_user_id=None, display_name="u1", university=None, plan="free")
    u2 = User(id=2, line_user_id=None, display_name="u2", university=None, plan="free")
    session.add(u1)
    session.add(u2)

    # user1 tasks (1 done)
    t1 = Task(
        user_id=1,
        title="t1",
        course_name="c1",
        deadline=now,
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
        title="t2",
        course_name="c1",
        deadline=now,
        memo=None,
        is_done=True,
        completed_at=now,
        should_notify=False,
        auto_notify_disabled_by_done=True,
        weekly_task_id=None,
        deleted_at=None,
    )
    # user2 task (0 done)
    t3 = Task(
        user_id=2,
        title="t3",
        course_name="c2",
        deadline=now,
        memo=None,
        is_done=False,
        completed_at=None,
        should_notify=True,
        auto_notify_disabled_by_done=False,
        weekly_task_id=None,
        deleted_at=None,
    )
    session.add(t1)
    session.add(t2)
    session.add(t3)

    # system-level run（user帰属不可なので total として数える契約）
    run = NotificationRun(
        status="success",
        started_at=now,
        finished_at=now,
        users_processed=2,
        due_candidates_total=0,
        morning_candidates_total=0,
        inapp_created=0,
        webpush_sent=0,
        webpush_failed=0,
        webpush_deactivated=0,
        line_sent=0,
        line_failed=0,
        stats=None,
        error_summary=None,
    )
    session.add(run)

    # inapp: user1 only
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

    # FakeSession が id を付ける前提なので一旦 commit
    session.commit()

    # outcome: user1 only
    out = TaskOutcomeLog(
        user_id=1,
        task_id=t1.id,
        deadline=now,
        outcome="missed",
        evaluated_at=now,
    )
    session.add(out)

    # action event: user2 only（分離確認用）
    ev = SuggestedActionAppliedEvent(
        user_id=2,
        action_id="demo-action",
        bucket="week",
        applied_at=now,
        payload={},
    )
    session.add(ev)

    session.commit()

    # --- 叩く ---
    r1 = client.get("/api/v1/admin/assets/users/1")
    assert r1.status_code == 200
    d1 = r1.json()
    assert isinstance(d1, dict)

    expected_keys = {
        "user_id",
        "tasks",
        "completed_tasks",
        "notification_runs",
        "in_app_notifications",
        "outcome_logs",
        "action_applied_events",
    }
    assert set(d1.keys()) == expected_keys
    for k in expected_keys:
        assert isinstance(d1[k], int)

    # user1 の資産
    assert d1["user_id"] == 1
    assert d1["tasks"] >= 2
    assert d1["completed_tasks"] >= 1
    assert d1["in_app_notifications"] >= 1
    assert d1["outcome_logs"] >= 1
    # user1 には action event を入れてないので 0 が期待
    assert d1["action_applied_events"] == 0
    # run は user帰属できないので total として 1 以上
    assert d1["notification_runs"] >= 1

    # user2 の資産
    r2 = client.get("/api/v1/admin/assets/users/2")
    assert r2.status_code == 200
    d2 = r2.json()
    assert set(d2.keys()) == expected_keys
    for k in expected_keys:
        assert isinstance(d2[k], int)

    assert d2["user_id"] == 2
    assert d2["tasks"] >= 1
    assert d2["completed_tasks"] == 0
    assert d2["in_app_notifications"] == 0
    assert d2["outcome_logs"] == 0
    assert d2["action_applied_events"] >= 1
    assert d2["notification_runs"] >= 1

    # 後片付け
    app.dependency_overrides.pop(get_current_user, None)
