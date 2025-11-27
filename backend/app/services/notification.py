# app/services/notification.py

from datetime import datetime, timedelta, date, time
from typing import List

from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.task import Task
from app.models.task_notification_log import TaskNotificationLog


# ================================
# 共通ヘルパー
# ================================

def has_notification_been_sent(
    db: Session,
    user_id: int,
    task_id: int,
    offset_hours: int,
) -> bool:
    """
    すでにこの task に対して、この offset_hours の通知が送られているか
    """
    return (
        db.query(TaskNotificationLog)
        .filter(
            TaskNotificationLog.user_id == user_id,
            TaskNotificationLog.task_id == task_id,
            TaskNotificationLog.offset_hours == offset_hours,
        )
        .first()
        is not None
    )


def mark_notification_as_sent(
    db: Session,
    user_id: int,
    task_id: int,
    offset_hours: int,
) -> None:
    """
    通知済みとしてログに保存
    """
    log = TaskNotificationLog(
        user_id=user_id,
        task_id=task_id,
        offset_hours=offset_hours,
        sent_at=datetime.now(),
    )
    db.add(log)
    db.commit()


# ================================
# 3時間前通知用
# ================================

def get_tasks_due_in_hours(
    db: Session,
    user_id: int,
    hours: int,
) -> List[Task]:
    """
    【例】3時間前通知用（毎時実行前提）

    - 「締切までの残り時間」が hours ±0.5時間 のタスクを拾う
      例: hours=3 の場合 → 2.5〜3.5時間の間
    - is_done = False
    - まだその hours の通知が送られていないものだけ
    """

    now = datetime.now()

    # とりあえず「今から hours+1時間後まで」のタスクをざっくり取る
    window_end = now + timedelta(hours=hours + 1)

    candidates = (
        db.query(Task)
        .filter(
            Task.user_id == user_id,
            Task.is_done == False,  # noqa: E712
            Task.deadline >= now,
            Task.deadline <= window_end,
        )
        .all()
    )

    result: List[Task] = []
    for task in candidates:
        # 締切までの残り時間（時間単位）
        diff_hours = (task.deadline - now).total_seconds() / 3600.0

        # ざっくり hours ±0.5時間の範囲を「hours時間前」とみなす
        if (hours - 0.5) <= diff_hours <= (hours + 0.5):
            if not has_notification_been_sent(db, user_id, task.id, hours):
                result.append(task)

    return result


# ================================
# 当日朝（8:00）通知用
# ================================

def get_tasks_due_today_morning(
    db: Session,
    user_id: int,
) -> List[Task]:
    """
    【当日朝8:00通知用】

    - 今日が締切
    - is_done = False
    - まだ当日朝通知(0)が送られていないもの
    """

    today = date.today()

    start_dt = datetime.combine(today, datetime.min.time())
    end_dt = datetime.combine(today, datetime.max.time())

    tasks = (
        db.query(Task)
        .filter(
            Task.user_id == user_id,
            Task.is_done == False,  # noqa: E712
            Task.deadline >= start_dt,
            Task.deadline <= end_dt,
        )
        .all()
    )

    # すでに朝通知済みのものを除外
    result: List[Task] = []
    for task in tasks:
        if not has_notification_been_sent(db, user_id, task.id, 0):
            result.append(task)

    return result
