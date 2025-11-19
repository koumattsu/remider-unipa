from pydantic_settings import BaseSettings
from typing import Optional, Union
from pydantic import field_validator


class Settings(BaseSettings):
    """アプリケーション設定"""
    
    # アプリケーション基本設定
    APP_NAME: str = "UniPA Reminder App"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    
    # データベース設定
    DATABASE_URL: str = "sqlite:///./unipa_reminder.db"
    
    # CORS設定（環境変数ではカンマ区切り文字列、またはJSON配列として指定可能）
    CORS_ORIGINS: Union[str, list[str]] = "http://localhost:5173,http://localhost:3000"
    
    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Union[str, list[str]]) -> list[str]:
        """CORS_ORIGINSをリストに変換"""
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            # カンマ区切り文字列をリストに変換
            return [origin.strip() for origin in v.split(",")]
        return ["http://localhost:5173", "http://localhost:3000"]
    
    # LINE Messaging API設定（将来用）
    LINE_CHANNEL_ACCESS_TOKEN: Optional[str] = None
    LINE_CHANNEL_SECRET: Optional[str] = None
    
    # ダミー認証設定（開発用）
    DUMMY_AUTH_ENABLED: bool = True
    DUMMY_USER_ID: int = 1  # デフォルトのダミーユーザーID
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


settings = Settings()

