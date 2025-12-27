# backend/tests/conftest.py

import os
import sys
# ✅ pytest 実行時に `app` を import できるようにする（backend直下をPYTHONPATHに足す）
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # .../backend
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.session import get_db
from app.core.security import get_current_user
from app.models.in_app_notification import InAppNotification
from app.models.notification_run import NotificationRun  

class _DummyUser:
    def __init__(self, user_id: int = 1):
        self.id = user_id

class FakeQuery:
    def __init__(self, total: int, dismissed: int, rows: list[tuple[object, int]]):
        self._total = total
        self._dismissed = dismissed
        self._rows = rows

        self._is_dismissed_query = False
        self._is_group_query = False

    def filter(self, *args, **kwargs):
        s = " ".join([str(a) for a in args])
        if "dismissed_at" in s and ("IS NOT" in s or "is not" in s):
            self._is_dismissed_query = True
        return self

    def with_entities(self, *ents):
        s = " ".join([str(e) for e in ents])
        if "status" in s:
            self._is_group_query = True
        return self

    def group_by(self, *args, **kwargs):
        return self

    # ✅ 追加
    def order_by(self, *args, **kwargs):
        return self

    # ✅ 追加
    def first(self):
        # NotificationRun.latest 用のダミー（attribute accessされるのでオブジェクトで返す）
        return getattr(self, "_first_obj", None)

    def scalar(self):
        return self._dismissed if self._is_dismissed_query else self._total

    def all(self):
        if self._is_group_query:
            return [("sent", 3), ("failed", 1), (None, 1)]
        return self._rows

class _FakeInApp:
    def __init__(self, dismissed_at=None, extra=None):
        self.dismissed_at = dismissed_at
        self.extra = extra

class FakeSession:
    def __init__(self):
        self.total = 5
        self.dismissed = 2
        from datetime import datetime, timezone
        self.rows = [
            _FakeInApp(dismissed_at=None, extra={"webpush": {"status": "sent", "sent": 1}}),
            _FakeInApp(dismissed_at=datetime(2025, 1, 1, tzinfo=timezone.utc), extra={"webpush": {"status": "failed", "failed": 1}}),
            _FakeInApp(dismissed_at=None, extra={"webpush": {"status": "deactivated", "deactivated": 1}}),
            _FakeInApp(dismissed_at=None, extra={"webpush": {"status": "skipped"}}),
            _FakeInApp(dismissed_at=None, extra=None),  # unknown になるケース
        ]

    def query(self, model):
        if model is InAppNotification:
            return FakeQuery(
                total=self.total,
                dismissed=self.dismissed,
                rows=self.rows,
            )
        if model is NotificationRun:
            q = FakeQuery(
                total=0,
                dismissed=0,
                rows=[],
            )

            # ✅ latest_notification_run() が参照する属性を揃えたダミー
            from datetime import datetime, timezone

            q._first_obj = NotificationRun(
                id=1,
                status="success",
                error_summary=None,
                users_processed=3,
                due_candidates_total=10,
                morning_candidates_total=5,
                inapp_created=2,
                webpush_sent=2,
                webpush_failed=1,
                webpush_deactivated=0,
                line_sent=0,
                line_failed=0,
                started_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
                finished_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
                stats={"snapshot": {"any": "ok"}},  # latestでは返さないがモデル上あってOK
            )

            return q

        raise AssertionError(f"Unexpected model: {model}")

@pytest.fixture()
def client():
    def _override_get_db():
        yield FakeSession()

    async def _override_get_current_user():
        return _DummyUser(1)

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = _override_get_current_user

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()
