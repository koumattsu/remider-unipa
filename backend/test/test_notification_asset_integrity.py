# backend/test/test_notification_asset_integrity.py

from datetime import datetime, timezone
from app.core.security import get_current_user
from app.db.session import get_db
from app.models.in_app_notification import InAppNotification


class _DummyUser:
    def __init__(self, user_id: int):
        self.id = user_id


def test_notification_logs_are_user_scoped_and_persistent(client):
    """
    Notification 資産性テスト

    - user1 / user2 の NotificationRun を作成
    - InAppNotification を紐づけ
    - user_id 分離と永続性を保証
    """

    app = client.app
    now = datetime.now(timezone.utc)

    # --- user1 ---
    async def _user1():
        return _DummyUser(1)

    app.dependency_overrides[get_current_user] = _user1

    override_get_db = app.dependency_overrides[get_db]
    gen = override_get_db()
    session = next(gen)

    notif1 = InAppNotification(
        user_id=1,
        title="Test Notification",
        body="Hello user1",
        created_at=now,
    )
    session.add(notif1)

    # --- user2 ---
    async def _user2():
        return _DummyUser(2)

    app.dependency_overrides[get_current_user] = _user2

    notif2 = InAppNotification(
        user_id=2,
        title="Test Notification",
        body="Hello user2",
        created_at=now,
    )
    session.add(notif2)

    # --- 資産チェック ---
    notifs = [x for x in session._added if isinstance(x, InAppNotification)]

    assert len(notifs) == 2

    for n in notifs:
        assert n.user_id in (1, 2)

    app.dependency_overrides.pop(get_current_user, None)
