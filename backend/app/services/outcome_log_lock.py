# backend/app/services/outcome_log_lock.py

from __future__ import annotations
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.models.task_outcome_log import TaskOutcomeLog

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)

def try_mark_outcome_as_evaluated(
    db: Session,
    *,
    user_id: int,
    task_id: int,
    deadline_utc: datetime,
    outcome: str,
    evaluated_at_utc: datetime | None = None,
) -> bool:
    """
    ✅ Outcome確定ロック（副作用）
    - UNIQUE(user_id, task_id, deadline) を利用して「その締切は1回だけ確定」を保証
    - begin_nested + flush で UNIQUE を即時評価
    - commit は呼ばない（呼び出し側でまとめてcommit）
    戻り値:
      - True: 今回新規に確定できた（＝初回評価）
      - False: 既に確定済み（＝二重評価防止でスキップ）
    """
    if evaluated_at_utc is None:
        evaluated_at_utc = _utcnow()

    log = TaskOutcomeLog(
        user_id=user_id,
        task_id=task_id,
        deadline=deadline_utc,
        outcome=outcome,
        evaluated_at=evaluated_at_utc,
    )
    try:
        with db.begin_nested():
            db.add(log)
            db.flush()  # ✅ ここで UNIQUE を評価
        return True
    except IntegrityError:
        db.rollback()
        return False
