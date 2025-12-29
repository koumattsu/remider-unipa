from __future__ import annotations
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import Optional, Literal
from sqlalchemy.orm import Session
from app.models.task import Task
from app.models.task_outcome_log import TaskOutcomeLog

Bucket = Literal["week", "month"]

def _to_jst_date(deadline_utc: datetime):
    jst = ZoneInfo("Asia/Tokyo")
    return deadline_utc.astimezone(jst).date()

def _bucket_start(d, bucket: Bucket):
    if bucket == "month":
        return d.replace(day=1)
    # week: Monday start
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
    - 集計バケット: week | month（JST基準）
    - 期間フィルタ: TaskOutcomeLog.deadline（UTC想定のdatetime）
    """
    q = db.query(TaskOutcomeLog).filter(TaskOutcomeLog.user_id == user_id)

    if from_deadline is not None:
        q = q.filter(TaskOutcomeLog.deadline >= from_deadline)
    if to_deadline is not None:
        q = q.filter(TaskOutcomeLog.deadline <= to_deadline)

    logs = q.order_by(TaskOutcomeLog.deadline.asc()).all()

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
            # 現状仕様は 'missed' のみだが、未知値は missed 側に倒さず、
            # 「missedカウント」に入れて契約テストで気づけるようにする
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

def build_outcome_missed_by_course(
    db: Session,
    *,
    user_id: int,
    from_deadline: Optional[datetime],
    to_deadline: Optional[datetime],
) -> dict:
    """
    OutcomeLog を唯一の真実として course別 missed率 を集計する（SSOT）
    - 分母/分子は TaskOutcomeLog
    - course_name は Task から「ラベル」として参照（見つからない場合は (unknown)）
    """
    q = db.query(TaskOutcomeLog).filter(TaskOutcomeLog.user_id == user_id)

    if from_deadline is not None:
        q = q.filter(TaskOutcomeLog.deadline >= from_deadline)
    if to_deadline is not None:
        q = q.filter(TaskOutcomeLog.deadline <= to_deadline)

    logs = q.order_by(TaskOutcomeLog.deadline.asc()).all()

    # ✅ ラベル付け用: task_id -> course_name
    tasks = db.query(Task).filter(Task.user_id == user_id).all()
    task_course: dict[int, str] = {t.id: t.course_name for t in tasks}
    agg: dict[str, dict[str, int]] = {}
    for log in logs:
        course = task_course.get(log.task_id) or "(unknown)"
        if course not in agg:
            agg[course] = {"total": 0, "missed": 0}
        agg[course]["total"] += 1
        if log.outcome != "done":
            agg[course]["missed"] += 1

    items: list[dict] = []
    for course_name, c in agg.items():
        total = c["total"]
        missed = c["missed"]
        missed_rate = (missed / total) if total > 0 else 0.0
        items.append(
            {
                "course_name": course_name,
                "total": total,
                "missed": missed,
                "missed_rate": round(missed_rate, 4),
            }
        )

    # ✅ 並びを決定的に（テスト/監査向け）
    items.sort(key=lambda x: (-x["missed_rate"], -x["missed"], -x["total"], x["course_name"]))

    return {
        "range": {
            "timezone": "Asia/Tokyo",
            "from": from_deadline,
            "to": to_deadline,
        },
        "items": items,
    }