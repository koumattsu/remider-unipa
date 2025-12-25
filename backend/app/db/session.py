# backend/app/db/session.py

from app.db.base import SessionLocal


def get_db():
    """データベースセッションの依存性注入"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
