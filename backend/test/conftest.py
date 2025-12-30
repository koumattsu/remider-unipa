# backend/test/conftest.py

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
from app.models.task import Task
from app.models.task_outcome_log import TaskOutcomeLog
from app.models.outcome_feature_snapshot import OutcomeFeatureSnapshot
from app.models.suggested_action_applied_event import SuggestedActionAppliedEvent

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
        self._eq_filters: dict[str, object] = {}

    def filter(self, *args, **kwargs):
        s = " ".join([str(a) for a in args])
        if "dismissed_at" in s and ("IS NOT" in s or "is not" in s):
            self._is_dismissed_query = True

        for a in args:
            left = getattr(a, "left", None)
            right = getattr(a, "right", None)
            op = getattr(a, "operator", None)

            # --- 1) (=) existing behavior ---
            if left is not None and right is not None:
                key = getattr(left, "key", None) or getattr(left, "name", None)
                val = getattr(right, "value", None)
                if key is not None and val is not None:
                    self._eq_filters[key] = val
                    continue

            # --- 2) IN (...) ---
            # SQLAlchemy: <col> IN (__[POSTCOMPILE_...])
            # a.right.value に list が入ることが多い
            if left is not None:
                key = getattr(left, "key", None) or getattr(left, "name", None)
                if key is not None:
                    rv = getattr(getattr(a, "right", None), "value", None)
                    if isinstance(rv, (list, tuple, set)):
                        if not hasattr(self, "_in_filters"):
                            self._in_filters = {}
                        self._in_filters[key] = set(rv)
                        continue

            # --- 3) >= / <= ---
            # right.value に datetime などが入る
            if left is not None and right is not None:
                key = getattr(left, "key", None) or getattr(left, "name", None)
                val = getattr(right, "value", None)
                if key is None or val is None:
                    continue

                op_str = str(op) if op is not None else str(a)
                if ">=" in op_str:
                    if not hasattr(self, "_ge_filters"):
                        self._ge_filters = {}
                    self._ge_filters[key] = val
                    continue
                if "<=" in op_str:
                    if not hasattr(self, "_le_filters"):
                        self._le_filters = {}
                    self._le_filters[key] = val
                    continue

        return self


    def with_entities(self, *ents):
        # ✅ (status, cnt) のように複数カラムなら集計モード
        if len(ents) >= 2:
            self._is_group_query = True
        return self
    
    def one_or_none(self):
        items = self._apply_filters(getattr(self, "_items", []))
        if not items:
            return None
        if len(items) == 1:
            return items[0]
        raise AssertionError("Expected at most one row")

    def group_by(self, *args, **kwargs):
        self._is_group_query = True
        return self
    
    def order_by(self, *args, **kwargs):
        return self

    def first(self):
        fo = getattr(self, "_first_obj", None)
        if fo is not None and not self._eq_filters:
            return fo

        items = self._apply_filters(getattr(self, "_items", []))
        return items[0] if items else None

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
        return self._apply_filters(getattr(self, "_items", []))
    
    def _apply_filters(self, items):
        if not self._eq_filters and not hasattr(self, "_in_filters") and not hasattr(self, "_ge_filters") and not hasattr(self, "_le_filters"):
            return items

        in_filters = getattr(self, "_in_filters", {})
        ge_filters = getattr(self, "_ge_filters", {})
        le_filters = getattr(self, "_le_filters", {})

        out = []
        for it in items:
            ok = True

            # (=)
            for k, v in self._eq_filters.items():
                if getattr(it, k, None) != v:
                    ok = False
                    break
            if not ok:
                continue

            # IN
            for k, vs in in_filters.items():
                if getattr(it, k, None) not in vs:
                    ok = False
                    break
            if not ok:
                continue

            # >=
            for k, v in ge_filters.items():
                x = getattr(it, k, None)
                if x is None or x < v:
                    ok = False
                    break
            if not ok:
                continue

            # <=
            for k, v in le_filters.items():
                x = getattr(it, k, None)
                if x is None or x > v:
                    ok = False
                    break
            if ok:
                out.append(it)

  
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
        self.action_events = []
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
        # ✅ Task（course_nameラベル用）
        self.tasks = [
            Task(
                id=10,
                user_id=1,
                title="t1",
                course_name="線形代数",
                deadline=now,
                memo=None,
                is_done=False,
                completed_at=None,
                should_notify=True,
                auto_notify_disabled_by_done=False,
                weekly_task_id=None,
                deleted_at=None,
            ),
            Task(
                id=11,
                user_id=1,
                title="t2",
                course_name="電磁気",
                deadline=now,
                memo=None,
                is_done=False,
                completed_at=None,
                should_notify=True,
                auto_notify_disabled_by_done=False,
                weekly_task_id=None,
                deleted_at=None,
            ),
        ]
        # ✅ OutcomeLog（分析用）
        self.outcome_logs = [
            TaskOutcomeLog(
                id=201,
                user_id=1,
                task_id=10,
                deadline=datetime(2025, 1, 6, tzinfo=timezone.utc),
                outcome="done",
                evaluated_at=datetime(2025, 1, 6, tzinfo=timezone.utc),
                created_at=datetime(2025, 1, 6, tzinfo=timezone.utc),
            ),
            TaskOutcomeLog(
                id=202,
                user_id=1,
                task_id=11,
                deadline=datetime(2025, 1, 7, tzinfo=timezone.utc),
                outcome="missed",
                evaluated_at=datetime(2025, 1, 7, tzinfo=timezone.utc),
                created_at=datetime(2025, 1, 7, tzinfo=timezone.utc),
            ),
        ]
        # ✅ Feature Snapshot（検証API用）
        self.feature_rows = [
            OutcomeFeatureSnapshot(
                id=301,
                user_id=1,
                task_id=10,
                deadline=now,
                feature_version="v1",
                features={"deadline_dow_jst": 0, "deadline_hour_jst": 9, "has_memo": False},
                created_at=now,
            )
        ]

        # ✅ 集計API（/notifications/in-app/summary）の group_by が期待する形
        self.group_rows = [("sent", 1), ("failed", 1), (None, 1)]

    def query(self, model):
        if model is InAppNotification:
            q = FakeQuery(total=self.total, dismissed=self.dismissed, rows=[])
            q._items = self.inapp_items
            return q
        if model is SuggestedActionAppliedEvent:
            q = FakeQuery(total=0, dismissed=0, rows=[])
            # add() されたものが見えるようにする（DBっぽく）
            q._items = [x for x in self._added if isinstance(x, SuggestedActionAppliedEvent)]
            return q
        if model is NotificationRun:
            q = FakeQuery(
                total=0,
                dismissed=0,
                rows=[],
            )

            # ✅ latest_notification_run() が参照する属性を揃えたダミー
            from datetime import datetime, timezone

            dummy = NotificationRun(
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
                stats={
                    "v": 1,
                    "kind": "notification_run_stats",
                    "generated_at": datetime(2025, 1, 1, tzinfo=timezone.utc).isoformat(),
                    "payload": {
                        "snapshot": {"any": "ok"},
                    },
                },  # latestでは返さないがモデル上あってOK
            )

            q._first_obj = dummy
            q._items = [dummy]
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
        
        if model is TaskOutcomeLog:
            q = FakeQuery(total=0, dismissed=0, rows=[])
            q._items = self.outcome_logs
            return q
        if model is OutcomeFeatureSnapshot:
            q = FakeQuery(total=0, dismissed=0, rows=[])
            q._items = self.feature_rows
            return q
        if model is Task:
            q = FakeQuery(total=0, dismissed=0, rows=[])
            q._items = self.tasks
            return q
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
