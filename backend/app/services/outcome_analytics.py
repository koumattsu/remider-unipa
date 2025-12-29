# backend/app/services/outcome_analytics.py

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import Optional, Literal

from sqlalchemy.orm import Session

from app.models.task_outcome_log import TaskOutcomeLog


Bucket = Literal["week", "month"]


@dataclass(frozen=True)
class OutcomeBucketRow:
    period_start: str  # YYYY-MM-DD (JST)
    total: int
    done: int
    missed: int
    done_rate: float


def _to_jst_date(deadline_utc: datetime) -> datetime.date:
    # deadline は timezone=True で入ってくる想定
    jst = ZoneInfo("Asia/Tokyo")
    return deadline_utc.astimezone(jst).date()


def _bucket_start(d: datetime.date, bucket: Bucket) -> datetime.date:
    if bucket == "month":
        return d.replace(day=1)
    # week: Monday start (JST)
    return d - timedelta(days=d.weekday())


def build_outcome_summary(
    db: Session,
    *,
    user_id: int,
    bucket: Bucket,
    from_deadline: Optional[datetime],
    to_deadline: Optional[datetime],
) -> dict:
    """
    OutcomeLog を唯一の真実として集計する（SSOT）
    - 集計単位: week | month（JST基準）
    - 期間フィルタ: TaskOutcomeLog.deadline（UTCのtimestamp）
    戻り値は API でそのまま返せる shape にする（破壊的変更を避ける）
    """
    q = db.query(TaskOutcomeLog).filter(TaskOutcomeLog.user_id == user_id)

    if from_deadline is not None:
        q = q.filter(TaskOutcomeLog.deadline >= from_deadline)
    if to_deadline is not None:
        q = q.filter(TaskOutcomeLog.deadline <= to_deadline)

    logs = q.order_by(TaskOutcomeLog.deadline.asc()).all()

    # bucket_start(str) -> counts
    agg: dict[str, dict[str, int]] = {}

    for log in logs:
        d_jst = _to_jst_date(log.deadline)
        start = _bucket_start(d_jst, bucket).isoformat()

        if start not in agg:
            agg[start] = {"total": 0, "done": 0, "missed": 0}

        agg[start]["total"] += 1
        if log.outcome == "done":
            agg[start]["done"] += 1
        else:
            # 'missed' 以外が来たら？は現状仕様上あり得ないが
            # ここは壊れにくさ優先で missed 扱いに寄せず、そのまま missed に入れる（契約で検知できる）
            agg[start]["missed"] += 1

    items: list[dict] = []
    for period_start in sorted(agg.keys()):
        total = agg[period_start]["total"]
        done = agg[period_start]["done"]
        missed = agg[period_start]["missed"]
        done_rate = (done / total) if total > 0 else 0.0

        items.append(
            {
                "period_start": period_start,
                "total": total,
                "done": done,
                "missed": missed,
                "done_rate": round(done_rate, 4),
            }
        )

    return {
        "range": {
            "timezone": "Asia/Tokyo",
            "bucket": bucket,
            "from": from_deadline,
            "to": to_deadline,
        },
        "items": items,
    }
