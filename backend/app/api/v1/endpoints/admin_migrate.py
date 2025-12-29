# backend/app/api/v1/endpoints/admin_migrate.py

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from sqlalchemy import select
from app.db.session import get_db
from app.db.base import init_db
from app.models.user import User
from app.models.notification_setting import NotificationSetting
from app.models.notification_run import NotificationRun

router = APIRouter(tags=["admin"])

@router.post("/migrate/create-tables")
def create_tables():
    """
    テーブルが足りない場合に create_all で作成する（1回だけ実行想定）
    """
    init_db()
    return {"status": "ok"}

@router.post("/migrate/notification-settings")
def migrate_notification_settings(db: Session = Depends(get_db)):
    """
    既存ユーザーに NotificationSetting が無ければ作成する
    （一度だけ実行する移行用エンドポイント）
    """
    users = db.query(User).all()
    created = 0
    for user in users:
        exists = (
            db.query(NotificationSetting)
            .filter(NotificationSetting.user_id == user.id)
            .first()
        )
        if not exists:
            db.add(NotificationSetting(user_id=user.id))
            created += 1

    db.commit()
    return {
        "created": created,
        "total_users": len(users),
    }

@router.post("/migrate/task-notification-logs-deadline-at-send")
def migrate_task_notification_logs_deadline_at_send(db: Session = Depends(get_db)):
    """
    本番DBに deadline_at_send が無い場合に追加する（1回だけ実行）
    ついでに index / unique をDB側にも整える（あればスキップ）
    """
    # 1) column 追加（存在するなら何もしない）
    db.execute(
        text("""
        ALTER TABLE task_notification_logs
        ADD COLUMN IF NOT EXISTS deadline_at_send TIMESTAMPTZ NULL;
        """)
    )

    # 2) index 追加（存在するなら何もしない）
    db.execute(
        text("""
        CREATE INDEX IF NOT EXISTS ix_task_notif_user_task_deadline_at_send_offset
        ON task_notification_logs (user_id, task_id, deadline_at_send, offset_hours);
        """)
    )

    # 3) unique constraint 追加（IF NOT EXISTS が無いので DO ブロックで安全に）
    db.execute(
        text("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'uq_task_notification_user_task_deadline_offset'
            ) THEN
                ALTER TABLE task_notification_logs
                ADD CONSTRAINT uq_task_notification_user_task_deadline_offset
                UNIQUE (user_id, task_id, deadline_at_send, offset_hours);
            END IF;
        END $$;
        """)
    )

    db.commit()
    return {"status": "ok"}

@router.post("/migrate/notification-runs")
def migrate_notification_runs(db: Session = Depends(get_db)):
    """
    NotificationRun をDBに導入する（1回だけ実行想定）
    - テーブル作成
    - 不足カラムがあれば追加（将来の拡張にも耐える）
    """
    dialect = db.bind.dialect.name if db.bind is not None else "unknown"

    # SQLite など（本番はPostgres想定だが、開発の壊れ防止）
    if dialect != "postgresql":
        init_db()
        return {"status": "ok", "dialect": dialect, "mode": "init_db"}

    # 1) create table（存在するなら何もしない）
    db.execute(
        text("""
        CREATE TABLE IF NOT EXISTS notification_runs (
            id SERIAL PRIMARY KEY,
            status VARCHAR(16) NOT NULL DEFAULT 'running',
            error_summary TEXT NULL,

            users_processed INTEGER NOT NULL DEFAULT 0,

            due_candidates_total INTEGER NOT NULL DEFAULT 0,
            morning_candidates_total INTEGER NOT NULL DEFAULT 0,

            inapp_created INTEGER NOT NULL DEFAULT 0,

            webpush_sent INTEGER NOT NULL DEFAULT 0,
            webpush_failed INTEGER NOT NULL DEFAULT 0,
            webpush_deactivated INTEGER NOT NULL DEFAULT 0,

            line_sent INTEGER NOT NULL DEFAULT 0,
            line_failed INTEGER NOT NULL DEFAULT 0,

            started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            finished_at TIMESTAMPTZ NULL
        );
        """)
    )

    # 2) 将来のカラム追加に備え、ADD COLUMN IF NOT EXISTS（安全側）
    db.execute(text("ALTER TABLE notification_runs ADD COLUMN IF NOT EXISTS status VARCHAR(16) NOT NULL DEFAULT 'running';"))
    db.execute(text("ALTER TABLE notification_runs ADD COLUMN IF NOT EXISTS error_summary TEXT NULL;"))

    db.execute(text("ALTER TABLE notification_runs ADD COLUMN IF NOT EXISTS users_processed INTEGER NOT NULL DEFAULT 0;"))
    db.execute(text("ALTER TABLE notification_runs ADD COLUMN IF NOT EXISTS due_candidates_total INTEGER NOT NULL DEFAULT 0;"))
    db.execute(text("ALTER TABLE notification_runs ADD COLUMN IF NOT EXISTS morning_candidates_total INTEGER NOT NULL DEFAULT 0;"))
    db.execute(text("ALTER TABLE notification_runs ADD COLUMN IF NOT EXISTS inapp_created INTEGER NOT NULL DEFAULT 0;"))

    db.execute(text("ALTER TABLE notification_runs ADD COLUMN IF NOT EXISTS webpush_sent INTEGER NOT NULL DEFAULT 0;"))
    db.execute(text("ALTER TABLE notification_runs ADD COLUMN IF NOT EXISTS webpush_failed INTEGER NOT NULL DEFAULT 0;"))
    db.execute(text("ALTER TABLE notification_runs ADD COLUMN IF NOT EXISTS webpush_deactivated INTEGER NOT NULL DEFAULT 0;"))

    db.execute(text("ALTER TABLE notification_runs ADD COLUMN IF NOT EXISTS line_sent INTEGER NOT NULL DEFAULT 0;"))
    db.execute(text("ALTER TABLE notification_runs ADD COLUMN IF NOT EXISTS line_failed INTEGER NOT NULL DEFAULT 0;"))

    db.execute(text("ALTER TABLE notification_runs ADD COLUMN IF NOT EXISTS started_at TIMESTAMPTZ NOT NULL DEFAULT NOW();"))
    db.execute(text("ALTER TABLE notification_runs ADD COLUMN IF NOT EXISTS finished_at TIMESTAMPTZ NULL;"))

    # ---- v2: observability columns ----
    db.execute(text("ALTER TABLE notification_runs ADD COLUMN IF NOT EXISTS users_total INTEGER NOT NULL DEFAULT 0;"))
    db.execute(text("ALTER TABLE notification_runs ADD COLUMN IF NOT EXISTS users_with_candidates INTEGER NOT NULL DEFAULT 0;"))
    db.execute(text("ALTER TABLE notification_runs ADD COLUMN IF NOT EXISTS duration_ms INTEGER NULL;"))
    db.execute(text("ALTER TABLE notification_runs ADD COLUMN IF NOT EXISTS stats JSONB NULL;"))

    db.execute(text("CREATE INDEX IF NOT EXISTS ix_notification_runs_users_total ON notification_runs(users_total);"))

    # 3) index（観測用途で効く）
    db.execute(text("CREATE INDEX IF NOT EXISTS ix_notification_runs_status ON notification_runs(status);"))
    db.execute(text("CREATE INDEX IF NOT EXISTS ix_notification_runs_started_at ON notification_runs(started_at);"))

    db.commit()
    return {"status": "ok", "dialect": dialect}

@router.post("/migrate/notification-run-id-columns")
def migrate_notification_run_id_columns(db: Session = Depends(get_db)):
    """
    InAppNotification / TaskNotificationLog に run_id を追加
    """
    db.execute(text("""
        ALTER TABLE in_app_notifications
        ADD COLUMN IF NOT EXISTS run_id INTEGER;
    """))
    db.execute(text("""
        CREATE INDEX IF NOT EXISTS ix_inapp_run_id
        ON in_app_notifications (run_id);
    """))

    db.execute(text("""
        ALTER TABLE task_notification_logs
        ADD COLUMN IF NOT EXISTS run_id INTEGER;
    """))
    db.execute(text("""
        CREATE INDEX IF NOT EXISTS ix_task_notif_run_id
        ON task_notification_logs (run_id);
    """))

    db.commit()
    return {"status": "ok"}

@router.post("/migrate/backfill-task-notification-logs-deadline-at-send")
def backfill_task_notification_logs_deadline_at_send(db: Session = Depends(get_db)):
    """
    既存互換で nullable になっている task_notification_logs.deadline_at_send の NULL を埋める（1回だけ実行）
    - まず tasks.deadline で埋める
    - tasks.deadline が無い/参照できないものは sent_at で埋める
    目的：UNIQUE(user_id, task_id, deadline_at_send, offset_hours) の dedupe を完全に効かせる
    """
    dialect = db.bind.dialect.name if db.bind is not None else "unknown"

    if dialect == "postgresql":
        # ① tasks.deadline で埋める（task_id が残ってるもの）
        r1 = db.execute(
            text("""
            UPDATE task_notification_logs tnl
            SET deadline_at_send = t.deadline
            FROM tasks t
            WHERE tnl.deadline_at_send IS NULL
              AND tnl.task_id = t.id
              AND t.deadline IS NOT NULL;
            """)
        )

        # ② 残り（task無し/deadline無し）は sent_at で埋める
        r2 = db.execute(
            text("""
            UPDATE task_notification_logs
            SET deadline_at_send = sent_at
            WHERE deadline_at_send IS NULL;
            """)
        )

        # ③ 検算
        null_count = db.execute(
            text("SELECT COUNT(*) FROM task_notification_logs WHERE deadline_at_send IS NULL;")
        ).scalar() or 0

        db.commit()
        return {
            "status": "ok",
            "dialect": dialect,
            "filled_from_tasks": int(getattr(r1, "rowcount", 0) or 0),
            "filled_from_sent_at": int(getattr(r2, "rowcount", 0) or 0),
            "null_remaining": int(null_count),
        }

    # --- fallback（sqlite/dev壊れ防止）：Pythonで埋める ---
    # できるだけ同じ意味になるように埋める（ただし dev 用）
    rows = db.execute(
        text("""
       SELECT id, task_id, sent_at
        FROM task_notification_logs
        WHERE deadline_at_send IS NULL;
        """)
    ).all()
    if not rows:
        return {"status": "ok", "dialect": dialect, "updated": 0, "null_remaining": 0}

    updated = 0
    for (log_id, task_id, sent_at) in rows:
        deadline = None
        if task_id is not None:
            deadline = db.execute(
                text("SELECT deadline FROM tasks WHERE id = :tid"),
                {"tid": task_id},
            ).scalar()
        fill = deadline or sent_at
        db.execute(
            text("UPDATE task_notification_logs SET deadline_at_send = :v WHERE id = :id"),
            {"v": fill, "id": log_id},
        )
        updated += 1
    db.commit()
    null_count = db.execute(
        text("SELECT COUNT(*) FROM task_notification_logs WHERE deadline_at_send IS NULL;")
    ).scalar() or 0
    return {"status": "ok", "dialect": dialect, "updated": updated, "null_remaining": int(null_count)}

@router.get("/migrate/notification-runs/latest")
def get_latest_notification_run(db: Session = Depends(get_db)):
    """
    観測用（read-only）
    最新の NotificationRun を1件返す
    """
    run = (
        db.query(NotificationRun)
        .order_by(NotificationRun.started_at.desc())
        .first()
    )
    if not run:
        raise HTTPException(status_code=404, detail="not found")

    return {
        "id": run.id,
        "status": run.status,
        "error_summary": run.error_summary,
        "users_processed": run.users_processed,
        "due_candidates_total": run.due_candidates_total,
        "morning_candidates_total": run.morning_candidates_total,
        "inapp_created": run.inapp_created,
        "webpush_sent": run.webpush_sent,
        "webpush_failed": run.webpush_failed,
        "webpush_deactivated": run.webpush_deactivated,
        "line_sent": run.line_sent,
        "line_failed": run.line_failed,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        # GET契約には stats は含まれてない（ログの expected_keys に無い）ので入れない
    }

@router.get("/migrate/notification-runs")
def list_notification_runs(
    limit: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """
    観測用（read-only）
    最近の NotificationRun を返す
    """
    runs = (
        db.query(NotificationRun)
        .order_by(NotificationRun.started_at.desc())
        .limit(limit)
        .all()
    )
    return {
        "items": [
            {
                "id": r.id,
                "status": r.status,
                "stats": getattr(r, "stats", None),
                "error_summary": r.error_summary,
                "users_processed": r.users_processed,
                "due_candidates_total": r.due_candidates_total,
                "morning_candidates_total": r.morning_candidates_total,
                "inapp_created": r.inapp_created,
                "webpush_sent": r.webpush_sent,
                "webpush_failed": r.webpush_failed,
                "webpush_deactivated": r.webpush_deactivated,
                "line_sent": r.line_sent,
                "line_failed": r.line_failed,
                "started_at": r.started_at.isoformat() if r.started_at else None,
                "finished_at": r.finished_at.isoformat() if r.finished_at else None,
            }
            for r in runs
        ]
    }