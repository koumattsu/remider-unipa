from datetime import datetime, timezone

from app.core.security import get_current_user
from app.db.session import get_db

from app.models.user import User
from app.models.task import Task

class _DummyUser:
    def __init__(self, user_id: int):
        self.id = user_id

def test_admin_assets_export_runs_contract(client):
    """
    ExportRuns 契約テスト（最小）
    - POST で export_run を作成して保存できる
    - GET で履歴が返る
    - キー固定 / 型固定
    """
    app = client.app
    now = datetime.now(timezone.utc)

    async def _user1():
        return _DummyUser(1)

    app.dependency_overrides[get_current_user] = _user1

    # FakeSession を取得
    override_get_db = app.dependency_overrides[get_db]
    gen = override_get_db()
    session = next(gen)

    # 最低限のデータ（export が空でも良いが、資産がある方が現実的）
    u1 = User(id=1, line_user_id=None, display_name="u1", university=None, plan="free")
    session.add(u1)

    t1 = Task(
        user_id=1, title="t1", course_name="c1", deadline=now,
        memo=None, is_done=False, completed_at=None,
        should_notify=True, auto_notify_disabled_by_done=False,
        weekly_task_id=None, deleted_at=None,
    )
    session.add(t1)
    session.commit()

    # --- POST ---
    r = client.post("/api/v1/admin/assets/export/runs", params={"kind": "global", "limit": 100})
    assert r.status_code == 200

    data = r.json()
    assert isinstance(data, dict)
    assert set(data.keys()) == {"ok", "export_run_id", "export_hash"}
    assert data["ok"] is True
    assert isinstance(data["export_run_id"], int)
    assert isinstance(data["export_hash"], str)
    assert len(data["export_hash"]) >= 16

    # --- GET ---
    r2 = client.get("/api/v1/admin/assets/export/runs", params={"limit": 10})
    assert r2.status_code == 200
    d2 = r2.json()
    assert isinstance(d2, dict)
    assert set(d2.keys()) == {"items"}
    assert isinstance(d2["items"], list)
    assert len(d2["items"]) >= 1

    item = d2["items"][0]
    expected = {
        "id",
        "export_version",
        "kind",
        "user_id",
        "from",
        "to",
        "limit",
        "export_hash",
        "created_at",
    }
    assert set(item.keys()) == expected

    assert isinstance(item["id"], int)
    assert isinstance(item["export_version"], int)
    assert isinstance(item["kind"], str)
    assert (item["user_id"] is None) or isinstance(item["user_id"], int)
    assert (item["from"] is None) or isinstance(item["from"], str)
    assert (item["to"] is None) or isinstance(item["to"], str)
    assert isinstance(item["limit"], int)
    assert isinstance(item["export_hash"], str)
    assert (item["created_at"] is None) or isinstance(item["created_at"], str)

    app.dependency_overrides.pop(get_current_user, None)
