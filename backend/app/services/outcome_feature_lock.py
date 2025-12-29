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
    try:
        with db.begin_nested():
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
    except IntegrityError:
        db.rollback()
        return False
