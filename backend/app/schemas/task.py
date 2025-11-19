from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class TaskBase(BaseModel):
    title: str
    course_name: str
    deadline: datetime
    memo: Optional[str] = None


class TaskCreate(TaskBase):
    pass


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    course_name: Optional[str] = None
    deadline: Optional[datetime] = None
    memo: Optional[str] = None
    is_done: Optional[bool] = None


class TaskResponse(TaskBase):
    id: int
    user_id: int
    is_done: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

