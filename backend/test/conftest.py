# backend/tests/conftest.py

import os
import sys
# ✅ pytest 実行時に `app` を import できるようにする（backend直下をPYTHONPATHに足す）
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # .../backend
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timezone
from app.main import app
from app.db.session import get_db
from app.core.security import get_current_user
from app.models.in_app_notification import InAppNotification
from app.models.notification_run import NotificationRun
from app.models.notification_setting import NotificationSetting
from app.models.webpush_subscription import WebPushSubscription

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
        # ✅ (status, cnt) のように複数カラムなら集計モード
        if len(ents) >= 2:
            self._is_group_query = True
        return self
    
    def one_or_none(self):
        items = getattr(self, "_items", [])
        if not items:
            return None
        if len(items) == 1:
            return items[0]
        raise AssertionError("Expected at most one row")

    def group_by(self, *args, **kwargs):
        self._is_group_query = True
        return self

    # ✅ 追加
    def order_by(self, *args, **kwargs):
        return self
    
    def order_by(self, *args, **kwargs):
        return self

    # ✅ 追加
    def first(self):
        # NotificationRun.latest 用のダミー（attribute accessされるのでオブジェクトで返す）
        return getattr(self, "_first_obj", None)

    def scalar(self):
        return self._dismissed if self._is_dismissed_query else self._total

    def all(self):
        # ✅ 集計クエリ（in-app summary）
        if self._is_group_query:
            return [
                ("sent", 1),
                ("failed", 1),
                ("deactivated", 1),
                ("skipped", 1),
                (None, 1),
            ]

        # ✅ 通知一覧（run summary / run in-app）
        return getattr(self, "_items", [])

        
    def limit(self, *args, **kwargs):
        return self

class _FakeInApp:
    def __init__(
        self,
        id: int,
        run_id: int,
        kind: str = "webpush",
        title: str = "t",
        body: str = "b",
        deep_link: str = "/dashboard?tab=today",
        task_id: int | None = None,
        deadline_at_send=None,
        offset_hours: int | None = None,
        created_at=None,
        dismissed_at=None,
        extra=None,
    ):
        self.id = id
        self.run_id = run_id
        self.kind = kind
        self.title = title
        self.body = body
        self.deep_link = deep_link
        self.task_id = task_id
        self.deadline_at_send = deadline_at_send
        self.offset_hours = offset_hours
        self.created_at = created_at
        self.dismissed_at = dismissed_at
        self.extra = extra

class FakeSession:
    def __init__(self):
        self._added = []
        self._id_seq = 1000
        self.total = 5
        self.dismissed = 2
        from datetime import datetime, timezone
        now = datetime(2025, 1, 6, tzinfo=timezone.utc)
        self.inapp_items = [
            _FakeInApp(
                id=101, run_id=1,
                created_at=now,
                deadline_at_send=now,
                extra={"webpush": {"status": "sent", "sent": 1}},
            ),
            _FakeInApp(
                id=102, run_id=1,
                created_at=now,
                deadline_at_send=now,
                dismissed_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
                extra={"webpush": {"status": "failed", "failed": 1}},
            ),
            _FakeInApp(
                id=103, run_id=1,
                created_at=now,
                deadline_at_send=now,
                extra={"webpush": {"status": "deactivated", "deactivated": 1}},
            ),
            _FakeInApp(
                id=104, run_id=1,
                created_at=now,
                deadline_at_send=now,
                extra={"webpush": {"status": "skipped"}},
            ),
            _FakeInApp(
                id=105, run_id=1,
                created_at=now,
                deadline_at_send=now,
                extra=None,  # unknown
            ),
        ]

        # ✅ 集計API（/notifications/in-app/summary）の group_by が期待する形
        self.group_rows = [("sent", 1), ("failed", 1), (None, 1)]

    def query(self, model):
        if model is InAppNotification:
            q = FakeQuery(total=self.total, dismissed=self.dismissed, rows=[])
            q._items = self.inapp_items
            return q
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
                webpush_sent=1,
                webpush_failed=1,
                webpush_deactivated=1,
                line_sent=0,
                line_failed=0,
                started_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
                finished_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
                stats={"snapshot": {"any": "ok"}},  # latestでは返さないがモデル上あってOK
            )
            return q
        
        if model is WebPushSubscription:
            class _Q:
                def __init__(self, items):
                    self._items = items

                def filter(self, *args, **kwargs):
                    return self
                
                def order_by(self, *args, **kwargs):
                    return self

                def limit(self, *args, **kwargs):
                    return self

                def one_or_none(self):
                    return self._items[0] if self._items else None

                def all(self):
                    return self._items

            # upsert 前は空、add() 後は _added に入る
            subs = [x for x in self._added if isinstance(x, WebPushSubscription)]
            return _Q(subs)
            
        if model is NotificationSetting:
            class _FakeSetting:
                def __init__(self):
                    self.enable_webpush = True  # ← debug-send を通したいので True

            class _Q:
                def filter(self, *args, **kwargs):
                    return self

                def one_or_none(self):
                    return _FakeSetting()

            return _Q()

        raise AssertionError(f"Unexpected model: {model}")

    def add(self, obj):
        # DBがやることを再現
        if getattr(obj, "id", None) is None:
            obj.id = self._id_seq
            self._id_seq += 1

        if getattr(obj, "created_at", None) is None:
            obj.created_at = datetime.now(timezone.utc)

        self._added.append(obj)

    def commit(self):
        pass

    def refresh(self, obj):
        pass

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
