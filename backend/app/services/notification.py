# app/services/notification.py

from datetime import datetime, timedelta, date, time, timezone
from typing import List, Dict
from sqlalchemy.orm import Session
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from app.models.task import Task
from app.models.task_notification_override import TaskNotificationOverride
from app.models.weekly_task import WeeklyTask
from app.models.task_notification_log import TaskNotificationLog
from app.services.notification_decision import NotificationDecision  # ✅ 追加
import logging
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)
JST = timezone(timedelta(hours=9))

# ✅ SSOT契約：朝通知は offset_hours=0 として扱う
MORNING_OFFSET_HOURS = 0

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

def try_mark_notification_as_sent(
    db: Session,
    user_id: int,
    task_id: int,
    deadline_utc: datetime,
    offset_hours: int,
    *,
    sent_at_utc: datetime,
    run_id: int | None = None,
) -> bool:
    # ✅ 送信前ロックは「このトランザクション内」で確保する（commitは呼び出し側でまとめて行う）
    # - ここで commit すると「ログだけ確定して InApp が残らない」欠落が起き得る
    # - SAVEPOINT + flush で一意制約チェックだけ行い、成功ならロック獲得
    try:
        with db.begin_nested():
            log = TaskNotificationLog(
                user_id=user_id,
                task_id=task_id,
                deadline_at_send=deadline_utc,
                offset_hours=offset_hours,
                run_id=run_id,
                sent_at=sent_at_utc,
            )
            db.add(log)
            db.flush()  # ✅ ここで unique 制約を評価させる
        return True
    except IntegrityError:
        # ✅ 既にロック済み（=二重送信防止）
        return False

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
    # ⓪ ソフトデリートは即除外（将来価値のため）
    if task.deleted_at is not None:
        return False
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

def decide_notification(
    *,
    task: Task,
    weekly_is_active: bool | None,
    now_utc: datetime,
    override: TaskNotificationOverride | None,
    base_offsets: List[int],
    offset_hours: int | None = None,
) -> NotificationDecision:
    """
    SSOT（Phase 1）：
    - 通知「候補」かどうかだけを判定する
    - DBロック・diff_hours 判定は含めない（最小diff）
    """

    # ⓪ ソフトデリート
    if task.deleted_at is not None:
        return NotificationDecision(False, "skipped:soft_deleted", [])

    # ① 完了
    if task.is_done:
        return NotificationDecision(False, "skipped:completed", [])

    # ② should_notify（None は True 扱い）
    if task.should_notify is False:
        return NotificationDecision(False, "skipped:task_notify_disabled", [])

    # ③ weekly active
    if task.weekly_task_id is not None:
        if weekly_is_active is not True:
            return NotificationDecision(False, "skipped:weekly_inactive", [])

    # ④ 締切が未来か（UTC）
    deadline_utc = to_utc(task.deadline)
    if deadline_utc < now_utc:
        return NotificationDecision(False, "skipped:deadline_passed", [])

    # ⑤ override（三値）
    # - offset_hours が 0（朝通知）の場合は [0] をベースに扱う
    effective_offsets = [0] if offset_hours == 0 else base_offsets

    if override:
        ro = override.reminder_offsets_hours
        if ro is None:
            # 継承：朝なら [0]、時間前なら base_offsets
            effective_offsets = [0] if offset_hours == 0 else base_offsets
        elif isinstance(ro, list) and len(ro) == 0:
            return NotificationDecision(False, "skipped:override_disabled", [])
        else:
            effective_offsets = ro

    # ✅ 朝通知（offset_hours=0）は Phase2（窓判定）に入れない
    # - “今日の朝に出す候補か” は get_tasks_due_today_morning() 側で label_date==today_jst で確定する
    if offset_hours == 0:
        return NotificationDecision(True, "candidate:morning", effective_offsets)

    # Phase 2（SSOT拡張）：
    if offset_hours is not None:
        try:
            h = int(offset_hours)
        except (TypeError, ValueError):
            return NotificationDecision(False, "skipped:invalid_offset", [])

        if h <= 0:
            return NotificationDecision(False, "skipped:invalid_offset", [])

        # このoffsetが有効か
        if h not in (effective_offsets or []):
            return NotificationDecision(False, "skipped:offset_not_enabled", [])

        diff_hours = (deadline_utc - now_utc).total_seconds() / 3600.0

        # 通知ウィンドウ判定（既存ロジックをSSOTに移管）
        if h == 1:
            # 90分前〜60分前
            if not (1.0 <= diff_hours <= 1.5):
                return NotificationDecision(False, "skipped:offset_window_outside", [])
        else:
            # ±30分
            if not ((h - 0.5) <= diff_hours <= (h + 0.5)):
                return NotificationDecision(False, "skipped:offset_window_outside", [])

        return NotificationDecision(True, "send:offset_hit", effective_offsets)

    # offset_hours 未指定の場合は「候補」だけ返す（Phase1のまま）
    return NotificationDecision(True, "candidate:offset_window", effective_offsets)

def decide_notification_and_lock(
    *,
    db: Session,
    user_id: int,
    run_id: int | None,
    task: Task,
    weekly_is_active: bool | None,
    now_utc: datetime,
    override: TaskNotificationOverride | None,
    base_offsets: List[int],
    offset_hours: int,
) -> NotificationDecision:
    """
    SSOT（Phase 3）：
    - decide_notification()（候補/override/window）を呼ぶ
    - should_send=True のときだけ try_mark_notification_as_sent() で送信前ロックを獲得する
    - ロック獲得できなければ skipped:already_locked
    """
    d = decide_notification(
        task=task,
        weekly_is_active=weekly_is_active,
        now_utc=now_utc,
        override=override,
        base_offsets=base_offsets,
        offset_hours=offset_hours,
    )
    if not d.should_send:
        return d

    # ✅ ロックは “送るべき” と判定できた場合のみ
    deadline_utc = to_utc(task.deadline)
    if not try_mark_notification_as_sent(
        db, user_id, task.id, deadline_utc, int(offset_hours),
        sent_at_utc=now_utc,
        run_id=run_id
    ):
        return NotificationDecision(False, "skipped:already_locked", d.effective_offsets)
    return d

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
            TaskNotificationLog.deadline_at_send == deadline_utc,
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
    raise RuntimeError(
        "mark_notification_as_sent is deprecated. "
        "Use try_mark_notification_as_sent() via SSOT instead."
    )
    # --- legacy code below (kept for reference; unreachable) ---
    # log = TaskNotificationLog(...)
    # db.add(log)
    # db.commit()

from collections import defaultdict
from typing import DefaultDict

def get_tasks_due_in_offsets(
    db: Session,
    user_id: int,
    offsets: List[int],
    *,
    now_utc: datetime,
    run_id: int | None = None,
    debug: Dict[str, int] | None = None,
) -> Dict[int, List[Task]]:
    """
    ✅ 1回のDB取得 + 1回の走査で、offsetごとの通知対象を返す
    - overrides.reminder_offsets_hours があればそれを優先
    - overrides が無ければ引数 offsets を採用
    """
    # ✅ now_utc は呼び出し元が必ず注入する（SSOT固定）

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
        .filter(Task.user_id == user_id, Task.deleted_at.is_(None),)
        .all()
    )

    # ✅ TZ観測（3時間前が拾えない原因を“事実”で潰す）
    # candidates は (Task, weekly_is_active) のタプルなので [0][0] が Task
    logger.info(
        "[TZ DEBUG] user_id=%s now_utc=%s now_jst=%s sample_deadline=%s candidates=%s offsets=%s",
        user_id,
        now_utc.isoformat(),
        now_utc.astimezone(ZoneInfo("Asia/Tokyo")).isoformat(),
        (to_utc(candidates[0][0].deadline).isoformat() if candidates else "NONE"),
        len(candidates),
        offsets,
    )

    for task, weekly_is_active in candidates:
        # override の取得（既存のまま）
        override = (
            db.query(TaskNotificationOverride)
            .filter(
                TaskNotificationOverride.user_id == user_id,
                TaskNotificationOverride.task_id == task.id,
            )
            .first()
        )

        decision = decide_notification(
            task=task,
            weekly_is_active=weekly_is_active,
            now_utc=now_utc,
            override=override,
            base_offsets=normalized,
        )
        if not decision.should_send:
            if debug is not None:
                k = f"decision.{decision.reason}"
                debug[k] = debug.get(k, 0) + 1
            logger.info(
                "[notify-skip] user_id=%s task_id=%s reason=%s",
                user_id, task.id, decision.reason
            )
            continue

        deadline_utc = to_utc(task.deadline)
        diff_hours = (deadline_utc - now_utc).total_seconds() / 3600.0
        # ✅ SSOT: effective_offsets は decide_notification() の結果のみを信頼する
        effective_offsets = decision.effective_offsets
        for offset in effective_offsets or []:
            try:
                h = int(offset)
            except (TypeError, ValueError):
                continue
            if h <= 0:
                continue

            offset_decision = decide_notification_and_lock(
                db=db,
                user_id=user_id,
                run_id=run_id,
                task=task,
                weekly_is_active=weekly_is_active,
                now_utc=now_utc,
                override=override,
                base_offsets=normalized,
                offset_hours=h,
            )

            if not offset_decision.should_send:
                if debug is not None:
                    k = f"decision.{offset_decision.reason}"
                    debug[k] = debug.get(k, 0) + 1
                logger.info(
                    "[due-skip] user_id=%s task_id=%s offset=%s reason=%s deadline_utc=%s diff_hours=%.3f",
                    user_id, task.id, h, offset_decision.reason, deadline_utc.isoformat(), diff_hours
                )
                continue

            logger.info(
                "[due-hit] user_id=%s task_id=%s offset=%s deadline_utc=%s diff_hours=%.3f",
                user_id, task.id, h, deadline_utc.isoformat(), diff_hours
            )
            if debug is not None:
                debug["decision.sent:offset_hit"] = debug.get("decision.sent:offset_hit", 0) + 1
                # ✅ 監査用：taskごとの reason は上書きせずカウント（曖昧さを排除）
                rk = f"task_reason:{task.id}:{decision.reason}"
                debug[rk] = debug.get(rk, 0) + 1
            due_map[h].append(task)

    return dict(due_map)

# ================================
# 3時間前通知用（内部UTC）
# ================================

def get_tasks_due_in_hours(
    db: Session,
    user_id: int,
    hours: int,
    *,
    now_utc: datetime,
    run_id: int | None = None,
) -> List[Task]:
    """
    互換用ラッパー。
    実際の通知判定は get_tasks_due_in_offsets に一本化する。
    """
    due_map = get_tasks_due_in_offsets(
        db,
        user_id=user_id,
        offsets=[hours],
        now_utc=now_utc,
        run_id=run_id,
    )
    return due_map.get(hours, [])

# ================================
# 当日朝通知用（内部UTC・判定はJST）
# ================================

def get_tasks_due_today_morning(
    db: Session,
    user_id: int,
    *,
    now_utc: datetime,
    run_id: int | None = None,
    debug: Dict[str, int] | None = None,
) -> List[Task]:
    """
    ✅ 内部UTC、判定はJSTの「今日」
    """
    today_jst = now_utc.astimezone(JST).date()
    now_jst = now_utc.astimezone(JST)
    # ✅ 朝通知は「朝の時間帯」だけ候補化する（SSOT入口から呼ばれても漏れないように）
    # cron.py の is_morning_window と同等の考え方
    if not (time(5, 0) <= now_jst.time() <= time(10, 0)):
        if debug is not None:
            debug["decision.skipped:not_morning_window"] = debug.get("decision.skipped:not_morning_window", 0) + 1
        return []
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
        override = (
            db.query(TaskNotificationOverride)
            .filter(
                TaskNotificationOverride.user_id == user_id,
                TaskNotificationOverride.task_id == task.id,
            )
            .first()
        )
        # ✅ 朝通知も Phase1 SSOT を必ず通す
        decision = decide_notification(
            task=task,
            weekly_is_active=weekly_is_active,
            now_utc=now_utc,
            override=override,
            base_offsets=[],
            offset_hours=0,       # ✅ 朝通知 = 0
        )
        if not decision.should_send:
            if debug is not None:
                k = f"decision.{decision.reason}"
                debug[k] = debug.get(k, 0) + 1
            logger.info(
                "[morning-skip] user_id=%s task_id=%s reason=%s",
                user_id, task.id, decision.reason
            )
            continue

        label_date = deadline_label_date_jst(task.deadline)
        deadline_utc = to_utc(task.deadline)

        if label_date == today_jst:
            if try_mark_notification_as_sent(
                db, user_id, task.id, deadline_utc, MORNING_OFFSET_HOURS,
                sent_at_utc=now_utc,
                run_id=run_id
            ):
                if debug is not None:
                    debug["decision.sent:morning_hit"] = debug.get("decision.sent:morning_hit", 0) + 1
                    rk = f"task_reason:{task.id}:{decision.reason}"
                    debug[rk] = debug.get(rk, 0) + 1
                result.append(task)
    return result

from dataclasses import dataclass
from typing import Dict, Tuple

@dataclass
class NotificationCandidates:
    due_in_hours: Dict[int, List[Task]]   # offset_hours -> tasks
    morning: List[Task]                   # 朝通知タスク
    debug: Dict[str, int]                 # 数だけ（ログ用）

def normalize_offsets_for_plan(
    *,
    raw_offsets: list[int] | None,
    plan: str | None,
) -> list[int]:
    """
    SSOT:
    - free は [1] 固定（朝通知は別ロジック）
    - int化 / <=0除外 / 重複排除（順序維持）
    """
    offsets = raw_offsets or []

    if (plan or "free") == "free":
        offsets = [1]

    normalized: list[int] = []
    seen: set[int] = set()
    for x in offsets:
        try:
            h = int(x)
        except (TypeError, ValueError):
            continue
        if h <= 0:
            continue
        if h in seen:
            continue
        seen.add(h)
        normalized.append(h)

    return normalized

def collect_notification_candidates(
    db: Session,
    user_id: int,
    offsets_hours: List[int] | None = None,  # ← デフォルトを付ける
    *,
    raw_offsets: List[int] | None = None,
    plan: str | None = None,
    now_utc: datetime,
    run_id: int | None = None,
) -> NotificationCandidates:
    # ✅ cron以外（API/手動/管理）から呼ばれても動くように
    # テストは now_utc を渡して固定できる
    if now_utc is None:
        now_utc = datetime.now(timezone.utc)

    # ✅ SSOT入口：plan + raw_offsets が来たらそれを唯一の真実として採用
    if raw_offsets is not None or plan is not None:
        normalized_offsets = normalize_offsets_for_plan(
            raw_offsets=list(raw_offsets or []),
            plan=plan,
        )
    else:
        # 互換：従来の offsets_hours を正規化
        normalized_offsets: List[int] = []
        for x in offsets_hours or []:
            try:
                h = int(x)
            except (TypeError, ValueError):
                continue
            if h > 0:
                normalized_offsets.append(h)    
         
    debug: Dict[str, int] = {
        "offsets_count": len(normalized_offsets),
        "offsets_raw_count": len(list(raw_offsets or [])) if (raw_offsets is not None) else -1,
    }
    due_map: Dict[int, List[Task]] = get_tasks_due_in_offsets(
        db,
        user_id=user_id,
        offsets=normalized_offsets,
        now_utc=now_utc,
        run_id=run_id,
        debug=debug,
    )

    morning_tasks = get_tasks_due_today_morning(
        db,
        user_id=user_id,
        now_utc=now_utc,
        run_id=run_id,
        debug=debug,
    )

    total_due = sum(len(v) for v in due_map.values())

    debug["due_total"] = total_due
    debug["morning_total"] = len(morning_tasks)

    return NotificationCandidates(
        due_in_hours=due_map,
        morning=morning_tasks,
        debug=debug,
    )