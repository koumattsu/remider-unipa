# backend/app/db/base.py

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
import os

is_sqlite = settings.DATABASE_URL.startswith("sqlite")

# SQLite / Postgres の connect_args を分ける
connect_args = {}
if is_sqlite:
    connect_args = {"check_same_thread": False}
else:
    # ✅ Postgres: URLに sslmode が無い場合だけ require を補う（Neon等で必須になりがち）
    if "sslmode=" not in settings.DATABASE_URL:
        connect_args = {"sslmode": "require"}

engine_kwargs = {
    "pool_pre_ping": True,
}
if not is_sqlite:
    # ✅ ENVで調整可能（未設定なら現状互換のデフォルト）
    pool_size = int(os.getenv("DB_POOL_SIZE", "5"))
    max_overflow = int(os.getenv("DB_MAX_OVERFLOW", "5"))
    pool_timeout = int(os.getenv("DB_POOL_TIMEOUT", "30"))
    pool_recycle = int(os.getenv("DB_POOL_RECYCLE", "300"))

    engine_kwargs.update(
        {
            # 長時間アイドルで切れるのを避ける
            "pool_recycle": pool_recycle,
            # ✅ 接続枯渇対策：本番ではENVで引き上げら允许
            "pool_size": pool_size,
            "max_overflow": max_overflow,
            "pool_timeout": pool_timeout,
            # ✅ 直近利用の接続を優先し、死んだ接続を掴みにくくする
            "pool_use_lifo": True,
        }
    )

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    **engine_kwargs,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def init_db():
    """データベースを初期化（テーブル作成）"""
    # ✅ 集約import（追加モデルのimport漏れ事故を防ぐ）
    import app.models  # noqa: F401

    from sqlalchemy import text
    try:
        with engine.connect() as conn:
            before = conn.execute(
                text("SELECT count(*) FROM information_schema.tables WHERE table_type='BASE TABLE'")
            ).scalar()
        print("[INIT_DB] tables(before) =", before)
    except Exception as e:
        print("[INIT_DB] tables(before) check error:", e)
    try:
        Base.metadata.create_all(bind=engine)
        print("[INIT_DB] create_all done")
    except Exception as e:
        print("[INIT_DB] create_all ERROR:", e)
        raise
    try:
        with engine.connect() as conn:
            after = conn.execute(
                text("SELECT count(*) FROM information_schema.tables WHERE table_type='BASE TABLE'")
            ).scalar()
        print("[INIT_DB] tables(after) =", after)
    except Exception as e:
        print("[INIT_DB] tables(after) check error:", e)
