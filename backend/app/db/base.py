# backend/app/db/base.py

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

is_sqlite = settings.DATABASE_URL.startswith("sqlite")

# SQLite用の設定（PostgreSQLに移行しやすいようURLを設定から取得）
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def init_db():
    """データベースを初期化（テーブル作成）"""
    # ✅ 集約import（追加モデルのimport漏れ事故を防ぐ）
    import app.models  # noqa: F401

    Base.metadata.create_all(bind=engine)

