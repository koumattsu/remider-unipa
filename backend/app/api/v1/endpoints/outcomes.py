# backend/app/api/v1/endpoints/outcomes.py

from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.task_outcome_log import TaskOutcomeLog

router = APIRouter()

@router.get("", response_model=list[dict])
def list_outcomes(
    from_: Optional[datetime] = Query(None, alias="from"),
    to: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    OutcomeLog を期間指定で取得する（分析専用・read only）

    - from / to は deadline 基準
    - 指定なしの場合は全件
    """
    q = (
        db.query(TaskOutcomeLog)
        .filter(TaskOutcomeLog.user_id == current_user.id)
    )

    if from_:
        q = q.filter(TaskOutcomeLog.deadline >= from_)
    if to:
        q = q.filter(TaskOutcomeLog.deadline <= to)

    logs = q.order_by(TaskOutcomeLog.deadline.asc()).all()

    # まずは dict 返却でOK（後で schema 化できる）
    return [
        {
            "task_id": log.task_id,
            "deadline": log.deadline,
            "outcome": log.outcome,
            "evaluated_at": log.evaluated_at,
        }
        for log in logs
    ]
