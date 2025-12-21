# app/services/notification.py

from datetime import datetime, timedelta, date, time, timezone
from typing import List, Dict
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

def deadline_label_date_jst(dt: datetime) -> date:
    """
    ✅ UIの「24:xx」表記に合わせた“日付ラベル”を返す（瞬間はズラさない）
    - JST で hour==0（00:xx）は「前日扱い」（= 24:xx 表記）
    """
    jst_dt = to_utc(dt).astimezone(JST)
    label = jst_dt.date()
    if jst_dt.hour == 0:
        label = label - timedelta(days=1)
    return label


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
    deadline_utc = to_utc(task.deadline)
    if deadline_utc < now_utc:
        return False
    return True

def has_notification_been_sent(
    db: Session,
    user_id: int,
    task_id: int,
    deadline_utc: datetime,
    offset_hours: int,
) -> bool:
    return (
        db.query(TaskNotificationLog)
        .filter(
            TaskNotificationLog.user_id == user_id,
            TaskNotificationLog.task_id == task_id,
            TaskNotificationLog.deadline == deadline_utc,
            TaskNotificationLog.offset_hours == offset_hours,
        )
        .first()
        is not None
    )

def mark_notification_as_sent(
    db: Session,
    user_id: int,
    task_id: int,
    deadline_utc: datetime,
    offset_hours: int,
) -> None:
    log = TaskNotificationLog(
        user_id=user_id,
        task_id=task_id,
        deadline=deadline_utc,  # ✅ 追加
        offset_hours=offset_hours,
        sent_at=datetime.now(timezone.utc),
    )
    db.add(log)
    db.commit()


from collections import defaultdict
from typing import DefaultDict

def get_tasks_due_in_offsets(
    db: Session,
    user_id: int,
    offsets: List[int],
) -> Dict[int, List[Task]]:
    """
    ✅ 1回のDB取得 + 1回の走査で、offsetごとの通知対象を返す
    - overrides.reminder_offsets_hours があればそれを優先
    - overrides が無ければ引数 offsets を採用
    """
    now_utc = datetime.now(timezone.utc)

    # offsets を正規化
    normalized: List[int] = []
    for x in offsets or []:
        try:
            h = int(x)
        except (TypeError, ValueError):
            continue
        if h > 0:
            normalized.append(h)

    due_map: DefaultDict[int, List[Task]] = defaultdict(list)
    if not normalized:
        return dict(due_map)

    # candidates を一括取得（weekly active だけ join）
    candidates = (
        db.query(Task, WeeklyTask.is_active)
        .outerjoin(WeeklyTask, Task.weekly_task_id == WeeklyTask.id)
        .filter(Task.user_id == user_id)
        .all()
    )

    for task, weekly_is_active in candidates:
        # ✅ 通知対象の共通判定（唯一の真実に寄せる）
        if not is_notification_candidate(task, weekly_is_active, now_utc):
            continue

        deadline_utc = to_utc(task.deadline)
        diff_hours = (deadline_utc - now_utc).total_seconds() / 3600.0

        # override の取得（※ここはまだ1件ずつ。次の最適化でJOINに変えられる）
        override = (
            db.query(TaskNotificationOverride)
            .filter(
                TaskNotificationOverride.user_id == user_id,
                TaskNotificationOverride.task_id == task.id,
            )
            .first()
        )

        # override があればそれを優先、なければグローバル offsets
        effective_offsets = None
        if override and override.reminder_offsets_hours is not None:
            effective_offsets = override.reminder_offsets_hours
        else:
            effective_offsets = normalized

        for offset in effective_offsets or []:
            try:
                h = int(offset)
            except (TypeError, ValueError):
                continue
            if h <= 0:
                continue

            if (h - 0.5) <= diff_hours <= (h + 0.5):
                if not has_notification_been_sent(
                    db,
                    user_id,
                    task.id,
                    deadline_utc,
                    h,
                ):
                    due_map[h].append(task)
    return dict(due_map)


# ================================
# 3時間前通知用（内部UTC）
# ================================

def get_tasks_due_in_hours(
    db: Session,
    user_id: int,
    hours: int,
) -> List[Task]:
    """
    互換用ラッパー。
    実際の通知判定は get_tasks_due_in_offsets に一本化する。
    """
    due_map = get_tasks_due_in_offsets(
        db,
        user_id=user_id,
        offsets=[hours],
    )
    return due_map.get(hours, [])



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

        label_date = deadline_label_date_jst(task.deadline)
        deadline_utc = to_utc(task.deadline)

        if label_date == today_jst:
            if not has_notification_been_sent(
                db,
                user_id,
                task.id,
                deadline_utc,
                0,
            ):
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
    # offsets を正規化
    normalized_offsets: List[int] = []
    for x in offsets_hours or []:
        try:
            h = int(x)
        except (TypeError, ValueError):
            continue
        if h > 0:
            normalized_offsets.append(h)

    # ✅ ここが変更点：1回の走査で offset → tasks を作る
    due_map: Dict[int, List[Task]] = get_tasks_due_in_offsets(
        db,
        user_id=user_id,
        offsets=normalized_offsets,
    )

    total_due = sum(len(v) for v in due_map.values())

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
