# app/services/notification.py

from datetime import datetime, timedelta, date, time, timezone
from typing import List
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.models.task import Task
from app.models.task_notification_log import TaskNotificationLog
from app.models.task_notification_override import TaskNotificationOverride
from app.models.weekly_task import WeeklyTask

JST = timezone(timedelta(hours=9))

# ================================
# UTC変換ヘルパー（最重要）
# ================================

def to_utc(dt: datetime) -> datetime:
    """
    DBのdatetimeをUTCに正規化するヘルパー。

    - tzinfo が無い（naive）の場合は「JSTとして保存されている」とみなして
      JSTを付けてからUTCに変換
    - tzinfo が付いている場合は、そのタイムゾーンからUTCに変換
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=JST).astimezone(timezone.utc)
    return dt.astimezone(timezone.utc)

# ================================
# 共通ヘルパー
# ================================

def has_notification_been_sent(
    db: Session,
    user_id: int,
    task_id: int,
    offset_hours: int,
) -> bool:
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
    ✅ 通知ログは UTC で保存する
    """
    log = TaskNotificationLog(
        user_id=user_id,
        task_id=task_id,
        offset_hours=offset_hours,
        sent_at=datetime.now(timezone.utc),  # ← ★ UTCに変更
    )
    db.add(log)
    db.commit()


# ================================
# 3時間前通知用（内部UTC）
# ================================

def get_tasks_due_in_hours(
    db: Session,
    user_id: int,
    hours: int,
) -> List[Task]:
    """
    【例】3時間前通知用（毎時実行前提）

    - 内部はUTCで計算
    - 表示・ログだけJSTに変換
    - is_done = False
    - まだその hours の通知が送られていないものだけ
    """

    now_utc = datetime.now(timezone.utc)

    print("=== get_tasks_due_in_hours debug ===")
    print("  now_utc:", now_utc)
    print("  now_jst:", now_utc.astimezone(JST))
    print("  target hours:", hours)

    candidates = (
        db.query(Task)
        .outerjoin(WeeklyTask, Task.weekly_task_id == WeeklyTask.id)
        .filter(
            Task.user_id == user_id,
            Task.is_done == False,  # noqa: E712
            or_(
                Task.should_notify == True,
                Task.should_notify.is_(None),
            ),
            # ✅ weekly由来ならテンプレが生きてるものだけ通知（幽霊通知の止血）
            or_(
                Task.weekly_task_id.is_(None),   # 通常タスク
                WeeklyTask.is_active == True,    # weekly由来でも active のみ
            ),
        )
        .all()
    )

    result: List[Task] = []

    for task in candidates:
        deadline_utc = to_utc(task.deadline)
        deadline_jst = deadline_utc.astimezone(JST)

        diff_hours = (deadline_utc - now_utc).total_seconds() / 3600.0

        print(
            "  task:", task.title,
            "deadline(JST):", deadline_jst,
            "diff_hours:", diff_hours,
            "is_done:", task.is_done,
        )

        # --- 🔔 タスクごとの通知オーバーライド取得 ---
        override = (
            db.query(TaskNotificationOverride)
            .filter(
                TaskNotificationOverride.user_id == user_id,
                TaskNotificationOverride.task_id == task.id,
            )
            .first()
        )

        if override and override.reminder_offsets_hours is not None:
            effective_offsets = override.reminder_offsets_hours
        else:
            effective_offsets = [hours]

        for offset in effective_offsets:
            if (offset - 0.5) <= diff_hours <= (offset + 0.5):
                if not has_notification_been_sent(db, user_id, task.id, offset):
                    print("   → このタスクが通知対象！", task.title, f"({offset}時間前)")
                    result.append(task)

    print("=== get_tasks_due_in_hours result count:", len(result), "===\n")
    return result


# ================================
# 当日朝通知用（内部UTC・判定はJST）
# ================================

def get_tasks_due_today_morning(
    db: Session,
    user_id: int,
) -> List[Task]:
    """
    ✅ 内部UTC、判定はJSTの「今日」
    """

    now_utc = datetime.now(timezone.utc)
    today_jst = now_utc.astimezone(JST).date()

    start_jst = datetime.combine(today_jst, time(0, 0, 0, tzinfo=JST))
    end_jst = datetime.combine(today_jst, time(23, 59, 59, tzinfo=JST))

    candidates = (
        db.query(Task)
        .outerjoin(WeeklyTask, Task.weekly_task_id == WeeklyTask.id)
        .filter(
            Task.user_id == user_id,
            Task.is_done == False,  # noqa: E712
            or_(
                Task.should_notify == True,
                Task.should_notify.is_(None),
            ),
            or_(
            Task.weekly_task_id.is_(None),
            WeeklyTask.is_active == True,
            ),
        )
        .all()
    )

    result: List[Task] = []

    for task in candidates:
        deadline_jst = to_utc(task.deadline).astimezone(JST)

        if start_jst <= deadline_jst <= end_jst:
            if not has_notification_been_sent(db, user_id, task.id, 0):
                result.append(task)

    return result
