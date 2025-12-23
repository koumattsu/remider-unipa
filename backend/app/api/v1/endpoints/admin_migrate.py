# backend/app/api/v1/endpoints/admin_migrate.py

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
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
