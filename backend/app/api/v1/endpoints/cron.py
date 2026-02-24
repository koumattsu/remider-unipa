# backend/app/api/v1/endpoints/cron.py

from sqlalchemy import text
import re
from datetime import datetime, timedelta, timezone, time
from typing import Dict
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, aliased
from sqlalchemy import and_, func
from app.db.session import get_db
from app.models.action_effectiveness_snapshot import ActionEffectivenessSnapshot
from app.models.user import User
from app.models.user_lifecycle_snapshot import UserLifecycleSnapshot
from app.models.task import Task
from app.models.in_app_notification import InAppNotification
from app.models.weekly_task import WeeklyTask
from app.models.notification_setting import NotificationSetting 
from app.models.notification_run import NotificationRun 
from app.models.webpush_delivery import WebPushDelivery
from app.models.webpush_event import WebPushEvent
from app.core.config import settings
from app.core.time import JST
from zoneinfo import ZoneInfo
from app.services.outcome_analytics import (
    build_action_effectiveness,
)
from app.services.notification import (
    collect_notification_candidates,
    to_utc,
    try_mark_notification_as_sent,  # ✅ 追加
    MORNING_OFFSET_HOURS,  
)
from app.services.line_client import (
    send_deadline_reminder,
    send_simple_text,
    send_daily_digest,
)
from app.services.weekly_materialize import materialize_weekly_tasks_for_user
from app.services.webpush_sender import WebPushSender
from app.services.outcome_decision import decide_task_outcome
from app.services.outcome_log_lock import try_mark_outcome_as_evaluated
from app.services.outcome_features import extract_outcome_features, FEATURE_VERSION
from app.services.outcome_feature_lock import try_mark_outcome_feature_as_saved

router = APIRouter()

TOKYO = ZoneInfo("Asia/Tokyo")

# ✅ HashRouter 前提の deeplink をSSOTとして統一
TODAY_DEEPLINK = "/#/dashboard?tab=today"

@router.post("/debug-migrate-notification-setting")
async def debug_migrate_notification_setting(db: Session = Depends(get_db)):
    """
    一度だけ実行する想定のマイグレーション用エンドポイント。
    Render本番の notification_settings テーブルに
    enable_morning_notification カラムを追加する。
    """
    try:
        db.execute(
            text(
                "ALTER TABLE notification_settings "
                "ADD COLUMN enable_morning_notification BOOLEAN NOT NULL DEFAULT 1;"
            )
        )
        db.commit()
        return {"status": "ok", "message": "column added"}
    except Exception as e:
        # すでにカラムがある場合などはここに来る
        return {"status": "error", "message": str(e)}
    
@router.post("/debug-migrate-action-effectiveness-snapshots")
async def debug_migrate_action_effectiveness_snapshots(db: Session = Depends(get_db)):
    """
    一度だけ実行する想定:
    action_effectiveness_snapshots テーブルを作る（Alembic無し運用のため）
    """
    try:
        db.execute(text("""
        CREATE TABLE IF NOT EXISTS action_effectiveness_snapshots (
          id SERIAL PRIMARY KEY,
          user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          bucket VARCHAR(16) NOT NULL,
          window_days INTEGER NOT NULL,
          min_total INTEGER NOT NULL,
          limit_events INTEGER NOT NULL,
          action_id VARCHAR(128) NOT NULL,
          applied_count INTEGER NOT NULL,
          measured_count INTEGER NOT NULL,
          improved_count INTEGER NOT NULL,
          improved_rate DOUBLE PRECISION NOT NULL,
          avg_delta_missed_rate DOUBLE PRECISION NOT NULL,
          captured_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """))
        db.commit()
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "message": str(e)}    

# ユーザーごとの通知設定を取得 or デフォルトで作成
def get_or_create_notification_setting(db: Session, user_id: int) -> NotificationSetting:
    setting = (
        db.query(NotificationSetting)
        .filter(NotificationSetting.user_id == user_id)
        .first()
    )

    if setting is None:
        setting = NotificationSetting(
            user_id=user_id,
            reminder_offsets_hours=[1],       # デフォルト: 1時間前のみ
            daily_digest_time="08:00",        # デフォルト: 朝8時
            enable_morning_notification=True, # デフォルト: 朝通知ON
        )
        db.add(setting)
        db.commit()
        db.refresh(setting)
        return setting

    # 万が一どれか空なら補正しておく
    updated = False

    if setting.enable_webpush is None:
        setting.enable_webpush = False
        updated = True

    if not setting.reminder_offsets_hours:
        setting.reminder_offsets_hours = [1]
        updated = True

    if not setting.daily_digest_time:
        setting.daily_digest_time = "08:00"
        updated = True

    if setting.enable_morning_notification is None:
        setting.enable_morning_notification = True
        updated = True

    if updated:
        db.add(setting)
        db.commit()
        db.refresh(setting)

    return setting

def _parse_hhmm(s: str | None) -> time:
    # "08:00" 想定。壊れてたら 08:00 にフォールバック
    try:
        if not s:
            raise ValueError("empty")
        hh, mm = s.split(":")
        return time(int(hh), int(mm))
    except Exception:
        return time(8, 0)

def _is_in_digest_window(*, now_jst: datetime, digest_time_str: str | None) -> bool:
    """
    ✅ 朝通知は daily_digest_time を唯一の真実にする
    - cron が 30分おき前提
    - 設定時刻の「少し前〜少し後」を許容して取りこぼしを防ぐ
      例: 08:00設定なら 07:55〜08:35
    """
    t = _parse_hhmm(digest_time_str)

    # ✅ TZ を確実に固定（tzinfo の混入/ズレを防ぐ）
    anchor = datetime(now_jst.year, now_jst.month, now_jst.day, t.hour, t.minute, tzinfo=TOKYO)

    start = anchor - timedelta(minutes=5)
    end = anchor + timedelta(minutes=35)
    return start <= now_jst < end

def _format_task_lines(tasks: list[Task]) -> str:
    # 要件：タイトル/締切/内容（箇条書き）
    # ここでは body に「箇条書き」を入れる
    lines: list[str] = []
    for t in tasks:
        # deadline は timezone aware 前提
        dl = t.deadline.astimezone(JST).strftime("%m/%d %H:%M") if t.deadline else "-"
        title = t.title or "(no title)"
        course = t.course_name or ""
        if course:
            lines.append(f"・{title}（{course} / {dl}）")
        else:
            lines.append(f"・{title}（{dl}）")
    return "\n".join(lines)

def _format_deadline_hhmm_jst(t: Task) -> str:
    if not t.deadline:
        return "-"
    return t.deadline.astimezone(JST).strftime("%H:%M")

def _build_single_task_push_body(t: Task) -> str:
    # ✅ 例: "統計学レポートの締切は18:00です"
    hhmm = _format_deadline_hhmm_jst(t)
    title = t.title or "(no title)"
    return f"{title}の締切は{hhmm}です"

def _upsert_in_app_notification(
    db: Session,
    *,
    run_id: int,
    user_id: int,
    task: Task,
    deadline_at_send_utc: datetime,
    offset_hours: int,
    kind: str,
    title: str,
    body: str,
    deep_link: str,
) -> InAppNotification | None:
    from sqlalchemy.exc import IntegrityError
    exists = (
        db.query(InAppNotification.id)
        .filter(InAppNotification.user_id == user_id)
        .filter(InAppNotification.task_id == task.id)
        .filter(InAppNotification.deadline_at_send == deadline_at_send_utc)
        .filter(InAppNotification.offset_hours == offset_hours)
        .first()
    )
    if exists:
        return None

    n = InAppNotification(
        run_id=run_id,
        user_id=user_id,
        task_id=task.id,
        deadline_at_send=deadline_at_send_utc,
        offset_hours=offset_hours,
        kind=kind,
        title=title,
        body=body,
        deep_link=deep_link,
    )
    db.add(n)
    try:
        with db.begin_nested() as nested:
            db.flush()  # ✅ Unique制約で最終チェック（並列でも壊れない）
    except IntegrityError:
        # ✅ SAVEPOINT だけ rollback（外側TXは生かす）
        nested.rollback()
        return None
    return n

@router.post("/debug-migrate-task-auto-notify-flag")
async def debug_migrate_task_auto_notify_flag(db: Session = Depends(get_db)):
    """
    一度だけ実行する想定:
    tasks テーブルに auto_notify_disabled_by_done カラムを追加する。
    """
    try:
        db.execute(text(
            "ALTER TABLE tasks "
            "ADD COLUMN IF NOT EXISTS auto_notify_disabled_by_done BOOLEAN NOT NULL DEFAULT false;"
        ))

        db.commit()
        return {"status": "ok", "message": "column added"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@router.post("/daily")
async def run_daily_job(db: Session = Depends(get_db)):
    started_at_utc = datetime.now(timezone.utc)
    now_utc = started_at_utc
    # ==============================
    # NotificationRun（cron 1実行 = 1行）
    # ==============================
    run = NotificationRun(status="running")
    db.add(run)
    db.commit()
    db.refresh(run)

    # NotificationRun counters（finallyで必ず参照するので先に初期化）
    users_total = 0
    users_processed = 0
    users_with_candidates = 0
    due_candidates_total = 0
    morning_candidates_total = 0
    inapp_created = 0
    webpush_sent = 0
    webpush_failed = 0
    webpush_deactivated = 0
    line_sent = 0
    line_failed = 0
    # ✅ decision reason 集計（SSOT由来）
    decision_counts: Dict[str, int] = {}

    try:
        # 内部の基準はUTC、ログ表示はJST
        now_utc = datetime.now(timezone.utc)
        now_jst = now_utc.astimezone(JST)

        # ✅ 朝通知：daily_digest_time の窓で判定（固定5-10は廃止）
        # setting は user ごとに取るので、ここでは作らない（下の user ループ内で判定）
        is_morning_window = None  # 互換の置き場所だけ確保（使わない）

        print("=== run_daily_job ===")
        print("[daily] build=2025-12-21-a")
        print("  now_utc:", now_utc)
        print("  now_jst:", now_jst)

        results: Dict[str, int] = {
            "morning": 0,
            "users_targeted": 0,
        }

        users = db.query(User).all()
        users_total = len(users)
        VALID_LINE_UID = re.compile(r"^U[0-9a-f]{32}$")

        for user in users:
            user_id = user.id
            line_user_id = user.line_user_id  # NoneでもOK

            results["users_targeted"] += 1
            users_processed += 1

            # 通知設定取得
            setting = get_or_create_notification_setting(db, user_id=user_id)

            digest_ok = _is_in_digest_window(
                now_jst=now_jst,
                digest_time_str=getattr(setting, "daily_digest_time", "08:00"),
            )

            # ★ weekly_tasks -> tasks の生成入口を materialize に統一（向こう7日分）
            materialize_weekly_tasks_for_user(db, user_id=user_id, days=7)

            # ✅ OutcomeLog：締切到達時点の結果を1回だけ確定保存（通知とは独立）
            outcomes_created = evaluate_task_outcomes(db, user_id=user_id, now_utc=now_utc)
            if outcomes_created:
                # ✅ OutcomeLog + FeatureSnapshot を同一トランザクションで確定
                db.commit()

            # - 例外で cron 全体を落とさない（監査ログは残す）
            try:
                eff = build_action_effectiveness(
                    db,
                    user_id=user_id,
                    from_applied_at=None,
                    to_applied_at=None,
                    window_days=7,
                    min_total=5,
                    limit_events=500,
                )

                items = list((eff or {}).get("items") or [])
                # 何も無い日は保存しない（ゴミ資産を増やさない）
                if items:
                    for x in items:
                        s = ActionEffectivenessSnapshot(
                            user_id=user_id,
                            bucket="week",
                            window_days=int((eff["range"] or {}).get("window_days", 7)),
                            min_total=int((eff["range"] or {}).get("min_total", 5)),
                            limit_events=int((eff["range"] or {}).get("limit_events", 500)),
                            action_id=str(x.get("action_id")),
                            applied_count=int(x.get("applied_count", 0)),
                            measured_count=int(x.get("measured_count", 0)),
                            improved_count=int(x.get("improved_count", 0)),
                            improved_rate=float(x.get("improved_rate", 0.0)),
                            avg_delta_missed_rate=float(x.get("avg_delta_missed_rate", 0.0)),
                        )
                        db.add(s)
                    db.commit()
            except Exception as e:
                print("[CRON] action effectiveness snapshot failed:", str(e))
                db.rollback()    

            # ns = db.query(NotificationSetting).filter(...).first()
            raw_offsets = list(getattr(setting, "reminder_offsets_hours", []) or [])

            cands = collect_notification_candidates(
                db,
                user_id=user_id,
                raw_offsets=raw_offsets,
                plan=getattr(user, "plan", "free"),
                now_utc=now_utc,
                run_id=run.id,
            )

            # ✅ 監査: decision reason 集計（従来通り）
            for k, v in (cands.debug or {}).items():
                if not (isinstance(k, str) and isinstance(v, int)):
                    continue
                if not k.startswith("decision."):
                    continue
                reason = k[len("decision."):]
                decision_counts[reason] = decision_counts.get(reason, 0) + v

            # ✅ 監査: 朝通知の「なぜ0か」を stats に残すための集計（SSOT維持・DB変更なし）
            # - decision.* 以外も含めて payload に載せられるように、ここで user 別の要点だけ取り出す
            # - 集計は "counts" として run.stats に入れる（finally で）
            if "cron_debug_counts" not in locals():
                cron_debug_counts = {"digest_ok_true": 0, "digest_ok_false": 0}
            if digest_ok:
                cron_debug_counts["digest_ok_true"] = int(cron_debug_counts.get("digest_ok_true", 0)) + 1
            else:
                cron_debug_counts["digest_ok_false"] = int(cron_debug_counts.get("digest_ok_false", 0)) + 1

            # notification.py 側の morning 監査カウンタ（存在するものだけ合算）
            for kk in [
                "morning.candidates_raw",
                "morning.skipped",
                "morning.skipped:label_date_mismatch",
                "morning.skipped:already_locked",
                "decision.sent:morning_hit",
                "due_total",
                "morning_total",
            ]:
                vv = (cands.debug or {}).get(kk)
                if isinstance(vv, int):
                    cron_debug_counts[kk] = int(cron_debug_counts.get(kk, 0)) + int(vv)
            
            had_any_candidate = False
            for h, ts in cands.due_in_hours.items():
                due_candidates_total += len(ts)
                if ts:
                    had_any_candidate = True

            # morning
            if cands.morning:
                had_any_candidate = True

            if had_any_candidate:
                users_with_candidates += 1

            offsets = sorted(cands.due_in_hours.keys())

            for h in offsets:
                print("[daily] user_id=", user_id, "due_count@", h, "=", len(cands.due_in_hours.get(h, [])))
            # ---------- ① 「○時間前」通知 ----------

            for hours in offsets:
                tasks_due = cands.due_in_hours.get(hours, [])
                if not tasks_due:
                    continue

                # ✅ まずベル通知を作る（無料の最低保証）
                created_inapps: list[InAppNotification] = []
                for task in tasks_due:
                    deadline_at_send = to_utc(task.deadline)
                    reason = None
                    if cands.debug:
                        reason = cands.debug.get(f"task_reason:{task.id}")

                    n = _upsert_in_app_notification(
                        db=db,
                        run_id=run.id,
                        user_id=user_id,
                        task=task,
                        deadline_at_send_utc=deadline_at_send,
                        offset_hours=hours,
                        kind="task_reminder",
                        title=f"締切まで約{int(hours)}時間",
                        body=_build_single_task_push_body(task),
                        deep_link=TODAY_DEEPLINK,
                    )
                    if n:
                        n.extra = {**(n.extra or {}), "reason": reason}
                        created_inapps.append(n)
                        inapp_created += 1

                if created_inapps:
                    db.commit()

                # ✅ WebPush（無料/有料共通・設定ONのときだけ）
                if setting.enable_webpush:
                    touched = False
                    for n in created_inapps:
                        try:
                            res = WebPushSender.send_for_notification(
                                db=db,
                                user_id=user_id,
                                notification=n,
                            )
                            webpush_sent += int(res.get("sent", 0))
                            webpush_failed += int(res.get("failed", 0))
                            webpush_deactivated += int(res.get("deactivated", 0))

                            sent_n = int(res.get("sent", 0))
                            failed_n = int(res.get("failed", 0))
                            deactivated_n = int(res.get("deactivated", 0))

                            if sent_n > 0:
                                delivery_status = "sent"
                            elif deactivated_n > 0 and failed_n == 0:
                                delivery_status = "deactivated"
                            elif failed_n > 0:
                                delivery_status = "failed"
                            else:
                                delivery_status = "skipped"

                            n.extra = {
                                **(n.extra or {}),
                                "webpush": {
                                    "status": delivery_status,
                                    "at": now_utc.isoformat(),
                                    "sent": sent_n,
                                    "failed": failed_n,
                                    "deactivated": deactivated_n,
                                },
                            }
                            db.add(n)
                            touched = True
                        except Exception as e:
                            print("[CRON] webpush failed:", str(e))
                            webpush_failed += 1
                            n.extra = {
                                **(n.extra or {}),
                                "webpush": {
                                    "status": "failed",
                                    "at": now_utc.isoformat(),
                                    "sent": 0,
                                    "failed": 1,
                                    "deactivated": 0,
                                },
                                "webpush_error": str(e)[:300],
                            }
                            db.add(n)
                            touched = True

                    if touched:
                        db.commit()

                if user.plan != "free" and line_user_id:
                    try:
                        trace_id = await send_deadline_reminder(...)
                        line_sent += len(tasks_due)
                        if created_inapps:
                            for n in created_inapps:
                                n.extra = {
                                    **(n.extra or {}),
                                    "line": {"status": "sent", "at": now_utc.isoformat(), "trace_id": trace_id},
                                }
                                db.add(n)
                            db.commit()
                    except Exception as e:
                        print("[CRON] send_deadline_reminder failed:", str(e))
                        line_failed += len(tasks_due)
                        if created_inapps:
                            for n in created_inapps:
                                n.extra = {
                                    **(n.extra or {}),
                                    "line": {"status": "failed", "at": now_utc.isoformat(), "error": str(e)[:300]},
                                }
                                db.add(n)
                            db.commit()

                # ✅ 集計は常に offset_{hours} に統一（SSOT）
                key = f"offset_{int(hours)}"
                results[key] = results.get(key, 0) + len(tasks_due)
        
            # ---------- ② 当日タスクの「朝通知」（時間条件を外す） ----------
            if setting.enable_morning_notification and digest_ok:
                tasks_today = cands.morning

                # ✅ 朝ダイジェストもベルに残す（無料の最低保証）
                created_morning: list[InAppNotification] = []
                locked_tasks_today: list[Task] = []

                for task in tasks_today:
                    deadline_at_send = to_utc(task.deadline)

                    # ✅ ここで “送信確定ロック(offset=0)” を取る（候補抽出側では取らない）
                    ok = try_mark_notification_as_sent(
                        db,
                        user_id=user_id,
                        task_id=task.id,
                        deadline_utc=deadline_at_send,
                        offset_hours=0,               # MORNING_OFFSET_HOURS 相当
                        sent_at_utc=now_utc,
                        run_id=run.id,
                    )
                    if not ok:
                        # ✅ 既に同じ朝のロックを取られている（重複防止）
                        if cands.debug is not None:
                            cands.debug["morning.skipped:already_locked"] = (
                                int(cands.debug.get("morning.skipped:already_locked", 0)) + 1
                            )
                        continue

                    # ✅ ここから先は「朝通知として確定」した task
                    locked_tasks_today.append(task)

                    if cands.debug is not None:
                        cands.debug["decision.sent:morning_hit"] = (
                            int(cands.debug.get("decision.sent:morning_hit", 0)) + 1
                        )

                    reason = None
                    if cands.debug:
                        reason = cands.debug.get(f"task_reason:{task.id}")

                    n = _upsert_in_app_notification(
                        db=db,
                        run_id=run.id,
                        user_id=user_id,
                        task=task,
                        deadline_at_send_utc=deadline_at_send,
                        offset_hours=MORNING_OFFSET_HOURS,
                        kind="morning_digest",
                        title="今日の締切",
                        body=_build_single_task_push_body(task),
                        deep_link=TODAY_DEEPLINK,
                    )
                    if n:
                        n.extra = {
                            **(n.extra or {}),
                            "reason": reason,
                        }
                        created_morning.append(n)
                        inapp_created += 1

                # ✅ “ロック成功数” を朝の公式カウントにする（嘘をやめる）
                morning_candidates_total += len(locked_tasks_today)

                # ✅ ロック成功が1件でもあれば commit（InAppが既存でもロックは資産）
                if locked_tasks_today or created_morning:
                    db.commit()

                # ✅ WebPush（朝は1本に集約：digest）
                if setting.enable_webpush and locked_tasks_today and created_morning:
                    show = locked_tasks_today[:8]
                    lines: list[str] = []
                    for t in show:
                        hhmm = _format_deadline_hhmm_jst(t)
                        title = t.title or "(no title)"
                        lines.append(f"・{title} {hhmm}")
                    if len(locked_tasks_today) > len(show):
                        lines.append(f"ほか{len(locked_tasks_today) - len(show)}件")

                    anchor = created_morning[0]

                    payload = {
                        "title": "今日の締切",
                        "body": "\n".join(lines),
                        "url": anchor.deep_link,
                        "deep_link": anchor.deep_link,
                        "notification_id": anchor.id,
                        "run_id": run.id,
                    }

                    try:
                        res = WebPushSender._send_payload(
                            db,
                            user_id=user_id,
                            payload=payload,
                            in_app_notification_id=anchor.id,
                            run_id=run.id,
                        )
                        webpush_sent += int(res.get("sent", 0))
                        webpush_failed += int(res.get("failed", 0))
                        webpush_deactivated += int(res.get("deactivated", 0))

                        anchor.extra = {
                            **(anchor.extra or {}),
                            "webpush_digest": {
                                "status": "sent" if int(res.get("sent", 0)) > 0 else "skipped",
                                "sent": int(res.get("sent", 0)),
                                "failed": int(res.get("failed", 0)),
                                "deactivated": int(res.get("deactivated", 0)),
                                "at": now_utc.isoformat(),
                                "tasks_total": len(locked_tasks_today),
                                "shown": len(show),
                            },
                        }
                        db.add(anchor)
                        db.commit()

                    except Exception as e:
                        print("[CRON] webpush digest failed:", str(e))
                        webpush_failed += 1
                        db.rollback()

                # ✅ LINE（有料のみ）も “ロック成功分” だけ送る
                if locked_tasks_today:
                    if user.plan != "free" and line_user_id:
                        try:
                            trace_id = await send_daily_digest(
                                line_user_id=line_user_id,
                                tasks=locked_tasks_today,
                            )
                            if created_morning:
                                for n in created_morning:
                                    n.extra = {
                                        **(n.extra or {}),
                                        "line": {
                                            "status": "sent",
                                            "at": now_utc.isoformat(),
                                            "trace_id": trace_id,
                                        },
                                    }
                                    db.add(n)
                                db.commit()
                        except Exception as e:
                            print("[CRON] send_daily_digest failed:", str(e))
                            if created_morning:
                                for n in created_morning:
                                    n.extra = {
                                        **(n.extra or {}),
                                        "line": {
                                            "status": "failed",
                                            "at": now_utc.isoformat(),
                                            "error": str(e)[:300],
                                        },
                                    }
                                    db.add(n)
                                db.commit()

                    # ✅ “morning” の件数も嘘をやめてロック成功数
                    results["morning"] += len(locked_tasks_today)

                    # ✅ 朝ループ内で増えた debug を run 集計に反映（合算タイミングを正す）
                    for kk in [
                        "morning.candidates_raw",
                        "morning.passed_ssot",
                        "morning.passed_label_date",
                        "morning.skipped",
                        "morning.skipped:label_date_mismatch",
                        "morning.skipped:already_locked",
                        "decision.sent:morning_hit",
                        "due_total",
                        "morning_total",
                    ]:
                        vv = (cands.debug or {}).get(kk)
                        if isinstance(vv, int):
                            cron_debug_counts[kk] = int(cron_debug_counts.get(kk, 0)) + int(vv)

        # ✅ API 表示用：そのまま返す（嘘の正規化をしない）
        detail = dict(results)

        notified = any(
            k.startswith("offset_") and v > 0 for k, v in detail.items()
        ) or detail.get("morning", 0) > 0

        return {
            "notified": notified,
            "detail": detail,
            "run_id": int(run.id),
            "build": settings.BUILD_ID,
        }

    except Exception as e:
        db.rollback()
        run.status = "fail"
        run.error_summary = (f"{type(e).__name__}: {str(e)}")[:500]
        raise

    finally:
        run.users_processed = users_processed
        run.users_total = users_total
        run.users_with_candidates = users_with_candidates
        run.duration_ms = int((now_utc - started_at_utc).total_seconds() * 1000)
        run.due_candidates_total = due_candidates_total
        run.morning_candidates_total = morning_candidates_total
        run.inapp_created = inapp_created
        # ✅ 例外でも必ず存在するように初期化（SSOTの防波堤）
        snapshot = None
        events = {"sent": 0, "failed": 0, "deactivated": 0, "skipped": 0, "unknown": 0}
        webpush_source = "delivery"

        try:
            inapp_total = int(
                db.query(func.count(InAppNotification.id))
                .filter(InAppNotification.run_id == run.id)
                .scalar()
                or 0
            )
            # ✅ SSOT: message軸の WebPush（通知メッセージ数 / opened数）
            # - sent_messages: run内で生成された InAppNotification（= message）
            # - opened_messages: webpush_events.notification_id の DISTINCT（= message）
            # NOTE: delivery軸(webpush_events)とは別に保持する（互換/監査のため）
            opened_messages = 0
            try:
                opened_messages = int(
                    db.query(func.count(func.distinct(WebPushEvent.notification_id)))
                    .filter(WebPushEvent.run_id == run.id)
                    .filter(WebPushEvent.event_type.in_(["opened", "open", "click"]))
                    .scalar()
                    or 0
                )
            except Exception:
                pass

            sent_messages = int(inapp_total or 0)
            open_rate = (float(opened_messages) / float(sent_messages)) if sent_messages > 0 else None

            webpush_messages = {
                "sent_messages": sent_messages,
                "opened_messages": opened_messages,
                "open_rate": open_rate,
            }


            # ✅ SSOT: WebPushDelivery から集計（subscription軸=attempt数）
            # NOTE:
            # - events は「通知メッセージ数」ではなく「subscriptionごとの配信attempt数」
            #   （= WebPushDelivery 行数）を集計している。
            # - 反応率(opened/送信)を message軸で出す場合、この events を分母に使うと粒度がズレるので注意。
            try:
                rows2 = (
                    db.query(WebPushDelivery.status, func.count(WebPushDelivery.id))
                    .filter(WebPushDelivery.run_id == run.id)
                    .group_by(WebPushDelivery.status)
                    .all()
                )
                for st, cnt in rows2 or []:
                    key = st if st in events else "unknown"
                    events[key] += int(cnt or 0)
            except Exception:
                pass

            # ✅ fallback（FakeSession / 旧環境）
            if sum(events.values()) == 0:
                webpush_source = "inapp_extra"
                status_expr = func.jsonb_extract_path_text(
                    InAppNotification.extra, "webpush", "status"
                )
                rows = (
                    db.query(status_expr.label("status"), func.count(InAppNotification.id))
                    .filter(InAppNotification.run_id == run.id)
                    .group_by(status_expr)
                    .all()
                )
                for st, cnt in rows or []:
                    key = st if st in events else "unknown"
                    events[key] += int(cnt or 0)

            snapshot = {
                "generated_at": now_utc.isoformat(),
                "inapp_total": inapp_total,
                "webpush_events": events,
                "webpush_source": webpush_source,
                "webpush_messages": webpush_messages,
            }
        except Exception as e:
            snapshot = {
                "generated_at": now_utc.isoformat(),
                "error": (f"{type(e).__name__}: {str(e)}")[:300],
                "webpush_source": webpush_source,
                "webpush_events": events,
                "webpush_messages": {
                    "sent_messages": 0,
                    "opened_messages": 0,
                    "open_rate": None,
                },
            }

        # ✅ SSOT集計結果を直カラムへ同期（監査一貫性）
        # NOTE: これらは attempt数（subscription軸）であり、通知メッセージ数ではない。
        run.webpush_sent = int(events.get("sent", 0))
        run.webpush_failed = int(events.get("failed", 0))
        run.webpush_deactivated = int(events.get("deactivated", 0))
        build_id = settings.BUILD_ID
        run.stats = {
            "v": 1,
            "kind": "notification_run_stats",
            "generated_at": now_utc.isoformat(),
            "payload": {
                "build": build_id,
                "now_utc": started_at_utc.isoformat(),
                "users_total": users_total,
                "users_processed": users_processed,
                "users_with_candidates": users_with_candidates,
                "snapshot": snapshot,
                "decision_counts": decision_counts,
                # ✅ 監査: 朝通知が0の時に「窓/候補/ロック」どこで落ちたかを説明可能にする
                "cron_debug_counts": (locals().get("cron_debug_counts") or {}),
                # ✅ 明示: morning_candidates_total は "morning_total(=ロック成功数)" と一致する設計
                "notes": {
                    "morning_candidates_total_semantics": "count of tasks that passed morning label_date and acquired offset=0 lock (try_mark_notification_as_sent)",
                },
            },
        }
        run.line_sent = line_sent
        run.line_failed = line_failed

        # ==============================
        # status 確定（success/partial/fail）
        # ==============================
        has_success = (inapp_created > 0) or (run.webpush_sent > 0) or (line_sent > 0)
        has_failure = (run.webpush_failed > 0) or (line_failed > 0)

        # except で fail がセット済みなら尊重（例外落ち）
        if run.status != "fail":
            if has_success and has_failure:
                run.status = "partial"
            elif has_success and not has_failure:
                run.status = "success"
            elif (not has_success) and has_failure:
                run.status = "fail"
            else:
                # 候補ゼロなど：正常
                run.status = "success"

        run.finished_at = now_utc
        db.add(run)
        db.commit()

        # ==============================
        # UserLifecycleSnapshot（資産）：1日1回自動 capture（失敗しても cron を落とさない）
        # ==============================
        lifecycle_result = {"attempted": 0, "created": 0, "skipped": 0, "error": None}
        try:
            captured_day = now_utc.astimezone(JST).date()

            # FakeSession 互換：User は query 禁止の可能性があるので _added fallback
            try:
                users = db.query(User).all() or []
            except Exception:
                added = getattr(db, "_added", []) or []
                users = [x for x in added if isinstance(x, User)]

            lifecycle_result["attempted"] = len(users)

            # タスクは count/distinct 禁止環境でも動くように all→Python（既存方針に揃える）
            try:
                tasks_all = db.query(Task).all() or []
            except Exception:
                added = getattr(db, "_added", []) or []
                tasks_all = [x for x in added if isinstance(x, Task)]

            tasks_by_user: dict[int, list[Task]] = {}
            for t in tasks_all:
                if getattr(t, "deleted_at", None) is not None:
                    continue
                uid = int(getattr(t, "user_id"))
                tasks_by_user.setdefault(uid, []).append(t)

            created_ids: list[int] = []

            for u in users:
                uid = int(getattr(u, "id"))

                # ✅ DBユニーク制約が最終防衛線。ここでは savepoint で「1ユーザだけスキップ」を可能にする
                try:
                    with db.begin_nested():
                        user_tasks = tasks_by_user.get(uid, [])

                        tasks_total = int(len(user_tasks))
                        completed_total = int(
                            sum(1 for t in user_tasks if getattr(t, "completed_at", None) is not None)
                        )
                        done_rate = float(completed_total / tasks_total) if tasks_total > 0 else 0.0

                        # first/last は “手元にある資産” から作れる範囲で固定（まずは Task のみ）
                        created_ats = [getattr(t, "created_at", None) for t in user_tasks if getattr(t, "created_at", None)]
                        completed_ats = [getattr(t, "completed_at", None) for t in user_tasks if getattr(t, "completed_at", None)]
                        updated_ats = [getattr(t, "updated_at", None) for t in user_tasks if getattr(t, "updated_at", None)]

                        snap = UserLifecycleSnapshot(
                            user_id=uid,
                            captured_at=now_utc,
                            captured_day=captured_day,
                            registered_at=getattr(u, "created_at", None),  # ※User.created_at導入は次Priorityで強化
                            first_task_created_at=min(created_ats) if created_ats else None,
                            first_task_completed_at=min(completed_ats) if completed_ats else None,
                            last_active_at=max(updated_ats + completed_ats) if (updated_ats or completed_ats) else None,
                            tasks_total=tasks_total,
                            completed_total=completed_total,
                            done_rate=done_rate,
                            active_7d=False,   # 次で SSOT 定義を固める（last_active_at 基準に統一）
                            active_30d=False,  # 次で SSOT 定義を固める
                        )
                        db.add(snap)
                        db.flush()  # id 確定
                        created_ids.append(int(snap.id))
                        lifecycle_result["created"] += 1
                except Exception:
                    # ここは「同日重複」なども含む。cron全体は落とさない。
                    lifecycle_result["skipped"] += 1
                    continue

            if created_ids:
                db.commit()
            else:
                db.rollback()

        except Exception as e:
            db.rollback()
            lifecycle_result["error"] = (f"{type(e).__name__}: {str(e)}")[:300]

        # ✅ 監査価値UP：run.stats に lifecycle 結果を追記して再コミット（run自体は既に確定済み）
        try:
            if isinstance(run.stats, dict):
                payload = run.stats.get("payload") or {}
                payload["lifecycle_capture"] = {
                    "captured_day": str(now_utc.astimezone(JST).date()),
                    **lifecycle_result,
                }
                run.stats["payload"] = payload
                db.add(run)
                db.commit()
        except Exception:
            db.rollback()

# ここから下の debug 系は、君の元コードそのまま残してOK
@router.post("/debug-send")
async def debug_send(db: Session = Depends(get_db)):
    """
    デバッグ用:
    現在登録されているユーザー全員にテストメッセージを送る。
    LINE Messaging API の動作確認に使用。
    """
    users = (
        db.query(User)
        .filter(User.line_user_id.isnot(None))
        .all()
    )

    results = []
    ok = 0
    ng = 0

    # テスト用メッセージ（固定）
    msg = "🔧 デバッグ通知テスト\nUNIPAリマインダーのLINE送信テストです。"

    for user in users:
        line_user_id = user.line_user_id
        if not line_user_id:
            ng += 1
            results.append({
                "user_id": user.id,
                "status": "skipped",
                "reason": "line_user_id is empty",
            })
            continue

        # フォーマット不正はスキップ（line_clientも同様にwarnしてreturnするが、結果に残す）
        if not (isinstance(line_user_id, str) and re.fullmatch(r"U[0-9a-f]{32}", line_user_id)):
            ng += 1
            results.append({
                "user_id": user.id,
                "line_user_id": line_user_id,
                "status": "skipped",
                "reason": "invalid line_user_id format (expected U + 32 hex chars)",
            })
            continue
        try:
            await send_simple_text(line_user_id, msg)
            ok += 1
            results.append({
                "user_id": user.id,
                "line_user_id": line_user_id,
                "status": "sent",
            })
        except Exception as e:
            ng += 1
            # line_client.py は RuntimeError に status/body を入れて投げてくれてるので repr(e) で十分追える
            results.append({
                "user_id": user.id,
                "line_user_id": line_user_id,
                "status": "error",
                "error": repr(e),
            })

    return {
        "message": "debug-send executed",
        "sent_ok": ok,
        "sent_ng": ng,
        "count": len(results),
        "results": results,
    }

@router.get("/debug-users")
async def debug_users(db: Session = Depends(get_db)):
    """
    デバッグ用:
    User テーブルの中身をざっくり確認するエンドポイント。
    line_user_id を持っているかどうかを中心に見る。
    """
    users = db.query(User).all()
    result = []
    for u in users:
        result.append(
            {
                "id": u.id,
                "line_user_id": u.line_user_id,
                "display_name": getattr(u, "display_name", None),
                "university": getattr(u, "university", None),
                "plan": getattr(u, "plan", None),
            }
        )
    return {
        "count": len(result),
        "users": result,
    }

@router.get("/debug-task")
async def debug_task(
    task_id: int = Query(..., ge=1),
    db: Session = Depends(get_db),
):
    """
    デバッグ用:
    tasks API が認証必須でも、DB上の task を確認できる観測点。
    通知が来ない時に「task の user_id / deadline / should_notify」を確定する。
    """
    t = db.query(Task).filter(Task.id == task_id).first()
    if not t:
        return {"found": False, "task_id": task_id}

    return {
        "found": True,
        "task": {
            "id": t.id,
            "user_id": getattr(t, "user_id", None),
            "title": getattr(t, "title", None),
            "course_name": getattr(t, "course_name", None),
            "deadline": str(getattr(t, "deadline", None)),
            "should_notify": getattr(t, "should_notify", None),
            "is_done": getattr(t, "is_done", None),
            "auto_notify_disabled_by_done": getattr(t, "auto_notify_disabled_by_done", None),
        },
    }

@router.get("/debug-tasks-recent")
async def debug_tasks_recent(
    user_id: int = 2,
    limit: int = 10,
    db: Session = Depends(get_db),
):
    qs = (
        db.query(Task)
        .filter(Task.user_id == user_id)
        .order_by(Task.deadline.desc())
        .limit(limit)
        .all()
    )
    return {
        "user_id": user_id,
        "count": len(qs),
        "tasks": [
            {
                "id": t.id,
                "title": t.title,
                "deadline": str(t.deadline),
                "should_notify": t.should_notify,
                "is_done": t.is_done,
            }
            for t in qs
        ],
    }

@router.post("/debug-register-user")
async def debug_register_user(
    line_user_id: str,
    db: Session = Depends(get_db),
):
    """
    デバッグ用:
    手動で User を1件登録 or 取得する。
    - すでに存在する line_user_id ならそのユーザーを返す
    - 無ければ新規作成する
    ※ display_name / university / plan にデフォルトを入れて、
      NOT NULL 制約で落ちないようにしている。
    """
    try:
        if not re.fullmatch(r"U[0-9a-f]{32}", line_user_id):
            return {"created": False, "error": "invalid line_user_id format (expected U + 32 hex chars)"}
        # 既存ユーザー検索
        user = (
            db.query(User)
            .filter(User.line_user_id == line_user_id)
            .first()
        )

        created = False

        # なければ新規作成
        if not user:
            user = User(
                line_user_id=line_user_id,
                display_name="LINEユーザー",
                university="未設定",
                plan="free",
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            created = True

        # ★ 必ず dict を return する（None を返さない）
        return {
            "created": created,
            "user": {
                "id": user.id,
                "line_user_id": user.line_user_id,
            },
        }

    except Exception as e:
        # 例外が出ても null を返さないようにする
        db.rollback()
        return {
            "created": False,
            "error": str(e),
        }

def evaluate_task_outcomes(db: Session, user_id: int, now_utc: datetime) -> int:
    """
    user_id の tasks について、
    deadline <= now_utc かつ (user_id, task_id, deadline) の OutcomeLog が無いものを評価して保存する。

    outcome 定義（設計合意）:
    - completed_at があり completed_at <= deadline → done
    - それ以外 → missed

    戻り値: 今回追加したログ件数
    """
    due_tasks = (
        db.query(Task)
        .filter(Task.user_id == user_id)
        .filter(Task.deadline <= now_utc)
        .all()
    )
    if not due_tasks:
        return 0
    created = 0
    for t in due_tasks:
        deadline = t.deadline
        outcome = decide_task_outcome(t, at_utc=now_utc)
        locked = try_mark_outcome_as_evaluated(
            db,
            user_id=user_id,
            task_id=t.id,
            deadline_utc=deadline,
            outcome=outcome,
            evaluated_at_utc=now_utc,
        )
        if locked:
            # ✅ Feature Snapshot（資産）: Outcome確定と同一トランザクションで保存
            features = extract_outcome_features(t)
            try_mark_outcome_feature_as_saved(
                db,
                user_id=user_id,
                task_id=t.id,
                deadline_utc=deadline,
                feature_version=FEATURE_VERSION,
                features=features,
            )
            created += 1

    # ✅ commit は呼び出し側（cron）に任せる：同一トランザクションを崩さない
    return created

@router.post("/debug-migrate-notification-runs")
async def debug_migrate_notification_runs(db: Session = Depends(get_db)):
    """
    一度だけ実行する想定:
    notification_runs テーブルに不足カラムを追加する（Alembic無し運用のため）
    """
    try:
        db.execute(text("""
        ALTER TABLE notification_runs
          ADD COLUMN IF NOT EXISTS users_total INTEGER NOT NULL DEFAULT 0,
          ADD COLUMN IF NOT EXISTS users_with_candidates INTEGER NOT NULL DEFAULT 0,
          ADD COLUMN IF NOT EXISTS duration_ms INTEGER NOT NULL DEFAULT 0,

          ADD COLUMN IF NOT EXISTS webpush_sent INTEGER NOT NULL DEFAULT 0,
          ADD COLUMN IF NOT EXISTS webpush_failed INTEGER NOT NULL DEFAULT 0,
          ADD COLUMN IF NOT EXISTS webpush_deactivated INTEGER NOT NULL DEFAULT 0,

          ADD COLUMN IF NOT EXISTS line_sent INTEGER NOT NULL DEFAULT 0,
          ADD COLUMN IF NOT EXISTS line_failed INTEGER NOT NULL DEFAULT 0,

          ADD COLUMN IF NOT EXISTS finished_at TIMESTAMPTZ NULL,
          ADD COLUMN IF NOT EXISTS stats JSONB NULL;
        """))
        db.commit()
        return {"status": "ok", "message": "notification_runs columns added"}
    except Exception as e:
        db.rollback()
        return {"status": "error", "message": str(e)}
    
@router.get("/debug-db-info")
async def debug_db_info(db: Session = Depends(get_db)):
    row = db.execute(text("""
        SELECT
          current_database() AS db,
          current_user AS db_user,
          inet_server_addr()::text AS server_addr,
          inet_server_port() AS server_port,
          current_setting('search_path') AS search_path
    """)).mappings().first()
    return {"db_info": dict(row or {})}