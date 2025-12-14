# backend/app/schemas/task.py

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

class MoodleHtmlImportRequest(BaseModel):
    """
    Moodle タイムラインHTMLを一括インポートするためのリクエストスキーマ
    """
    html: str

class TaskBase(BaseModel):
    """
    タスクの共通項目
    """
    title: str
    course_name: str
    deadline: datetime
    memo: Optional[str] = None
    # 👇 WeeklyTask 由来ならそのID（普通のタスクは None）
    weekly_task_id: Optional[int] = None
    should_notify: Optional[bool] = True

class TaskCreate(TaskBase):
    """
    タスク作成用スキーマ（クライアント → サーバー）
    """
    pass

class TaskUpdate(BaseModel):
    """
    タスク更新用スキーマ（部分更新もOK）
    """
    title: Optional[str] = None
    course_name: Optional[str] = None
    deadline: Optional[datetime] = None
    memo: Optional[str] = None
    is_done: Optional[bool] = None
    weekly_task_id: Optional[int] = None
    should_notify: Optional[bool] = None

class TaskResponse(TaskBase):
    """
    タスクのレスポンス用スキーマ（サーバー → クライアント）
    """
    id: int
    user_id: int
    is_done: bool
    created_at: datetime
    updated_at: datetime

    # Pydantic v2 の ORM モード相当
    model_config = ConfigDict(from_attributes=True)