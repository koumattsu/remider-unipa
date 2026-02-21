# backend/app/schemas/user.py

from pydantic import BaseModel
from typing import Optional

class UserBase(BaseModel):
    line_user_id: Optional[str] = None
    display_name: str
    university: Optional[str] = None
    plan: str = "free"

class UserCreate(UserBase):
    pass

class UserResponse(UserBase):
    id: int
    
    class Config:
        from_attributes = True
