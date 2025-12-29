# backend/app/api/v1/endpoints/analytics_outcomes.py

from datetime import datetime
from typing import Optional, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.services.outcome_analytics import build_outcome_summary

router = APIRouter()

@router.get("/outcomes/summary", response_model=dict)
def get_outcome_summary(
    bucket: Literal["week", "month"] = Query("week"),
    from_: Optional[datetime] = Query(None, alias="from"),
    to: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    OutcomeLog を唯一の真実として集計した達成率を返す（read-only）
    - from/to は deadline 基準（UTC想定のdatetime）
    - bucket は JST基準の週/月
    """
    return build_outcome_summary(
        db,
        user_id=current_user.id,
        bucket=bucket,
        from_deadline=from_,
        to_deadline=to,
    )
