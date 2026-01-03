# backend/app/core/config.py
from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import Optional, Union

class Settings(BaseSettings):
    APP_NAME: str = "UniPA Reminder App"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    DATABASE_URL: str = "sqlite:///./unipa_reminder.db"
    VAPID_PUBLIC_KEY: str = ""
    VAPID_PRIVATE_KEY: str = ""
    VAPID_SUBJECT: str = "mailto:admin@example.com"

    # ✅ 本番(frontend on render)もデフォで許可しておく
    #    Renderで環境変数CORS_ORIGINSを入れたらそっちが優先される
    CORS_ORIGINS: Union[str, list[str]] = (
        "https://unipa-reminder-frontend.onrender.com,"
        "http://localhost:5173,"
        "http://localhost:3000"
    )

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Union[str, list[str]]) -> list[str]:
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return ["http://localhost:5173", "http://localhost:3000"]

    LINE_CHANNEL_ACCESS_TOKEN: Optional[str] = None
    LINE_CHANNEL_SECRET: Optional[str] = None

    # ✅ 安全側デフォルト（本番事故を防ぐ）
    # ローカルで使うなら .env で DUMMY_AUTH_ENABLED=true を明示
    DUMMY_AUTH_ENABLED: bool = False
    DUMMY_USER_ID: int = 1

    LINE_LOGIN_CHANNEL_ID: str = ""
    LINE_LOGIN_CHANNEL_SECRET: str = ""
    LINE_LOGIN_REDIRECT_URI: str = ""

    @field_validator("LINE_LOGIN_REDIRECT_URI", mode="before")
    @classmethod
    def normalize_line_redirect_uri(cls, v: str) -> str:
        if v is None:
            return ""
        if not isinstance(v, str):
            v = str(v)
        uri = v.strip().replace("\r", "").replace("\n", "")
        if len(uri) >= 2 and ((uri[0] == '"' and uri[-1] == '"') or (uri[0] == "'" and uri[-1] == "'")):
            uri = uri[1:-1].strip()
        return uri

    FRONTEND_URL: str = "http://localhost:5173"
    SESSION_SECRET: str = ""
    FEATURE_HASH_SECRET: str = ""

    SESSION_COOKIE_NAME: str = "unipa_session"
    # ✅ cookie属性を一箇所に集約（auth/securityで必ずこれを使う）
    SESSION_COOKIE_PATH: str = "/"
    SESSION_COOKIE_DOMAIN: Optional[str] = None
    ENV: str = "development"

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
