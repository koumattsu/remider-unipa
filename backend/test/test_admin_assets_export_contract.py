from datetime import datetime, timezone

from app.core.security import get_current_user
from app.db.session import get_db

from app.models.user import User
from app.models.task import Task
from app.models.asset_snapshot import AssetSnapshot
from app.models.notification_run import NotificationRun
from app.models.in_app_notification import InAppNotification
from app.models.task_outcome_log import TaskOutcomeLog
from app.models.suggested_action_applied_event import SuggestedActionAppliedEvent


class _DummyUser:
    def __init__(self, user_id: int):
        self.id = user_id


def test_admin_assets_export_contract(client):
    """
    Admin Export 契約テスト（最小）
    - キー固定
    - 生テキストを出さない（in_app title/body, action payload 生）
    - global/user 両方動く
    """
    app = client.app
    now = datetime.now(timezone.utc)

    async def _user1():
        return _DummyUser(1)

    app.dependency_overrides[get_current_user] = _user1

    override_get_db = app.dependency_overrides[get_db]
    gen = override_get_db()
    session = next(gen)

    # --- seed ---
    u1 = User(id=1, line_user_id=None, display_name="u1", university=None, plan="free")
    u2 = User(id=2, line_user_id=None, display_name="u2", university=None, plan="free")
    session.add(u1); session.add(u2)

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
    session.add(t1); session.add(t2)

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
        title="SECRET_TITLE",
        body="SECRET_BODY",
        deep_link="/today",
        extra={"maybe_secret": "x"},
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
        user_id=1,
        action_id="demo-action",
        bucket="week",
        applied_at=now,
        payload={"raw": "SECRET_PAYLOAD"},
    )
    session.add(ev)

    # snapshots（SSOT）
    s_global = AssetSnapshot(
        kind="global",
        user_id=None,
        users=2,
        tasks=2,
        completed_tasks=1,
        notification_runs=1,
        in_app_notifications=1,
        outcome_logs=1,
        action_applied_events=1,
        stats={"v": 1},
        created_at=now,
    )
    s_user = AssetSnapshot(
        kind="user",
        user_id=1,
        users=1,
        tasks=1,
        completed_tasks=0,
        notification_runs=1,
        in_app_notifications=1,
        outcome_logs=1,
        action_applied_events=1,
        stats={"v": 1},
        created_at=now,
    )
    session.add(s_global); session.add(s_user)

    session.commit()

    # --- global export ---
    r = client.get("/api/v1/admin/assets/export", params={"kind": "global", "limit": 100})
    assert r.status_code == 200
    data = r.json()
    assert set(data.keys()) == {"export_version", "generated_at", "range", "payload"}
    assert data["export_version"] == 1
    assert isinstance(data["generated_at"], str)

    rng = data["range"]
    assert set(rng.keys()) == {"kind", "user_id", "from", "to", "limit"}
    assert rng["kind"] == "global"
    assert rng["user_id"] is None

    payload = data["payload"]
    assert set(payload.keys()) == {
        "asset_snapshots",
        "lifecycle_snapshots",
        "outcome_logs",
        "action_applied_events",
        "notification_runs",
        "in_app_notifications",
    }

    # in_app は title/body を出さない
    inapps = payload["in_app_notifications"]
    assert isinstance(inapps, list)
    if len(inapps) >= 1:
        one = inapps[0]
        assert "title" not in one
        assert "body" not in one

    # action payload 生は出さず payload_hash を出す
    events = payload["action_applied_events"]
    assert isinstance(events, list)
    if len(events) >= 1:
        one = events[0]
        assert "payload" not in one
        assert "payload_hash" in one
        assert isinstance(one["payload_hash"], str)

    # --- user export ---
    r2 = client.get("/api/v1/admin/assets/export", params={"kind": "user", "user_id": 1, "limit": 100})
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2["range"]["kind"] == "user"
    assert d2["range"]["user_id"] == 1

    app.dependency_overrides.pop(get_current_user, None)
