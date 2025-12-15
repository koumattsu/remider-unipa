# backend/app/api/v1/endpoints/auth.py

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.user import UserResponse

router = APIRouter(
    tags=["auth"],  # ← prefix は消して tags だけでOK
)

@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    """
    現在ログイン中のユーザー情報を取得
    """
    return UserResponse.model_validate(current_user)
