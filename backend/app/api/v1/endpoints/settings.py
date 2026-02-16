# backend/app/api/v1/endpoints/settings.py

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.notification_setting import NotificationSetting
from app.models.task import Task
from app.schemas.notification_setting import (
    NotificationSettingCreate,
    NotificationSettingUpdate,
    NotificationSettingResponse,
)

router = APIRouter()

@router.post("/notification", response_model=NotificationSettingResponse)
async def create_or_update_notification_setting(
    request: Request,
    setting_data: NotificationSettingUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """通知設定を作成または更新"""
    is_pro = False

    if not is_pro:
        incoming = setting_data.reminder_offsets_hours or []
        setting_data.reminder_offsets_hours = [h for h in incoming if h == 1]

    setting = (
        db.query(NotificationSetting)
        .filter(NotificationSetting.user_id == current_user.id)
        .first()
    )

    # ✅ 追加：全体通知の遷移を見る（OFF→ONのみ）
    prev_enable_webpush = bool(getattr(setting, "enable_webpush", False)) if setting else False
    incoming_enable_webpush = bool(setting_data.enable_webpush)

    if setting:
        setting.reminder_offsets_hours = setting_data.reminder_offsets_hours
        setting.daily_digest_time = setting_data.daily_digest_time
        setting.enable_morning_notification = setting_data.enable_morning_notification
        setting.enable_webpush = setting_data.enable_webpush
    else:
        setting = NotificationSetting(
            user_id=current_user.id,
            reminder_offsets_hours=setting_data.reminder_offsets_hours,
            daily_digest_time=setting_data.daily_digest_time,
            enable_morning_notification=setting_data.enable_morning_notification,
            enable_webpush=setting_data.enable_webpush,
        )
        db.add(setting)

    # ✅ 全体通知 OFF→ON の瞬間に、タスク通知も全部ONに戻す
    if (not prev_enable_webpush) and incoming_enable_webpush:
        db.query(Task).filter(
            Task.user_id == current_user.id,
            Task.deleted_at.is_(None),
        ).update(
            {Task.should_notify: True},
            synchronize_session=False,
        )

    db.commit()
    db.refresh(setting)
    return setting

@router.post("/notification", response_model=NotificationSettingResponse)
async def create_or_update_notification_setting(
    request: Request,
    setting_data: NotificationSettingUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """通知設定を作成または更新"""
    # TODO: 将来 plan を導入したらここで分岐する（無料/有料）
    is_pro = False

    # 無料ユーザーは「1時間前通知のみ」許可（ON/OFFは [] or [1]）
    if not is_pro:
        incoming = setting_data.reminder_offsets_hours or []
        setting_data.reminder_offsets_hours = [h for h in incoming if h == 1]

    setting = (
        db.query(NotificationSetting)
        .filter(NotificationSetting.user_id == current_user.id)
        .first()
    )

    if setting:
        # ★ ここでフラグも含めて全部上書きする
        setting.reminder_offsets_hours = setting_data.reminder_offsets_hours
        setting.daily_digest_time = setting_data.daily_digest_time
        setting.enable_morning_notification = (
            setting_data.enable_morning_notification
        )
        setting.enable_webpush = setting_data.enable_webpush
    else:
        # 新規作成
        setting = NotificationSetting(
            user_id=current_user.id,
            reminder_offsets_hours=setting_data.reminder_offsets_hours,
            daily_digest_time=setting_data.daily_digest_time,
            enable_morning_notification=setting_data.enable_morning_notification,
            enable_webpush=setting_data.enable_webpush,
        )
        db.add(setting)

    db.commit()
    db.refresh(setting)
    return setting
