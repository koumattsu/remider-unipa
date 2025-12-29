from sqlalchemy import (
    Column,
    Integer,
    ForeignKey,
    DateTime,
    String,
    UniqueConstraint,
    Index,
    JSON,
)
from sqlalchemy.sql import func
from app.db.base import Base


class OutcomeFeatureSnapshot(Base):
    """
    OutcomeLog（教師ラベル）に紐づく特徴量スナップショット（資産）
    - 生テキストは保持しない（匿名化・リーク防止）
    - feature_version で進化させる
    """
    __tablename__ = "outcome_feature_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "task_id",
            "deadline",
            "feature_version",
            name="uq_outcome_feature_user_task_deadline_ver",
        ),
        Index(
            "ix_outcome_feature_user_deadline",
            "user_id",
            "deadline",
        ),
        Index(
            "ix_outcome_feature_user_task_deadline",
            "user_id",
            "task_id",
            "deadline",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    task_id = Column(
        Integer,
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # OutcomeLog と同じdeadline（tasks.deadlineをコピーして固定）
    deadline = Column(DateTime(timezone=True), nullable=False, index=True)

    # 例: "v1"
    feature_version = Column(String(16), nullable=False, index=True)

    # 特徴量（匿名化済み・リークしない）
    features = Column(JSON, nullable=False)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )