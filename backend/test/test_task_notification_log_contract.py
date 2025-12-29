# backend/test/test_task_notification_log_contract.py

from __future__ import annotations
from datetime import datetime, timezone
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError
from app.db.base import Base
import app.models  # noqa: F401  # ← Base.metadata に全モデル登録させる
from app.models.task_notification_log import TaskNotificationLog

def _insert_minimal_row(db, table, values: dict):
    """
    できるだけ推測せず、必須カラムだけ埋めて INSERT する。
    - server_default / nullable=True / autoincrement は省略できる
    - nullable=False で default も server_default も無いものだけ埋める
    """
    cols = table.columns
    row = {}

    for c in cols:
        name = c.name

        # 明示指定があればそれを優先
        if name in values:
            row[name] = values[name]
            continue

        # PK auto は省略
        if c.primary_key and (c.autoincrement is True or c.autoincrement == "auto"):
            continue

        # server_default があるなら省略
        if c.server_default is not None:
            continue

        # nullable なら省略（NULLでOK）
        if c.nullable:
            continue

        # default があるなら省略（SQLAlchemy側で入る可能性）
        if c.default is not None:
            continue

        # ここに来るのは「nullable=False で default も server_default も無い」カラム
        # 推測を最小にするため型に応じた無難値を入れる
        py = getattr(c.type, "python_type", None)
        if py is int:
            row[name] = 0
        elif py is bool:
            row[name] = False
        elif py is str:
            row[name] = "x"
        elif py is datetime:
            row[name] = datetime.now(timezone.utc)
        else:
            # 型が分からない場合でも落ちないように文字列
            row[name] = "x"

    db.execute(table.insert().values(**row))


@pytest.fixture()
def db():
    # ✅ 実DB（SQLite in-memory）で UNIQUE 制約を検証する
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    Base.metadata.create_all(bind=engine)

    s = TestingSessionLocal()
    try:
        yield s
    finally:
        s.close()


def test_task_notification_log_contract__unique_by_user_task_deadline_offset(db):
    users = Base.metadata.tables["users"]
    tasks = Base.metadata.tables["tasks"]

    # ✅ user を1件作る（schemaが変わっても壊れにくい）
    _insert_minimal_row(db, users, {"id": 1})
    # ✅ task を1件作る（user_idだけは必須で合わせる）
    _insert_minimal_row(
        db,
        tasks,
        {
            "id": 10,
            "user_id": 1,
            "title": "t",
            "course_name": "c",
            "deadline": datetime(2025, 1, 1, tzinfo=timezone.utc),
        },
    )
    db.commit()

    # (user_id, task_id, deadline_at_send, offset_hours) が同じなら 2回目はDBが拒否する
    d1 = datetime(2025, 1, 1, tzinfo=timezone.utc)

    a = TaskNotificationLog(
        user_id=1,
        task_id=10,
        deadline_at_send=d1,
        offset_hours=3,
    )

    b = TaskNotificationLog(
        user_id=1,
        task_id=10,
        deadline_at_send=d1,
        offset_hours=3,
    )

    db.add_all([a, b])

    with pytest.raises(IntegrityError):
        db.commit()

    db.rollback()


def test_task_notification_log_contract__different_deadline_is_allowed(db):
    users = Base.metadata.tables["users"]
    tasks = Base.metadata.tables["tasks"]

    _insert_minimal_row(db, users, {"id": 1})
    _insert_minimal_row(
        db,
        tasks,
        {
            "id": 10,
            "user_id": 1,
            "title": "t",
            "course_name": "c",
            "deadline": datetime(2025, 1, 1, tzinfo=timezone.utc),
        },
    )
    db.commit()

    # deadline_at_send が違えばOK（締切変更に強いログ）
    a = TaskNotificationLog(
        user_id=1,
        task_id=10,
        deadline_at_send=datetime(2025, 1, 1, tzinfo=timezone.utc),
        offset_hours=3,
    )
    b = TaskNotificationLog(
        user_id=1,
        task_id=10,
        deadline_at_send=datetime(2025, 1, 2, tzinfo=timezone.utc),
        offset_hours=3,
    )
    db.add_all([a, b])

    # ✅ 契約：deadline_at_send が違えば OK（締切変更に強いログ）
    db.flush()

def test_task_notification_log_contract__different_offset_is_allowed(db):
    users = Base.metadata.tables["users"]
    tasks = Base.metadata.tables["tasks"]

    _insert_minimal_row(db, users, {"id": 1})
    _insert_minimal_row(
        db,
        tasks,
        {
            "id": 10,
            "user_id": 1,
            "title": "t",
            "course_name": "c",
            "deadline": datetime(2025, 1, 1, tzinfo=timezone.utc),
        },
    )
    db.commit()

    # offset_hours が違えばOK（3時間前と朝通知など）
    d1 = datetime(2025, 1, 1, tzinfo=timezone.utc)

    a = TaskNotificationLog(user_id=1, task_id=10, deadline_at_send=d1, offset_hours=3)
    b = TaskNotificationLog(user_id=1, task_id=10, deadline_at_send=d1, offset_hours=0)
    db.add_all([a, b])
    db.commit()