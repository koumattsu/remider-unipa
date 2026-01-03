from sqlalchemy import Column, Integer, DateTime, String, JSON, Index
from sqlalchemy.sql import func
from app.db.base import Base

class ExportRun(Base):
    """
    Export 実行ログ（資産）
    - いつ / どの条件(kind,user_id,limit,from,to)で export を生成したか
    - export_hash を保存して改ざん検出・監査に耐える
    """
    __tablename__ = "export_runs"

    id = Column(Integer, primary_key=True, index=True)

    export_version = Column(Integer, nullable=False, default=1)

    kind = Column(String(16), nullable=False, index=True)     # "global" | "user"
    user_id = Column(Integer, nullable=True, index=True)

    from_ts = Column(DateTime(timezone=True), nullable=True)
    to_ts = Column(DateTime(timezone=True), nullable=True)

    limit = Column(Integer, nullable=False, default=1000)

    export_hash = Column(String(128), nullable=False, index=True)

    # 監査/再現用メタ（生テキストは載せない。範囲や件数など）
    meta = Column(JSON, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

    __table_args__ = (
        Index("ix_export_runs_kind_created", "kind", "created_at"),
        Index("ix_export_runs_user_created", "user_id", "created_at"),
    )
