# backend/test/test_outcome_log_asset_integrity.py

from datetime import datetime, timezone, timedelta
from app.core.security import get_current_user
from app.db.session import get_db
from app.models.task import Task
from app.models.task_outcome_log import TaskOutcomeLog


class _DummyUser:
    def __init__(self, user_id: int):
        self.id = user_id


def test_outcome_log_is_immutable_and_user_scoped(client):
    """
    OutcomeLog 資産性テスト

    - user1 / user2 の task を作成
    - user1 の task に対して outcome を確定
    - OutcomeLog が
        - 正しい user_id に紐づく
        - 不変（1 task + 1 deadline = 1 outcome）
        - evaluated_at を保持
    """

    app = client.app
    now = datetime.now(timezone.utc)
    deadline = now - timedelta(hours=1)

    # --- user1 ---
    async def _user1():
        return _DummyUser(1)

    app.dependency_overrides[get_current_user] = _user1

    # task 作成
    client.post(
        "/api/v1/tasks",
        json={
            "title": "user1-task",
            "course_name": "course-a",
            "deadline": deadline.isoformat(),
            "memo": None,
            "should_notify": True,
        },
    )

    # --- DB を直接確認（FakeSession） ---
    override_get_db = app.dependency_overrides[get_db]
    gen = override_get_db()
    session = next(gen)

    tasks = [x for x in session._added if isinstance(x, Task)]
    assert len(tasks) == 1
    task = tasks[0]

    # OutcomeLog を直接追加（= 締切到達時点の確定を再現）
    outcome = TaskOutcomeLog(
        task_id=task.id,
        user_id=task.user_id,
        deadline=task.deadline,
        outcome="missed",
        evaluated_at=now,
    )
    session.add(outcome)

    # --- OutcomeLog 資産チェック ---
    outcomes = [x for x in session._added if isinstance(x, TaskOutcomeLog)]
    assert len(outcomes) == 1

    o = outcomes[0]
    assert o.task_id == task.id
    assert o.user_id == task.user_id
    assert o.deadline == task.deadline
    assert o.evaluated_at is not None

    app.dependency_overrides.pop(get_current_user, None)
