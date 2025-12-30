# backend/app/services/outcome_analytics.py

from __future__ import annotations
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import Optional, Literal
from sqlalchemy.orm import Session
from app.models.task import Task
from app.models.task_outcome_log import TaskOutcomeLog
from app.models.outcome_feature_snapshot import OutcomeFeatureSnapshot
from app.models.suggested_action_applied_event import SuggestedActionAppliedEvent

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

def build_action_effectiveness(
    db: Session,
    *,
    user_id: int,
    from_applied_at: Optional[datetime],
    to_applied_at: Optional[datetime],
    window_days: int,
    min_total: int,
    limit_events: int,
) -> dict:
    """
    ✅ SuggestedAction の効果を OutcomeLog（SSOT）で評価する（read-only）
    - 介入ログ: SuggestedActionAppliedEvent（資産）
    - 結果: TaskOutcomeLog（唯一の真実）
    - v0: reason_keys 等の「提案ロジック」には触れない（推測しない）

    評価方法（v0）:
    - event.applied_at を境に
      before: [applied_at - window_days, applied_at)
      after : [applied_at, applied_at + window_days)
    - 指標: missed_rate_after - missed_rate_before（負なら改善）
    - min_total: before/after の total が両方 min_total 以上のときだけ measured とする
    """
    # 1) 介入イベント（資産）
    q = db.query(SuggestedActionAppliedEvent).filter(
        SuggestedActionAppliedEvent.user_id == user_id
    )
    if from_applied_at is not None:
        q = q.filter(SuggestedActionAppliedEvent.applied_at >= from_applied_at)
    if to_applied_at is not None:
        q = q.filter(SuggestedActionAppliedEvent.applied_at <= to_applied_at)

    events = (
        q.order_by(SuggestedActionAppliedEvent.applied_at.desc())
        .limit(limit_events)
        .all()
    ) or []

    if not events:
        return {
            "range": {
                "timezone": "Asia/Tokyo",
                "from": from_applied_at,
                "to": to_applied_at,
                "window_days": window_days,
                "min_total": min_total,
                "limit_events": limit_events,
            },
            "items": [],
        }

    # 2) 必要な OutcomeLog をまとめて取得（JOINせずに 2クエリ + python 集計）
    w = timedelta(days=window_days)
    min_deadline = min(e.applied_at for e in events) - w
    max_deadline = max(e.applied_at for e in events) + w

    oq = db.query(TaskOutcomeLog).filter(TaskOutcomeLog.user_id == user_id)
    oq = oq.filter(TaskOutcomeLog.deadline >= min_deadline)
    oq = oq.filter(TaskOutcomeLog.deadline <= max_deadline)
    logs = oq.order_by(TaskOutcomeLog.deadline.asc()).all() or []

    # 3) action_id ごとの集計
    # action_id -> counters
    agg: dict[str, dict[str, float]] = {}
    for e in events:
        aid = e.action_id
        if aid not in agg:
            agg[aid] = {
                "applied_count": 0,
                "measured_count": 0,
                "improved_count": 0,
                "sum_delta": 0.0,
            }
        agg[aid]["applied_count"] += 1

        before_start = e.applied_at - w
        before_end = e.applied_at
        after_start = e.applied_at
        after_end = e.applied_at + w

        b_total = b_missed = 0
        a_total = a_missed = 0

        # logs は数が大きくなりうるが、limit_events を上限として制御
        for l in logs:
            d = l.deadline
            if before_start <= d < before_end:
                b_total += 1
                if l.outcome != "done":
                    b_missed += 1
            elif after_start <= d < after_end:
                a_total += 1
                if l.outcome != "done":
                    a_missed += 1

        if b_total < min_total or a_total < min_total:
            # ✅ 評価不能（母数不足）でも applied_count は積む
            continue

        b_rate = (b_missed / b_total) if b_total > 0 else 0.0
        a_rate = (a_missed / a_total) if a_total > 0 else 0.0
        delta = a_rate - b_rate
        agg[aid]["measured_count"] += 1
        agg[aid]["sum_delta"] += delta
        if delta < 0:
            agg[aid]["improved_count"] += 1

    items: list[dict] = []
    for aid, c in agg.items():
        applied_count = int(c["applied_count"])
        measured_count = int(c["measured_count"])
        improved_count = int(c["improved_count"])
        improved_rate = (improved_count / measured_count) if measured_count > 0 else 0.0
        avg_delta = (c["sum_delta"] / measured_count) if measured_count > 0 else 0.0
        items.append(
            {
                "action_id": aid,
                "applied_count": applied_count,
                "measured_count": measured_count,
                "improved_count": improved_count,
                "improved_rate": round(improved_rate, 4),
                "avg_delta_missed_rate": round(avg_delta, 4),
            }
        )

    # ✅ 決定的ソート（監査/表示安定）
    items.sort(
        key=lambda x: (
            -x["measured_count"],
            -x["applied_count"],
            x["action_id"],
        )
    )

    return {
        "range": {
            "timezone": "Asia/Tokyo",
            "from": from_applied_at,
            "to": to_applied_at,
            "window_days": window_days,
            "min_total": min_total,
            "limit_events": limit_events,
        },
        "items": items,
    }

def build_action_effectiveness_by_feature(
    db: Session,
    *,
    user_id: int,
    feature_version: str,
    from_applied_at: Optional[datetime],
    to_applied_at: Optional[datetime],
    window_days: int,
    min_total: int,
    limit_events: int,
    limit_samples_per_event: int,
) -> dict:
    """
    ✅ action × feature の「効きやすさ」を返す（read-only）
    - SSOT: TaskOutcomeLog（前後比較は v0 と同じ）
    - 条件: applied_at 直前 window の OutcomeFeatureSnapshot（資産）
    - JOINせずに 2クエリ + map
    - v1: 提案ロジック(reason_keys等)には触れない
    """
    # 1) 介入イベント
    q = db.query(SuggestedActionAppliedEvent).filter(
        SuggestedActionAppliedEvent.user_id == user_id
    )
    if from_applied_at is not None:
        q = q.filter(SuggestedActionAppliedEvent.applied_at >= from_applied_at)
    if to_applied_at is not None:
        q = q.filter(SuggestedActionAppliedEvent.applied_at <= to_applied_at)

    events = (
        q.order_by(SuggestedActionAppliedEvent.applied_at.desc())
        .limit(limit_events)
        .all()
    ) or []

    if not events:
        return {
            "range": {
                "timezone": "Asia/Tokyo",
                "version": feature_version,
                "from": from_applied_at,
                "to": to_applied_at,
                "window_days": window_days,
                "min_total": min_total,
                "limit_events": limit_events,
                "limit_samples_per_event": limit_samples_per_event,
            },
            "items": [],
        }

    w = timedelta(days=window_days)

    # 2) 必要な OutcomeLog をまとめて取得（before/after 両方）
    min_deadline = min(e.applied_at for e in events) - w
    max_deadline = max(e.applied_at for e in events) + w

    oq = db.query(TaskOutcomeLog).filter(TaskOutcomeLog.user_id == user_id)
    oq = oq.filter(TaskOutcomeLog.deadline >= min_deadline)
    oq = oq.filter(TaskOutcomeLog.deadline <= max_deadline)
    logs = oq.order_by(TaskOutcomeLog.deadline.asc()).all() or []

    if not logs:
        return {
            "range": {
                "timezone": "Asia/Tokyo",
                "version": feature_version,
                "from": from_applied_at,
                "to": to_applied_at,
                "window_days": window_days,
                "min_total": min_total,
                "limit_events": limit_events,
                "limit_samples_per_event": limit_samples_per_event,
            },
            "items": [],
        }

    # 3) FeatureSnapshot をまとめて取得（同じ範囲・指定version）
    task_ids = [l.task_id for l in logs]
    deadlines = [l.deadline for l in logs]
    fq = (
        db.query(OutcomeFeatureSnapshot)
        .filter(OutcomeFeatureSnapshot.user_id == user_id)
        .filter(OutcomeFeatureSnapshot.feature_version == feature_version)
        .filter(OutcomeFeatureSnapshot.task_id.in_(task_ids))
        .filter(OutcomeFeatureSnapshot.deadline.in_(deadlines))
    )
    snaps = fq.all() or []
    snap_map: dict[tuple[int, datetime], OutcomeFeatureSnapshot] = {
        (s.task_id, s.deadline): s for s in snaps
    }

    excluded_keys = {"course_hash"}  # v1: 爆発回避（既存方針に合わせる）

    # 4) 集計: (action_id, feature_key, feature_value) -> counts
    # 値は "見かけたイベント数" ベース（サンプル数で水増ししない）
    agg: dict[tuple[str, str, str], dict[str, int]] = {}

    for e in events:
        aid = e.action_id
        before_start = e.applied_at - w
        before_end = e.applied_at
        after_start = e.applied_at
        after_end = e.applied_at + w

        # v0 と同じ: 前後の missed_rate を計算
        b_total = b_missed = 0
        a_total = a_missed = 0
        for l in logs:
            d = l.deadline
            if before_start <= d < before_end:
                b_total += 1
                if l.outcome != "done":
                    b_missed += 1
            elif after_start <= d < after_end:
                a_total += 1
                if l.outcome != "done":
                    a_missed += 1

        if b_total < min_total or a_total < min_total:
            continue

        b_rate = (b_missed / b_total) if b_total > 0 else 0.0
        a_rate = (a_missed / a_total) if a_total > 0 else 0.0
        improved = (a_rate - b_rate) < 0

        # “条件”として、before window の FeatureSnapshot を最大 N 件だけサンプル
        #  - 直近を優先（deadline降順）
        before_logs = [l for l in logs if before_start <= l.deadline < before_end]
        before_logs.sort(key=lambda x: x.deadline, reverse=True)
        before_logs = before_logs[: max(1, int(limit_samples_per_event))]

        # イベント内で同じ feature 値を何度も数えない（イベント単位で重複排除）
        seen: set[tuple[str, str]] = set()
        for l in before_logs:
            s = snap_map.get((l.task_id, l.deadline))
            if s is None:
                continue
            features = s.features or {}
            for k, v in features.items():
                if k in excluded_keys:
                    continue
                vv = str(v).lower() if isinstance(v, bool) else str(v)
                key2 = (k, vv)
                if key2 in seen:
                    continue
                seen.add(key2)

                agg_key = (aid, k, vv)
                if agg_key not in agg:
                    agg[agg_key] = {"total_events": 0, "improved_events": 0}
                agg[agg_key]["total_events"] += 1
                if improved:
                    agg[agg_key]["improved_events"] += 1

    items: list[dict] = []
    for (aid, k, vv), c in agg.items():
        total_events = c["total_events"]
        improved_events = c["improved_events"]
        improved_rate = (improved_events / total_events) if total_events > 0 else 0.0
        items.append(
            {
                "action_id": aid,
                "feature_key": k,
                "feature_value": vv,
                "total_events": total_events,
                "improved_events": improved_events,
                "improved_rate": round(improved_rate, 4),
            }
        )

    # ✅ 決定的ソート（監査/表示安定）
    items.sort(
        key=lambda x: (
            -x["improved_rate"],
            -x["improved_events"],
            -x["total_events"],
            x["action_id"],
            x["feature_key"],
            x["feature_value"],
        )
    )

    return {
        "range": {
            "timezone": "Asia/Tokyo",
            "version": feature_version,
            "from": from_applied_at,
            "to": to_applied_at,
            "window_days": window_days,
            "min_total": min_total,
            "limit_events": limit_events,
            "limit_samples_per_event": limit_samples_per_event,
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

def build_outcome_missed_by_feature(
    db: Session,
    *,
    user_id: int,
    feature_version: str,
    from_deadline: Optional[datetime],
    to_deadline: Optional[datetime],
    limit: int,
) -> dict:
    """
    ✅ feature別 missed率 SSOT（read-only）
    - OutcomeLog（真実）× FeatureSnapshot（資産）を (task_id, deadline) map で束ねる
    - JOINしない（事故回避 / FakeSession耐性）
    - course_hash はカテゴリ爆発するのでデフォルト除外（必要なら別APIで）
    """
    # 1) OutcomeLog（母集団）
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

    # 2) FeatureSnapshot（同じ (task_id, deadline) の v を取る）
    task_ids = [l.task_id for l in logs]
    deadlines = [l.deadline for l in logs]

    fq = (
        db.query(OutcomeFeatureSnapshot)
        .filter(OutcomeFeatureSnapshot.user_id == user_id)
        .filter(OutcomeFeatureSnapshot.feature_version == feature_version)
        .filter(OutcomeFeatureSnapshot.task_id.in_(task_ids))
        .filter(OutcomeFeatureSnapshot.deadline.in_(deadlines))
    )
    if from_deadline is not None:
        fq = fq.filter(OutcomeFeatureSnapshot.deadline >= from_deadline)
    if to_deadline is not None:
        fq = fq.filter(OutcomeFeatureSnapshot.deadline <= to_deadline)

    snaps = fq.all() or []
    snap_map: dict[tuple[int, datetime], OutcomeFeatureSnapshot] = {
        (s.task_id, s.deadline): s for s in snaps
    }

    # 3) 集計
    #    key -> value -> counts
    agg: dict[str, dict[str, dict[str, int]]] = {}

    excluded_keys = {"course_hash"}  # ✅ カテゴリ爆発を避ける

    for l in logs:
        s = snap_map.get((l.task_id, l.deadline))
        if s is None:
            # ✅ 特徴量が無いものは feature分析から除外
            continue

        features = s.features or {}
        for k, v in features.items():
            if k in excluded_keys:
                continue
            vv = str(v).lower() if isinstance(v, bool) else str(v)

            if k not in agg:
                agg[k] = {}
            if vv not in agg[k]:
                agg[k][vv] = {"total": 0, "missed": 0}

            agg[k][vv]["total"] += 1
            if l.outcome != "done":
                agg[k][vv]["missed"] += 1

    items: list[dict] = []
    for k, by_val in agg.items():
        for vv, c in by_val.items():
            total = c["total"]
            missed = c["missed"]
            missed_rate = (missed / total) if total > 0 else 0.0
            items.append(
                {
                    "feature_key": k,
                    "feature_value": vv,
                    "total": total,
                    "missed": missed,
                    "missed_rate": round(missed_rate, 4),
                }
            )

    # ✅ 決定的ソート（監査/テスト/表示安定）
    items.sort(key=lambda x: (-x["missed_rate"], -x["missed"], -x["total"], x["feature_key"], x["feature_value"]))

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

def build_outcome_course_x_feature(
    db: Session,
    *,
    user_id: int,
    feature_version: str,
    from_deadline: Optional[datetime],
    to_deadline: Optional[datetime],
    limit: int,
    course_hash: Optional[str] = None,
) -> dict:
    """
    ✅ course × feature の missed率（read-only）
    - OutcomeLog（真実）× FeatureSnapshot（資産）を (task_id, deadline) map で束ねる
    - JOINしない（事故回避 / FakeSession耐性）
    - course_hash は features["course_hash"] を軸にする（v1想定）
    """
    # 1) OutcomeLog（母集団）
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
                "course_hash": course_hash,
            },
            "items": [],
        }

    # 2) FeatureSnapshot
    task_ids = [l.task_id for l in logs]
    deadlines = [l.deadline for l in logs]

    fq = (
        db.query(OutcomeFeatureSnapshot)
        .filter(OutcomeFeatureSnapshot.user_id == user_id)
        .filter(OutcomeFeatureSnapshot.feature_version == feature_version)
        .filter(OutcomeFeatureSnapshot.task_id.in_(task_ids))
        .filter(OutcomeFeatureSnapshot.deadline.in_(deadlines))
    )
    if from_deadline is not None:
        fq = fq.filter(OutcomeFeatureSnapshot.deadline >= from_deadline)
    if to_deadline is not None:
        fq = fq.filter(OutcomeFeatureSnapshot.deadline <= to_deadline)

    snaps = fq.all() or []
    snap_map: dict[tuple[int, datetime], OutcomeFeatureSnapshot] = {
        (s.task_id, s.deadline): s for s in snaps
    }

    # 3) 集計
    # course_hash -> feature_key -> feature_value -> counts
    agg: dict[str, dict[str, dict[str, dict[str, int]]]] = {}

    excluded_keys = {"course_hash"}  # ✅ course軸として使うので feature側からは除外

    for l in logs:
        s = snap_map.get((l.task_id, l.deadline))
        if s is None:
            continue

        features = s.features or {}
        ch = features.get("course_hash")
        if not ch:
            # ✅ course_hash がないスナップは cross から除外（仕様固定）
            continue
        ch = str(ch)
        if course_hash and ch != course_hash:
            continue

        if ch not in agg:
            agg[ch] = {}

        for k, v in features.items():
            if k in excluded_keys:
                continue
            vv = str(v).lower() if isinstance(v, bool) else str(v)

            if k not in agg[ch]:
                agg[ch][k] = {}
            if vv not in agg[ch][k]:
                agg[ch][k][vv] = {"total": 0, "missed": 0}

            agg[ch][k][vv]["total"] += 1
            if l.outcome != "done":
                agg[ch][k][vv]["missed"] += 1

    items: list[dict] = []
    for ch, by_key in agg.items():
        for k, by_val in by_key.items():
            for vv, c in by_val.items():
                total = c["total"]
                missed = c["missed"]
                missed_rate = (missed / total) if total > 0 else 0.0
                items.append(
                    {
                        "course_hash": ch,
                        "feature_key": k,
                        "feature_value": vv,
                        "total": total,
                        "missed": missed,
                        "missed_rate": round(missed_rate, 4),
                    }
                )

    # ✅ 決定的ソート（監査/テスト/表示安定）
    items.sort(
        key=lambda x: (
            -x["missed_rate"],
            -x["missed"],
            -x["total"],
            x["course_hash"],
            x["feature_key"],
            x["feature_value"],
        )
    )

    return {
        "range": {
            "timezone": "Asia/Tokyo",
            "version": feature_version,
            "from": from_deadline,
            "to": to_deadline,
            "limit": limit,
            "course_hash": course_hash,
        },
        "items": items,
    }
