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

def deadline_jst_effective(dt: datetime) -> datetime:
    """
    フロントの 24:00 ロジックと揃える補正。
    JST で 00:00:00 の締切は「前日扱い」にする。
    """
    deadline_utc = to_utc(dt)
    jst_dt = deadline_utc.astimezone(JST)

    if jst_dt.hour == 0 and jst_dt.minute == 0 and jst_dt.second == 0:
        return jst_dt - timedelta(days=1)

    return jst_dt

def is_notification_candidate(
    task: Task,
    weekly_is_active: bool | None,
    now_utc: datetime,
) -> bool:
    """
    ✅ 通知対象の共通判定（集約）

    - 完了タスクは除外
    - should_notify が False なら除外（None は True 扱い）
    - weekly由来ならテンプレが active のときだけ（幽霊通知止血）
    - 24:00補正込みの締切が「過去」なら除外
    """
    # ① 完了は除外
    if task.is_done:
        return False

    # ② should_notify は None を True 扱いにする
    if task.should_notify is False:
        return False

    # ③ weekly由来なら active のときだけ
    if task.weekly_task_id is not None:
        if weekly_is_active is not True:
            return False

    # ④ 24:00補正込みで「過去締切」は除外
    now_jst = now_utc.astimezone(JST)
    effective_deadline_jst = deadline_jst_effective(task.deadline)
    if effective_deadline_jst < now_jst:
        return False

    return True

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
        db.query(Task, WeeklyTask.is_active)
        .outerjoin(WeeklyTask, Task.weekly_task_id == WeeklyTask.id)
        .filter(
            Task.user_id == user_id,
            Task.is_done == False,  # noqa: E712
            or_(
                Task.should_notify == True,
                Task.should_notify.is_(None),
            ),
        )
        .all()
    )

    result: List[Task] = []

    for task, weekly_is_active in candidates:
        if not is_notification_candidate(task, weekly_is_active, now_utc):
            continue

        # ✅ 24:00補正後の締切を基準に diff を計算（将来事故りにくい）
        effective_deadline_jst = deadline_jst_effective(task.deadline)
        effective_deadline_utc = effective_deadline_jst.astimezone(timezone.utc)
        diff_hours = (effective_deadline_utc - now_utc).total_seconds() / 3600.0

        print(
            "  task:", task.title,
            "deadline(JST):", effective_deadline_jst,
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
    now_jst = now_utc.astimezone(JST)
    start_jst = datetime.combine(today_jst, time(0, 0, 0, tzinfo=JST))
    end_jst = datetime.combine(today_jst, time(23, 59, 59, tzinfo=JST))

    candidates = (
        db.query(Task, WeeklyTask.is_active)
        .outerjoin(WeeklyTask, Task.weekly_task_id == WeeklyTask.id)
        .filter(
            Task.user_id == user_id,
            Task.is_done == False,  # noqa: E712
            or_(
                Task.should_notify == True,
                Task.should_notify.is_(None),
            ),
        )
        .all()
    )
    result: List[Task] = []

    for task, weekly_is_active in candidates:
        if not is_notification_candidate(task, weekly_is_active, now_utc):
            continue

        effective_deadline_jst = deadline_jst_effective(task.deadline)

        if start_jst <= effective_deadline_jst <= end_jst:
            if not has_notification_been_sent(db, user_id, task.id, 0):
                result.append(task)
    return result

from dataclasses import dataclass
from typing import Dict, Tuple

@dataclass
class NotificationCandidates:
    due_in_hours: Dict[int, List[Task]]   # offset_hours -> tasks
    morning: List[Task]                   # 朝通知タスク
    debug: Dict[str, int]                 # 数だけ（ログ用）

def collect_notification_candidates(
    db: Session,
    user_id: int,
    offsets_hours: List[int],
) -> NotificationCandidates:
    """
    ✅ 通知対象の判定を集約して返す（送信はしない）
    - offsets_hours: 例 [3,6] など
    - due_in_hours は offsetごとに Task の配列を返す
    - morning は朝通知の配列を返す
    """
    normalized_offsets: List[int] = []
    for x in offsets_hours or []:
        try:
            h = int(x)
        except (TypeError, ValueError):
            continue
        if h > 0:
            normalized_offsets.append(h)

    due_map: Dict[int, List[Task]] = {}
    total_due = 0

    for h in normalized_offsets:
        tasks = get_tasks_due_in_hours(db, user_id=user_id, hours=h)
        # get_tasks_due_in_hours は「そのoffsetの窓に入った」taskを返す設計なので、
        # ここでは h キーに寄せて格納する（overrideがある場合は今後改善余地あり）
        due_map[h] = tasks
        total_due += len(tasks)

    morning_tasks = get_tasks_due_today_morning(db, user_id=user_id)

    return NotificationCandidates(
        due_in_hours=due_map,
        morning=morning_tasks,
        debug={
            "offsets_count": len(normalized_offsets),
            "due_total": total_due,
            "morning_total": len(morning_tasks),
        },
    )
