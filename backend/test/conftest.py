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
from sqlalchemy import func

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
        # dismissed_at isnot(None) が来たら dismissed count 側に寄せる
        s = " ".join([str(a) for a in args])
        if "dismissed_at" in s and ("IS NOT" in s or "is not" in s):
            self._is_dismissed_query = True
        return self

    def with_entities(self, *ents):
        s = " ".join([str(e) for e in ents])
        # group by 用の status_expr / label が入るとだいたい "status" が混ざる
        if "status" in s:
            self._is_group_query = True
        return self

    def group_by(self, *args, **kwargs):
        return self

    def scalar(self):
        # count(*) 系
        return self._dismissed if self._is_dismissed_query else self._total

    def all(self):
        # group by status の rows
        return self._rows


class FakeSession:
    def __init__(self):
        # テストデータ（必要ならここだけ変える）
        self.total = 5
        self.dismissed = 2
        # status None は unknown に寄ることを確認したい
        self.rows = [("sent", 3), ("failed", 1), (None, 1)]

    def query(self, model):
        # 今回は InAppNotification のみ想定（他が来たら落とす）
        assert model is InAppNotification
        return FakeQuery(total=self.total, dismissed=self.dismissed, rows=self.rows)

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
