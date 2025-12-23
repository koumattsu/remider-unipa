# backend/app/api/v1/endpoints/admin_migrate.py

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.db.session import get_db
from app.db.base import init_db
from app.models.user import User
from app.models.notification_setting import NotificationSetting

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
