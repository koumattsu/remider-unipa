# backend/app/api/v1/endpoints/settings.py

from datetime import time
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
    # TODO: 将来 plan を導入したらここで分岐する（無料/有料）
    is_pro = False

    # 無料ユーザーは「1時間前通知のみ」許可（ON/OFFは [] or [1]）
    # ✅ reminder_offsets_hours が送られてきた時だけフィルタする（Noneなら既存維持）
    if (not is_pro) and (setting_data.reminder_offsets_hours is not None):
        incoming = setting_data.reminder_offsets_hours or []
        setting_data.reminder_offsets_hours = [h for h in incoming if h == 1]

    setting = (
        db.query(NotificationSetting)
        .filter(NotificationSetting.user_id == current_user.id)
        .first()
    )

    # ✅ 追加：全体通知の遷移を見る（OFF→ONのみ）
    prev_enable_webpush = bool(setting.enable_webpush) if setting else False
    # ✅ enable_webpush が None（未送信）なら既存値を維持（勝手にOFFにしない）
    incoming_enable_webpush = (
        bool(setting_data.enable_webpush)
        if setting_data.enable_webpush is not None
        else prev_enable_webpush
    )

    if setting:
        # ✅ None は「変更なし」扱いで既存維持（フロントが部分更新でも壊れない）
        if setting_data.reminder_offsets_hours is not None:
            setting.reminder_offsets_hours = setting_data.reminder_offsets_hours
        if setting_data.daily_digest_time is not None:
            setting.daily_digest_time = setting_data.daily_digest_time
        if setting_data.enable_morning_notification is not None:
            setting.enable_morning_notification = setting_data.enable_morning_notification

        # enable_webpush は incoming_enable_webpush で確定値を入れる
        setting.enable_webpush = incoming_enable_webpush
    else:
        # 新規作成（未指定は安全側のデフォルト）
        setting = NotificationSetting(
            user_id=current_user.id,
            reminder_offsets_hours=setting_data.reminder_offsets_hours or [],
            daily_digest_time=setting_data.daily_digest_time,
            enable_morning_notification=bool(setting_data.enable_morning_notification)
            if setting_data.enable_morning_notification is not None
            else False,
            enable_webpush=incoming_enable_webpush,
        )
        db.add(setting)

    # ✅ 全体通知 OFF→ON の瞬間に、タスク通知も全部ONに戻す（UX仕様）
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

@router.get("/notification", response_model=NotificationSettingResponse)
async def get_notification_setting(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """通知設定を取得（無ければ作成して返す）"""
    setting = (
        db.query(NotificationSetting)
        .filter(NotificationSetting.user_id == current_user.id)
        .first()
    )

    if setting:
        return setting

    # ✅ 無ければ作成（安全側デフォルト）
    setting = NotificationSetting(
        user_id=current_user.id,
        reminder_offsets_hours=[],
        daily_digest_time="08:00",  # フロントのフォールバックと整合
        enable_morning_notification=False,
        enable_webpush=False,
    )
    db.add(setting)
    db.commit()
    db.refresh(setting)
    return setting
