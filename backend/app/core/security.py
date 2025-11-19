from fastapi import Request, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional
from app.models.user import User
from app.core.config import settings


async def get_current_user(
    request: Request,
    db: Session
) -> Optional[User]:
    """
    現在のユーザーを取得する（ダミー認証版）
    
    開発時はリクエストヘッダの `X-Dummy-User-Id` を見てユーザーを取得。
    将来的にLINEログインの認証に置き換える。
    """
    if not settings.DUMMY_AUTH_ENABLED:
        # 本番環境では実際の認証トークンを検証
        # TODO: LINEログインの認証処理を実装
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="認証が必要です"
        )
    
    # ダミー認証：ヘッダーからユーザーIDを取得
    dummy_user_id = request.headers.get("X-Dummy-User-Id")
    user_id = int(dummy_user_id) if dummy_user_id else settings.DUMMY_USER_ID
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        # ダミーユーザーが存在しない場合は作成
        user = User(
            id=user_id,
            line_user_id=f"dummy_line_{user_id}",
            display_name=f"ダミーユーザー{user_id}",
            university="テスト大学",
            plan="free"
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    
    return user


def require_auth(func):
    """認証が必要なエンドポイント用デコレータ（簡易版）"""
    return func

