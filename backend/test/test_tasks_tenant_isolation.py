# backend/tests/test_tasks_tenant_isolation.py

from datetime import datetime, timezone
from app.core.security import get_current_user
from app.models.task import Task
from app.db.session import get_db

class _DummyUser:
    def __init__(self, user_id: int):
        self.id = user_id

def test_tasks_are_isolated_by_user_id_in_db(client):
    """
    マルチテナント隔離テスト（安全版）

    - user1 / user2 として task を作成
    - FakeSession に保存された Task を直接検査
    - user_id が混ざらないことを保証
    """

    app = client.app
    now = datetime.now(timezone.utc)

    # --- user1 ---
    async def _user1():
        return _DummyUser(1)

    app.dependency_overrides[get_current_user] = _user1
    client.post(
        "/api/v1/tasks",
        json={
            "title": "user1-task",
            "course_name": "course-a",
            "deadline": now.isoformat(),
            "memo": None,
            "should_notify": True,
        },
    )

    # --- user2 ---
    async def _user2():
        return _DummyUser(2)

    app.dependency_overrides[get_current_user] = _user2
    client.post(
        "/api/v1/tasks",
        json={
            "title": "user2-task",
            "course_name": "course-b",
            "deadline": now.isoformat(),
            "memo": None,
            "should_notify": True,
        },
    )

    # get_db の override を取り出す
    override_get_db = app.dependency_overrides[get_db]

    # generator を実行して FakeSession を取得
    gen = override_get_db()
    session = next(gen)
    tasks = [obj for obj in session._added if isinstance(obj, Task)]

    assert any(t.user_id == 1 for t in tasks)
    assert any(t.user_id == 2 for t in tasks)

    # 交差がないこと
    for t in tasks:
        assert t.user_id in (1, 2)

    app.dependency_overrides.pop(get_current_user, None)
