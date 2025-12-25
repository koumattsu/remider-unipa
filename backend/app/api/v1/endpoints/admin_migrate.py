# backend/app/api/v1/endpoints/admin_migrate.py

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
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
