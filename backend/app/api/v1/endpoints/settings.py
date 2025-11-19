from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.notification_setting import NotificationSetting
from app.schemas.notification_setting import (
    NotificationSettingCreate,
    NotificationSettingUpdate,
    NotificationSettingResponse
)
from fastapi import Request

router = APIRouter()


@router.get("/notification", response_model=NotificationSettingResponse)
async def get_notification_setting(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """通知設定を取得（存在しない場合はデフォルト値を返す）"""
    setting = db.query(NotificationSetting).filter(
        NotificationSetting.user_id == current_user.id
    ).first()
    
    if not setting:
        # デフォルト設定を作成して返す
        setting = NotificationSetting(
            user_id=current_user.id,
            reminder_offsets_hours=[24, 3, 1],
            daily_digest_time="08:00"
        )
        db.add(setting)
        db.commit()
        db.refresh(setting)
    
    return setting


@router.post("/notification", response_model=NotificationSettingResponse)
async def create_or_update_notification_setting(
    request: Request,
    setting_data: NotificationSettingUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """通知設定を作成または更新"""
    setting = db.query(NotificationSetting).filter(
        NotificationSetting.user_id == current_user.id
    ).first()
    
    if setting:
        # 更新
        setting.reminder_offsets_hours = setting_data.reminder_offsets_hours
        setting.daily_digest_time = setting_data.daily_digest_time
    else:
        # 新規作成
        setting = NotificationSetting(
            user_id=current_user.id,
            **setting_data.model_dump()
        )
        db.add(setting)
    
    db.commit()
    db.refresh(setting)
    return setting

