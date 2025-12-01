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

# app/services/notification.py

# backend/app/services/notification.py

def get_tasks_due_in_hours(
    db: Session,
    user_id: int,
    hours: int,
) -> List[Task]:
    """
    【例】3時間前通知用（毎時実行前提）

    - 「締切までの残り時間」が hours ±0.5時間 のタスクを拾う
    - is_done = False
    - 通知ONのタスクだけ (Task.should_notify == True)
    - まだその hours の通知が送られていないものだけ
    """

    now = datetime.now()
    window_end = now + timedelta(hours=hours + 1)

    # ★ デバッグログ（いつでも消してOK）
    print("=== get_tasks_due_in_hours debug ===")
    print("  now:", now)
    print("  target hours:", hours)
    print("  window_end:", window_end)

    candidates = (
        db.query(Task)
        .filter(
            Task.user_id == user_id,
            Task.is_done == False,       # noqa: E712
            Task.should_notify == True,  # 通知ONのタスクだけ
            Task.deadline >= now,
            Task.deadline <= window_end,
        )
        .all()
    )

    result: List[Task] = []

    for task in candidates:
        diff_hours = (task.deadline - now).total_seconds() / 3600.0

        # ★ 各タスクごとのデバッグ
        print(
            "  task:", task.title,
            "deadline:", task.deadline,
            "diff_hours:", diff_hours,
            "should_notify:", task.should_notify,
            "is_done:", task.is_done,
        )

        if (hours - 0.5) <= diff_hours <= (hours + 0.5):
            if not has_notification_been_sent(db, user_id, task.id, hours):
                print("   → このタスクが通知対象！", task.title)
                result.append(task)

    print("=== get_tasks_due_in_hours result count:", len(result), "===\n")
    return result


# ================================
# 当日朝（8:00）通知用
# ================================

# app/services/notification.py

def get_tasks_due_today_morning(
    db: Session,
    user_id: int,
) -> List[Task]:
    """
    【当日朝8:00通知用】

    - 今日が締切
    - is_done = False
    - ★ 通知ONのタスクだけ (Task.should_notify == True)
    - まだ当日朝通知(0)が送られていないもの
    """

    today = date.today()

    start_dt = datetime.combine(today, datetime.min.time())
    end_dt = datetime.combine(today, datetime.max.time())

    tasks = (
        db.query(Task)
        .filter(
            Task.user_id == user_id,
            Task.is_done == False,        # noqa: E712
            Task.should_notify == True,   # ★ 通知ONのタスクだけ
            Task.deadline >= start_dt,
            Task.deadline <= end_dt,
        )
        .all()
    )

    result: List[Task] = []
    for task in tasks:
        if not has_notification_been_sent(db, user_id, task.id, 0):
            result.append(task)

    return result
