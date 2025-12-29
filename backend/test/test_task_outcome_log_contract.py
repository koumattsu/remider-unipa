from __future__ import annotations
from datetime import datetime, timezone
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError

from app.db.base import Base
import app.models  # noqa: F401  # Base.metadata に全モデル登録
from app.models.task_outcome_log import TaskOutcomeLog

def _insert_minimal_row(db, table, values: dict):
    cols = table.columns
    row = {}

    for c in cols:
        name = c.name

        if name in values:
            row[name] = values[name]
            continue

        if c.primary_key and (c.autoincrement is True or c.autoincrement == "auto"):
            continue
        if c.server_default is not None:
            continue
        if c.nullable:
            continue
        if c.default is not None:
            continue

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
            row[name] = "x"

    db.execute(table.insert().values(**row))

@pytest.fixture()
def db():
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

def test_task_outcome_log_contract__unique_by_user_task_deadline(db):
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

    d1 = datetime(2025, 1, 1, tzinfo=timezone.utc)

    a = TaskOutcomeLog(user_id=1, task_id=10, deadline=d1, outcome="done")
    b = TaskOutcomeLog(user_id=1, task_id=10, deadline=d1, outcome="missed")

    db.add_all([a, b])
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()

def test_task_outcome_log_contract__different_deadline_is_allowed(db):
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

    a = TaskOutcomeLog(
        user_id=1,
        task_id=10,
        deadline=datetime(2025, 1, 1, tzinfo=timezone.utc),
        outcome="done",
    )
    b = TaskOutcomeLog(
        user_id=1,
        task_id=10,
        deadline=datetime(2025, 1, 2, tzinfo=timezone.utc),
        outcome="done",
    )

    db.add_all([a, b])
    db.flush()  # ✅ deadlineが違えばOK
