# backend/app/schemas/weekly_task.py

from typing import Optional
from pydantic import BaseModel, Field

class WeeklyTaskBase(BaseModel):
    title: str = Field(..., description="タスクタイトル")
    course_name: Optional[str] = Field(None, description="授業名やカテゴリ")
    memo: Optional[str] = Field(None, description="メモ")

    # 0=月曜, 1=火曜, ... 6=日曜
    weekday: int = Field(..., ge=0, le=6, description="曜日 (0=月曜〜6=日曜)")

    # UI 上は 24:00 を許可する（24:00 → 翌日の 00:00 に正規化）
    time_hour: int = Field(0, ge=0, le=24, description="締切の時刻（時）")
    time_minute: int = Field(0, ge=0, le=59, description="締切の時刻（分）")

    is_active: bool = Field(True, description="有効かどうか")

class WeeklyTaskCreate(WeeklyTaskBase):
    pass

class WeeklyTaskUpdate(BaseModel):
    title: Optional[str] = None
    course_name: Optional[str] = None
    memo: Optional[str] = None
    weekday: Optional[int] = Field(None, ge=0, le=6)
    time_hour: Optional[int] = Field(None, ge=0, le=24)
    time_minute: Optional[int] = Field(None, ge=0, le=59)
    is_active: Optional[bool] = None

class WeeklyTaskResponse(WeeklyTaskBase):
    id: int

    class Config:
        from_attributes = True
