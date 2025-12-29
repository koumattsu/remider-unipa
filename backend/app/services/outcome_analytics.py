# backend/app/services/outcome_analytics.py

from __future__ import annotations
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import Optional, Literal
from sqlalchemy.orm import Session
from app.models.task import Task
from app.models.task_outcome_log import TaskOutcomeLog
from app.models.outcome_feature_snapshot import OutcomeFeatureSnapshot

Bucket = Literal["week", "month"]

def _to_jst_date(deadline_utc: datetime):
    jst = ZoneInfo("Asia/Tokyo")
    return deadline_utc.astimezone(jst).date()

def _bucket_start(d, bucket: Bucket):
    if bucket == "month":
        return d.replace(day=1)
    # week: Monday start
    return d - timedelta(days=d.weekday())

def _bucket_end(start, bucket: Bucket):
    """
    period_end は exclusive（JST日付）
    - week: 次の週の月曜
    - month: 翌月の1日
    """
    if bucket == "month":
        # start は必ず月初の date
        if start.month == 12:
            return start.replace(year=start.year + 1, month=1, day=1)
        return start.replace(month=start.month + 1, day=1)
    # week
    return start + timedelta(days=7)

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

    logs = q.order_by(TaskOutcomeLog.deadline.asc()).all() or []

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

        # JST日付（YYYY-MM-DD）で end を計算（exclusive）
        start_d = datetime.fromisoformat(period_start).date()
        period_end = _bucket_end(start_d, bucket).isoformat()

        items.append(
            {
                "period_start": period_start,
                "period_end": period_end,
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

    logs = q.order_by(TaskOutcomeLog.deadline.asc()).all() or []
    tasks = db.query(Task).filter(Task.user_id == user_id).all() or []
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

def build_outcome_training_set(
    db: Session,
    *,
    user_id: int,
    feature_version: str,
    from_deadline: Optional[datetime],
    to_deadline: Optional[datetime],
    limit: int,
) -> dict:
    """
    ✅ 教師データSSOT（read-only）
    - OutcomeLog（教師ラベル）× FeatureSnapshot（特徴量資産）を束ねる
    - JOINせずに 2クエリ + map（FakeSession / テスト容易性 / 事故回避）
    - from/to は deadline 基準（UTCのdatetimeを想定）
    """
    # 1) ラベル（OutcomeLog）
    q = db.query(TaskOutcomeLog).filter(TaskOutcomeLog.user_id == user_id)

    if from_deadline is not None:
        q = q.filter(TaskOutcomeLog.deadline >= from_deadline)
    if to_deadline is not None:
        q = q.filter(TaskOutcomeLog.deadline <= to_deadline)

    logs = q.order_by(TaskOutcomeLog.deadline.desc()).limit(limit).all() or []

    if not logs:
        return {
            "range": {
                "timezone": "Asia/Tokyo",
                "version": feature_version,
                "from": from_deadline,
                "to": to_deadline,
                "limit": limit,
            },
            "items": [],
        }

    # 2) 特徴量（FeatureSnapshot）
    task_ids = [l.task_id for l in logs]
    deadlines = [l.deadline for l in logs]

    fq = (
        db.query(OutcomeFeatureSnapshot)
        .filter(OutcomeFeatureSnapshot.user_id == user_id)
        .filter(OutcomeFeatureSnapshot.feature_version == feature_version)
        .filter(OutcomeFeatureSnapshot.task_id.in_(task_ids))
        .filter(OutcomeFeatureSnapshot.deadline.in_(deadlines))
    )

    # from/to も同じ条件を入れておく（安全側）
    if from_deadline is not None:
        fq = fq.filter(OutcomeFeatureSnapshot.deadline >= from_deadline)
    if to_deadline is not None:
        fq = fq.filter(OutcomeFeatureSnapshot.deadline <= to_deadline)

    snaps = fq.all() or []
    snap_map: dict[tuple[int, datetime], OutcomeFeatureSnapshot] = {
        (s.task_id, s.deadline): s for s in snaps
    }

    # 3) 返却（ログ順を維持して決定的に）
    items: list[dict] = []
    for l in logs:
        s = snap_map.get((l.task_id, l.deadline))
        if s is None:
            # ✅ 特徴量が無いものは training から除外（学習不能なので）
            continue
        items.append(
            {
                "task_id": l.task_id,
                "deadline": l.deadline,
                "outcome": l.outcome,
                "feature_version": s.feature_version,
                "features": s.features,
            }
        )

    return {
        "range": {
            "timezone": "Asia/Tokyo",
            "version": feature_version,
            "from": from_deadline,
            "to": to_deadline,
            "limit": limit,
        },
        "items": items,
    }

def build_outcome_risk_by_deadline_time(
    db: Session,
    *,
    user_id: int,
    from_deadline: Optional[datetime],
    to_deadline: Optional[datetime],
) -> dict:
    """
    ✅ 危険帯分析SSOT（read-only）
    - OutcomeLog を唯一の真実として、deadline の JST曜日×時間帯 で missed率を集計
    - UIで「落ちやすい締切時間」を出すための集計
    """
    q = db.query(TaskOutcomeLog).filter(TaskOutcomeLog.user_id == user_id)

    if from_deadline is not None:
        q = q.filter(TaskOutcomeLog.deadline >= from_deadline)
    if to_deadline is not None:
        q = q.filter(TaskOutcomeLog.deadline <= to_deadline)

    logs = q.order_by(TaskOutcomeLog.deadline.asc()).all() or []

    agg: dict[tuple[int, int], dict[str, int]] = {}  # (dow, hour) -> counts
    jst = ZoneInfo("Asia/Tokyo")

    for log in logs:
        d = log.deadline.astimezone(jst)
        key = (int(d.weekday()), int(d.hour))
        if key not in agg:
            agg[key] = {"total": 0, "missed": 0}
        agg[key]["total"] += 1
        if log.outcome != "done":
            agg[key]["missed"] += 1

    items: list[dict] = []
    for (dow, hour), c in agg.items():
        total = c["total"]
        missed = c["missed"]
        missed_rate = (missed / total) if total > 0 else 0.0
        items.append(
            {
                "deadline_dow_jst": dow,   # 0=Mon..6
                "deadline_hour_jst": hour, # 0..23
                "total": total,
                "missed": missed,
                "missed_rate": round(missed_rate, 4),
            }
        )

    # ✅ 決定的ソート（UI/監査/テスト向け）
    items.sort(key=lambda x: (-x["missed_rate"], -x["missed"], -x["total"], x["deadline_dow_jst"], x["deadline_hour_jst"]))

    return {
        "range": {
            "timezone": "Asia/Tokyo",
            "from": from_deadline,
            "to": to_deadline,
        },
        "items": items,
    }
