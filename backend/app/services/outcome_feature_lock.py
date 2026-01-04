# backend/services/outcome_feature_lock.py

from __future__ import annotations

from datetime import datetime
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.outcome_feature_snapshot import OutcomeFeatureSnapshot


def try_mark_outcome_feature_as_saved(
    db: Session,
    *,
    user_id: int,
    task_id: int,
    deadline_utc: datetime,
    feature_version: str,
    features: dict,
) -> bool:
    """
    OutcomeFeatureSnapshot の保存ロック（UNIQUE + flush）
    - commit は呼び出し側に任せる
    """
    # ✅ 監査耐性：UTC timezone-aware を強制（naive混入で集計が壊れるのを防ぐ）
    if deadline_utc.tzinfo is None:
        raise ValueError("deadline_utc must be timezone-aware (UTC)")

    with db.begin_nested() as nested:
        try:
            row = OutcomeFeatureSnapshot(
                user_id=user_id,
                task_id=task_id,
                deadline=deadline_utc,
                feature_version=feature_version,
                features=features,
            )
            db.add(row)
            db.flush()  # ✅ UNIQUE 競合をここで確定
            return True
        except IntegrityError as e:
            # ✅ UNIQUE競合だけ「既に保存済み」として扱う
            # Postgres: unique_violation = 23505
            pgcode = getattr(getattr(e, "orig", None), "pgcode", None)
            if pgcode == "23505":
                nested.rollback()
                return False
            raise
