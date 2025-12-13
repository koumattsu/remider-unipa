# backend/scripts/migrate_sqlite_to_postgres.py
import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# app を import できるようにパス調整（backend/ から実行想定）
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db.base import Base
from app.models.user import User
from app.models.weekly_task import WeeklyTask
from app.models.task import Task
from app.models.notification_setting import NotificationSetting
from app.models.task_notification_override import TaskNotificationOverride
from app.models.task_notification_log import TaskNotificationLog


SQLITE_URL = "sqlite:///./unipa_reminder.db"
POSTGRES_URL = os.getenv("DATABASE_URL")  # External Postgres (sslmode=require) を想定


def die(msg: str) -> None:
    print(f"[ERROR] {msg}")
    sys.exit(1)


def reset_sequences(pg_engine):
    """
    id を手動で挿入した後、Postgresの連番（sequence）を最大idに合わせる
    """
    seq_tables = [
        "users",
        "weekly_tasks",
        "tasks",
        "notification_settings",
        "task_notification_overrides",
        "task_notification_logs",
    ]
    with pg_engine.begin() as conn:
        for t in seq_tables:
            # テーブルに 0件だと setval が NULL になるので COALESCE
            conn.execute(text(f"""
                SELECT setval(
                    pg_get_serial_sequence('{t}', 'id'),
                    COALESCE((SELECT MAX(id) FROM {t}), 1),
                    true
                );
            """))


def main():
    if not POSTGRES_URL:
        die("DATABASE_URL が未設定です。.env に External Postgres URL (sslmode=require) を設定してください。")

    # エンジン作成
    sqlite_engine = create_engine(SQLITE_URL, connect_args={"check_same_thread": False})
    pg_engine = create_engine(POSTGRES_URL, pool_pre_ping=True)

    SqliteSession = sessionmaker(bind=sqlite_engine, autocommit=False, autoflush=False)
    PgSession = sessionmaker(bind=pg_engine, autocommit=False, autoflush=False)

    sqlite_db = SqliteSession()
    pg_db = PgSession()

    try:
        # 念のため Postgres 側テーブルがあるか（create_all済みの前提）
        Base.metadata.create_all(bind=pg_engine)

        # 二重実行事故防止：Postgres側に既にデータがあれば止める
        pg_users = pg_db.query(User).count()
        if pg_users > 0:
            die(f"Postgres側に既に users が {pg_users} 件あります。二重移行防止のため中断します。空DBで実行してください。")

        # ---------- 1) users ----------
        users = sqlite_db.query(User).order_by(User.id).all()
        for u in users:
            pg_db.add(User(
                id=u.id,
                line_user_id=u.line_user_id,
                display_name=u.display_name,
                university=u.university,
                plan=u.plan,
            ))
        pg_db.commit()
        print(f"[OK] users: {len(users)}")

        # ---------- 2) weekly_tasks ----------
        weekly_tasks = sqlite_db.query(WeeklyTask).order_by(WeeklyTask.id).all()
        for wt in weekly_tasks:
            pg_db.add(WeeklyTask(
                id=wt.id,
                user_id=wt.user_id,
                title=wt.title,
                course_name=wt.course_name,
                memo=wt.memo,
                weekday=wt.weekday,
                time_hour=wt.time_hour,
                time_minute=wt.time_minute,
                is_active=wt.is_active,
            ))
        pg_db.commit()
        print(f"[OK] weekly_tasks: {len(weekly_tasks)}")

        # ---------- 3) tasks ----------
        tasks = sqlite_db.query(Task).order_by(Task.id).all()
        for t in tasks:
            pg_db.add(Task(
                id=t.id,
                user_id=t.user_id,
                weekly_task_id=t.weekly_task_id,
                title=t.title,
                course_name=t.course_name,
                deadline=t.deadline,
                memo=t.memo,
                is_done=t.is_done,
                should_notify=t.should_notify,
                created_at=t.created_at,
                updated_at=t.updated_at,
            ))
        pg_db.commit()
        print(f"[OK] tasks: {len(tasks)}")

        # ---------- 4) notification_settings ----------
        settings = sqlite_db.query(NotificationSetting).order_by(NotificationSetting.id).all()
        for s in settings:
            pg_db.add(NotificationSetting(
                id=s.id,
                user_id=s.user_id,
                reminder_offsets_hours=s.reminder_offsets_hours,
                daily_digest_time=s.daily_digest_time,
                enable_morning_notification=s.enable_morning_notification,
            ))
        pg_db.commit()
        print(f"[OK] notification_settings: {len(settings)}")

        # ---------- 5) task_notification_overrides ----------
        overrides = sqlite_db.query(TaskNotificationOverride).order_by(TaskNotificationOverride.id).all()
        for o in overrides:
            pg_db.add(TaskNotificationOverride(
                id=o.id,
                user_id=o.user_id,
                task_id=o.task_id,
                enable_morning=o.enable_morning,
                reminder_offsets_hours=o.reminder_offsets_hours,
                created_at=o.created_at,
                updated_at=o.updated_at,
            ))
        pg_db.commit()
        print(f"[OK] task_notification_overrides: {len(overrides)}")

        # ---------- 6) task_notification_logs ----------
        logs = sqlite_db.query(TaskNotificationLog).order_by(TaskNotificationLog.id).all()
        for l in logs:
            pg_db.add(TaskNotificationLog(
                id=l.id,
                user_id=l.user_id,
                task_id=l.task_id,
                offset_hours=l.offset_hours,
                sent_at=l.sent_at,
            ))
        pg_db.commit()
        print(f"[OK] task_notification_logs: {len(logs)}")

        # sequence を合わせる
        reset_sequences(pg_engine)
        print("[OK] sequences reset")

        print("\n✅ Migration completed successfully!")

    finally:
        sqlite_db.close()
        pg_db.close()


if __name__ == "__main__":
    main()
