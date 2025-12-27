# backend/test/test_in_app_summary_aggregate_contract.py

from app.services.in_app_summary_aggregate import calc_in_app_summary_for_run

class _FakeInApp:
    def __init__(self, dismissed_at=None, extra=None):
        self.dismissed_at = dismissed_at
        self.extra = extra

class _Q:
    def __init__(self, items):
        self._items = items

    def filter(self, *args, **kwargs):
        return self

    def all(self):
        return self._items

    def scalar(self):
        # DB集計系が呼ばれたら落として fallback に入れる
        raise Exception("aggregate not supported in test fake")

class FakeSessionFallbackOnly:
    """
    ✅ DB集計は強制的に失敗させて fallback を通す
    （SQLite/FakeSessionでも契約が守られることを固定する）
    """
    def __init__(self, items):
        self._items = items

    def query(self, *entities):
        # count/sum 系は scalar() を呼ぶ想定なので落とす
        if len(entities) >= 1 and getattr(entities[0], "__class__", None).__name__ != "DeclarativeMeta":
            return _Q([])  # 念のため
        return _Q(self._items)


def test_calc_in_app_summary_for_run_contract__shape_and_counts():
    from datetime import datetime, timezone

    items = [
        _FakeInApp(dismissed_at=datetime(2025, 1, 1, tzinfo=timezone.utc), extra={"webpush": {"sent": 2}}),
        _FakeInApp(dismissed_at=None, extra={"webpush": {"failed": 1}}),
        _FakeInApp(dismissed_at=None, extra={"webpush": {"deactivated": 3}}),
        _FakeInApp(dismissed_at=None, extra=None),                 # unknown
        _FakeInApp(dismissed_at=None, extra={"webpush": "oops"}),   # unknown
        _FakeInApp(dismissed_at=None, extra={"webpush": {}}),       # counts 0
    ]

    db = FakeSessionFallbackOnly(items)

    summary = calc_in_app_summary_for_run(db, run_id=1)

    assert isinstance(summary, dict)
    assert set(summary.keys()) == {
        "inapp_total",
        "dismissed_count",
        "delivered",
        "failed",
        "deactivated",
        "unknown",
    }

    for k in summary.keys():
        assert isinstance(summary[k], int)
        assert summary[k] >= 0

    assert summary["inapp_total"] == 6
    assert summary["dismissed_count"] == 1
    assert summary["delivered"] == 2
    assert summary["failed"] == 1
    assert summary["deactivated"] == 3
    assert summary["unknown"] == 2


def test_calc_in_app_summary_for_run_contract__empty_is_zeros():
    db = FakeSessionFallbackOnly(items=[])

    summary = calc_in_app_summary_for_run(db, run_id=999)

    assert summary == {
        "inapp_total": 0,
        "dismissed_count": 0,
        "delivered": 0,
        "failed": 0,
        "deactivated": 0,
        "unknown": 0,
    }
