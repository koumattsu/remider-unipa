# backend/test/test_notification_decision_contract.py

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, List, Tuple
import pytest
from sqlalchemy.exc import IntegrityError

from app.models.task import Task
from app.services import notification as notif


# -----------------------------
# Mini DB / Query (test-local)
# -----------------------------
class _BeginNested:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        # 例外は外に投げる（IntegrityError を notif.try_mark... が握る）
        return False


class _Query:
    def __init__(self, session: "MiniSession", kind: str):
        self.s = session
        self.kind = kind

    def outerjoin(self, *args, **kwargs):
        return self

    def filter(self, *args, **kwargs):
        # 本テストは「通知判定の仕様」を縛るのが目的。
        # DBフィルタ自体の正しさはここで再現しない（その代わり is_notification_candidate を縛る）。
        return self

    def all(self):
        if self.kind == "task_with_weekly":
            # (Task, weekly_is_active) のタプル配列
            return self.s.task_rows
        raise AssertionError(f"Unexpected .all() kind={self.kind}")

    def first(self):
        if self.kind == "override":
            # task_id に対応する override を返す（無ければ None）
            return self.s.override_by_task_id.get(self.s._override_task_id)
        raise AssertionError(f"Unexpected .first() kind={self.kind}")

    def one_or_none(self):
        raise AssertionError("Not used in this test")


class MiniSession:
    """
    notif.get_tasks_due_in_offsets / get_tasks_due_today_morning が必要とする
    最小限の Session を test 内に閉じ込めたもの。
    """

    def __init__(self, task_rows: List[Tuple[Task, bool | None]]):
        self.task_rows = task_rows
        self.override_by_task_id: dict[int, Any] = {}
        self._override_task_id: int | None = None

        # (user_id, task_id, deadline_utc_iso, offset_hours) の一意ロック再現
        self._locks: set[tuple[int, int, str, int]] = set()

    def query(self, *models):
        # notif.get_tasks_due_in_offsets:
        #   db.query(Task, WeeklyTask.is_active) ...
        if len(models) == 2 and models[0] is Task:
            return _Query(self, "task_with_weekly")

        # notif.get_tasks_due_in_offsets:
        #   db.query(TaskNotificationOverride).filter(...task_id == X).first()
        # ここは filter の式解析を避け、テスト側で _override_task_id を直接セットする
        # → なので query が呼ばれたら override 用 Query を返す
        if len(models) == 1 and models[0].__name__ == "TaskNotificationOverride":
            return _Query(self, "override")

        raise AssertionError(f"Unexpected query models={models}")

    def begin_nested(self):
        return _BeginNested()

    def add(self, obj):
        # try_mark_notification_as_sent が TaskNotificationLog を add して flush する。
        # ここでは add 自体は何もしない（flush でユニーク判定を行う）
        self._last_added = obj

    def flush(self):
        # try_mark_notification_as_sent の unique 制約相当をここで再現
        obj = getattr(self, "_last_added", None)
        if obj is None:
            return
        key = (obj.user_id, obj.task_id, obj.deadline_at_send.isoformat(), obj.offset_hours)
        if key in self._locks:
            raise IntegrityError("duplicate", params=None, orig=None)
        self._locks.add(key)

    def commit(self):
        pass


# -----------------------------
# Fixed time helper (monkeypatch)
# -----------------------------
class _FixedDatetime:
    """
    notif.py は `from datetime import datetime` なので、
    notif.datetime を差し替えるためのラッパ。
    """
    _fixed_now: datetime = datetime(2025, 1, 6, 12, 0, 0, tzinfo=timezone.utc)

    @classmethod
    def now(cls, tz=None):
        if tz is None:
            return cls._fixed_now.replace(tzinfo=None)
        return cls._fixed_now.astimezone(tz)

    @staticmethod
    def combine(d, t):
        # get_tasks_due_today_morning で使う
        return datetime.combine(d, t)


@pytest.fixture()
def fixed_now(monkeypatch):
    monkeypatch.setattr(notif, "datetime", _FixedDatetime)
    return _FixedDatetime._fixed_now


def _make_task(
    *,
    task_id: int,
    user_id: int = 1,
    deadline_utc: datetime,
    is_done: bool = False,
    should_notify: bool = True,
    deleted_at=None,
    weekly_task_id=None,
) -> Task:
    t = Task()
    t.id = task_id
    t.user_id = user_id
    t.title = f"t{task_id}"
    t.course_name = "c"
    t.deadline = deadline_utc
    t.is_done = is_done
    t.should_notify = should_notify
    t.deleted_at = deleted_at
    t.weekly_task_id = weekly_task_id
    return t


def test_notification_decision_contract__done_past_and_dedupe(fixed_now):
    now = fixed_now

    # 1) 1時間前ウィンドウに入るタスク（diff_hours=1.2 → 1.0〜1.5内）
    t_due = _make_task(task_id=10, deadline_utc=now + timedelta(hours=1, minutes=12))

    # 2) 過去締切 → 絶対に候補に入らない
    t_past = _make_task(task_id=11, deadline_utc=now - timedelta(minutes=1))

    # 3) 完了済み → 絶対に候補に入らない
    t_done = _make_task(task_id=12, deadline_utc=now + timedelta(hours=1, minutes=12), is_done=True)

    db = MiniSession(
        task_rows=[
            (t_due, None),
            (t_past, None),
            (t_done, None),
        ]
    )

    # --- 1st run: due は t_due のみ、past/done は除外 ---
    c1 = notif.collect_notification_candidates(db, user_id=1, offsets_hours=[1], run_id=1)

    assert 1 in c1.due_in_hours
    assert [t.id for t in c1.due_in_hours[1]] == [10]

    # past/done は due 側から除外されている
    flat1 = [t.id for ts in c1.due_in_hours.values() for t in ts]
    assert 11 not in flat1
    assert 12 not in flat1

    # morning 側にも done は入らない（仕様の安全網）
    assert 12 not in [t.id for t in c1.morning]

    # --- 2nd run: 同じ deadline + offset は dedupe され、t_due は出てこない ---
    c2 = notif.collect_notification_candidates(db, user_id=1, offsets_hours=[1], run_id=2)

    # 2回目はロック済みなので空になる（dedupe 契約）
    assert c2.due_in_hours.get(1, []) == []
