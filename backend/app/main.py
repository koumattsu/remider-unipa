# backend/app/main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.v1.api import api_router
from app.api.v1.endpoints.line_webhook import router as line_webhook_router
from app.db.base import init_db
from app.db.base import engine, Base
from sqlalchemy import text

def create_tables_if_needed() -> None:
    try:
        # どこに繋いでるかを確定（パスワードは出さない）
        url = engine.url
        safe = f"{url.drivername}://{url.username}@{url.host}:{url.port}/{url.database}"
        print("[BOOT] ENV =", settings.ENV)
        print("[BOOT] AUTO_INIT_DB =", settings.AUTO_INIT_DB)
        print("[BOOT] DB =", safe)
        # models import が効いてるか（Baseに何テーブル載ってるか）
        import app.models  # noqa
        print("[BOOT] metadata tables =", len(Base.metadata.tables))
        # Neon/PG 側の実体（DB名・schema・search_path）を確定
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT current_database(), current_schema(), current_user, current_setting('search_path')")
            ).fetchone()
        print("[BOOT] pg =", row)
    except Exception as e:
        print("[BOOT] debug error:", e)

    # ✅ 起動時DDLは本番で事故りやすいのでデフォOFF（必要時のみON）
    if settings.AUTO_INIT_DB:
        init_db()

def get_application() -> FastAPI:
    create_tables_if_needed()

    app = FastAPI(
        title="UNIPA Reminder Backend",
        description="UNIPA / Moodle 課題リマインダー用バックエンド（FastAPI）",
        version="0.1.0",
    )

    # ✅ config.py の validator で list[str] になってる前提
    origins = settings.CORS_ORIGINS

    # 念のため FRONTEND_URL も許可に入れておく（入ってなければ追加）
    frontend_origin = (settings.FRONTEND_URL or "").strip().rstrip("/")
    if frontend_origin and frontend_origin not in origins:
        origins = [*origins, frontend_origin]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router, prefix="/api/v1")
    app.include_router(line_webhook_router, prefix="/line", tags=["line"])

    @app.get("/health")
    async def health_check():
        return {"ok": True}

    @app.get("/build")
    async def build_info():
        # ここは落ちてもサービス死なない（ヘルスとは分離）
        return {
            "env": settings.ENV,
            "build": settings.BUILD_ID,
            "version": settings.APP_VERSION,
        }
    return app

app = get_application()