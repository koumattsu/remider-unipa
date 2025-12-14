# backend/app/api/v1/endpoints/task_notification_override.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.models.task import Task
from app.models.task_notification_override import TaskNotificationOverride
from app.schemas.task_notification_override import (
    TaskNotificationOverrideRead,
    TaskNotificationOverrideUpdate,
)
from app.api.v1.endpoints.tasks import get_user_from_line_id

router = APIRouter()


# ================================
# ★ 追加するのはこれだけ（一覧GET）
# ================================
@router.get(
    "/notification-overrides",
    response_model=list[TaskNotificationOverrideRead],
)
def list_task_notification_overrides(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_user_from_line_id),
):
    """
    このユーザーの task_notification_overrides を一覧で取得
    Dashboard 初期ロード用
    """
    return (
        db.query(TaskNotificationOverride)
        .filter(TaskNotificationOverride.user_id == current_user.id)
        .all()
    )


# ================================
# ↓↓↓ 以下は「今のコードそのまま」
# ================================

@router.get(
    "/{task_id}/notification-override",
    response_model=TaskNotificationOverrideRead | None,
)
def get_task_notification_override(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_user_from_line_id),
):
    """
    このユーザー & この task_id 用の override を1件だけ取得
    なければ None を返す
    """
    override = (
        db.query(TaskNotificationOverride)
        .filter(
            TaskNotificationOverride.task_id == task_id,
            TaskNotificationOverride.user_id == current_user.id,
        )
        .first()
    )
    return override


@router.put(
    "/{task_id}/notification-override",
    response_model=TaskNotificationOverrideRead,
)
def upsert_task_notification_override(
    task_id: int,
    payload: TaskNotificationOverrideUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_user_from_line_id),
):
    """
    このタスク専用の通知設定を upsert する
    """
    # 1. タスクが自分のものか確認
    task = (
        db.query(Task)
        .filter(Task.id == task_id, Task.user_id == current_user.id)
        .first()
    )
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # 2. 既存の override があるか確認
    override = (
        db.query(TaskNotificationOverride)
        .filter(
            TaskNotificationOverride.task_id == task_id,
            TaskNotificationOverride.user_id == current_user.id,
        )
        .first()
    )

    # 3. なければ新規作成
    if override is None:
        override = TaskNotificationOverride(
            task_id=task_id,
            user_id=current_user.id,
        )
        db.add(override)

    # 4. 値を上書き（None = 全体設定に従う）
    override.enable_morning = payload.enable_morning
    override.reminder_offsets_hours = payload.reminder_offsets_hours

    db.commit()
    db.refresh(override)
    return override
