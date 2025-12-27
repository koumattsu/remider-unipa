# backend/test/test_webpush_aggregate_contract.py

from app.services.webpush_aggregate import calc_webpush_events_for_run

class _FakeInApp:
    def __init__(self, extra):
        self.extra = extra

class _Q:
    def __init__(self, items):
        self._items = items

    def filter(self, *args, **kwargs):
        return self

    def group_by(self, *args, **kwargs):
        return self

    def all(self):
        return self._items

class FakeSessionFallbackOnly:
    """
    ✅ JSONB集計( db.query(status_expr, count) )は方言なので、ここでは例外を投げて fallback に入れる
    """
    def __init__(self, items):
        self._items = items

    def query(self, *entities):
        # db.query(<expr>, func.count(...)) 形式を強制的に失敗させる
        if len(entities) >= 2:
            raise Exception("jsonb aggregation not supported in test fake")

        # fallback: db.query(InAppNotification) は 1 entity なのでここに来る
        return _Q(self._items)


def test_calc_webpush_events_for_run_contract__shape_and_counts():
    """
    契約テスト:
    - 必ず keys が固定（sent/failed/deactivated/skipped/unknown）
    - value は int かつ >=0
    - 方言に依存しない（fallback でも正しい集計になる）
    """
    items = [
        _FakeInApp({"webpush": {"status": "sent"}}),
        _FakeInApp({"webpush": {"status": "failed"}}),
        _FakeInApp({"webpush": {"status": "deactivated"}}),
        _FakeInApp({"webpush": {"status": "skipped"}}),
        _FakeInApp(None),  # extra が dict じゃない → unknown
        _FakeInApp({"webpush": "oops"}),  # webpush が dict じゃない → unknown
        _FakeInApp({"webpush": {"status": "weird"}}),  # 想定外status → unknown
        _FakeInApp({"webpush": {}}),  # status None → unknown
    ]
    db = FakeSessionFallbackOnly(items)

    events = calc_webpush_events_for_run(db, run_id=1)

    assert isinstance(events, dict)
    assert set(events.keys()) == {"sent", "failed", "deactivated", "skipped", "unknown"}

    for k in ["sent", "failed", "deactivated", "skipped", "unknown"]:
        assert isinstance(events[k], int)
        assert events[k] >= 0

    assert events["sent"] == 1
    assert events["failed"] == 1
    assert events["deactivated"] == 1
    assert events["skipped"] == 1
    assert events["unknown"] == 4


def test_calc_webpush_events_for_run_contract__empty_is_zeros():
    """
    契約テスト:
    - 対象0件でも必ずゼロで返る（落ちない）
    """
    db = FakeSessionFallbackOnly(items=[])

    events = calc_webpush_events_for_run(db, run_id=999)

    assert set(events.keys()) == {"sent", "failed", "deactivated", "skipped", "unknown"}
    assert events == {"sent": 0, "failed": 0, "deactivated": 0, "skipped": 0, "unknown": 0}