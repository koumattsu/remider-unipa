# backend/app/core/config.py

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
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

    # ===== LINE Login (OAuth) =====
    LINE_LOGIN_CHANNEL_ID: str = ""
    LINE_LOGIN_CHANNEL_SECRET: str = ""
    LINE_LOGIN_REDIRECT_URI: str = ""

    # ===== Frontend =====
    FRONTEND_URL: str = "http://localhost:5173"

    # ===== Session =====
    SESSION_SECRET: str = ""

    # ===== Cookie settings =====
    SESSION_COOKIE_NAME: str = "unipa_session"
    ENV: str = "development"  # "production" で本番扱い

    @property
    def SESSION_COOKIE_SECURE(self) -> bool:
        return self.ENV == "production"

    @property
    def SESSION_COOKIE_SAMESITE(self) -> str:
        return "none" if self.ENV == "production" else "lax"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"

settings = Settings()

@field_validator("LINE_LOGIN_REDIRECT_URI", mode="before")
@classmethod
def normalize_line_redirect_uri(cls, v: str) -> str:
    if v is None:
        return ""
    if not isinstance(v, str):
        return str(v)

    uri = v.strip()

        # たまに貼り付けで混ざるやつを除去（ここが効く）
    uri = uri.replace("\r", "").replace("\n", "")

        # 環境変数にダブルクォート付きで入れてしまったケース対策
    if len(uri) >= 2 and ((uri[0] == '"' and uri[-1] == '"') or (uri[0] == "'" and uri[-1] == "'")):
        uri = uri[1:-1].strip()

    return uri
