# app/services/notification.py

from datetime import datetime, timedelta, date, time, timezone

from typing import List

from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.models.task import Task
from app.models.task_notification_log import TaskNotificationLog

JST = timezone(timedelta(hours=9))

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
        sent_at=datetime.now(JST),
    )


    db.add(log)
    db.commit()


# ================================
# 3時間前通知用
# ================================

# backend/app/services/notification.py

def get_tasks_due_in_hours(
    db: Session,
    user_id: int,
    hours: int,
) -> List[Task]:
    """
    【例】3時間前通知用（毎時実行前提）

    - 日本時間(JST)で「締切までの残り時間」が hours ±0.5時間 のタスクを拾う
    - is_done = False
    - まだその hours の通知が送られていないものだけ
    """

    now_jst = datetime.now(JST)

    print("=== get_tasks_due_in_hours debug ===")
    print("  now_jst:", now_jst)
    print("  target hours:", hours)

    # ユーザーの未完了タスクを全部取得
    candidates = (
        db.query(Task)
        .filter(
            Task.user_id == user_id,
            Task.is_done == False,  # noqa: E712
        )
        .all()
    )

    result: List[Task] = []

    for task in candidates:
        deadline = task.deadline

        # DB側にタイムゾーンが付いてない場合は「JSTとして扱う」
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=JST)

        diff_hours = (deadline - now_jst).total_seconds() / 3600.0

        # ★ 各タスクごとのデバッグ
        print(
            "  task:", task.title,
            "deadline(JST):", deadline,
            "diff_hours:", diff_hours,
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

    - 日本時間で「今日」が締切
    - is_done = False
    - まだ当日朝通知(0)が送られていないもの
    """
    today_jst = datetime.now(JST).date()

    start_dt = datetime.combine(today_jst, time(0, 0, 0, tzinfo=JST))
    end_dt = datetime.combine(today_jst, time(23, 59, 59, tzinfo=JST))

    # ユーザーの未完了タスクを全部取得
    candidates = (
        db.query(Task)
        .filter(
            Task.user_id == user_id,
            Task.is_done == False,  # noqa: E712
        )
        .all()
    )

    result: List[Task] = []
    for task in candidates:
        deadline = task.deadline
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=JST)

        if start_dt <= deadline <= end_dt:
            if not has_notification_been_sent(db, user_id, task.id, 0):
                result.append(task)

    return result

