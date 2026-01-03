# backend/test/test_admin_assets_summary_contract.py

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

def test_admin_assets_summary_contract(client):
    """
    Admin Asset Summary 契約テスト（最小）
    - 返却キーを固定
    - カウントが int
    - 追加した資産が反映される
    """

    app = client.app
    now = datetime.now(timezone.utc)

    # 認証（v0 require_admin は current_user を通すだけなので get_current_user を固定）
    async def _user1():
        return _DummyUser(1)

    app.dependency_overrides[get_current_user] = _user1

    # FakeSession を取り出す（既存テストで使ってるパターンに合わせる）
    override_get_db = app.dependency_overrides[get_db]
    gen = override_get_db()
    session = next(gen)

    # --- 資産を作る（DB直投入：read-only集計の正確性確認） ---
    u1 = User(id=1, line_user_id=None, display_name="u1", university=None, plan="free")
    u2 = User(id=2, line_user_id=None, display_name="u2", university=None, plan="free")
    session.add(u1)
    session.add(u2)

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
        user_id=2,
        title="t2",
        course_name="c2",
        deadline=now,
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

    # TaskOutcomeLog は task_id が必要なので t1.id を使う（FakeSessionがIDを振る前提）
    # もし FakeSession が即時に id を振らない場合は、commit/flush 相当が必要なので、
    # 既存 conftest 実装に合わせて session.commit() を先に呼ぶ。
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
        user_id=1,
        action_id="demo-action",
        bucket="week",
        applied_at=now,
        payload={},
    )
    session.add(ev)

    session.commit()

    # --- 叩く ---
    res = client.get("/api/v1/admin/assets/summary")
    assert res.status_code == 200

    data = res.json()
    assert isinstance(data, dict)

    expected_keys = {
        "users",
        "tasks",
        "completed_tasks",
        "notification_runs",
        "in_app_notifications",
        "outcome_logs",
        "action_applied_events",
    }
    assert set(data.keys()) == expected_keys

    for k in expected_keys:
        assert isinstance(data[k], int)

    # 最低限「反映された」ことを確認
    assert data["users"] >= 2
    assert data["tasks"] >= 2
    assert data["completed_tasks"] >= 1
    assert data["notification_runs"] >= 1
    assert data["in_app_notifications"] >= 1
    assert data["outcome_logs"] >= 1
    assert data["action_applied_events"] >= 1

    # 後片付け
    app.dependency_overrides.pop(get_current_user, None)
