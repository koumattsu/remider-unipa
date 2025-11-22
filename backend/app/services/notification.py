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
    【例】3時間前通知用
    - 現在時刻 + 3時間 を中心に、±5分のものを取得
    - 未完了 (is_done = False)
    - まだ通知していないものだけ
    """

    now = datetime.now()
    target_time = now + timedelta(hours=hours)

    # 少し幅を持たせる（cronの実行ズレ対策）
    start_dt = target_time - timedelta(minutes=5)
    end_dt = target_time + timedelta(minutes=5)

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

    # すでに通知済みのものを除外
    result: List[Task] = []
    for task in tasks:
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
