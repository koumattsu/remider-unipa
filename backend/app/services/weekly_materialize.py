from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.task import Task
from app.models.weekly_task import WeeklyTask

JST = timezone(timedelta(hours=9))


def materialize_weekly_tasks_for_user(
    db: Session,
    user_id: int,
    days: int = 7,
) -> dict:
    """
    向こう days 日分の weekly_tasks を tasks に実体化する（存在してたら作らない）

    生成ルール（DoD用に確定）:
    - (user_id, weekly_task_id, deadline) が同一なら作らない（増殖防止）
    - deadline は JST aware datetime を保存
    - 生成時は is_done=False, should_notify=True（最小版）
    """
    templates = (
        db.query(WeeklyTask)
        .filter(WeeklyTask.user_id == user_id, WeeklyTask.is_active == True)  # noqa: E712
        .all()
    )

    created = 0
    skipped = 0

    today = datetime.now(JST).date()

    for offset in range(days):
        day = today + timedelta(days=offset)
        weekday_mon0 = day.weekday()  # 0=月..6=日

        for tpl in templates:
            if tpl.weekday != weekday_mon0:
                continue

            deadline_dt = datetime(
                day.year, day.month, day.day,
                tpl.time_hour or 0,
                tpl.time_minute or 0,
                0,
                tzinfo=JST,
            )

            exists = (
                db.query(Task.id)
                .filter(
                    and_(
                        Task.user_id == user_id,
                        Task.weekly_task_id == tpl.id,
                        Task.deadline == deadline_dt,
                    )
                )
                .first()
            )
            if exists:
                skipped += 1
                continue

            task = Task(
                user_id=user_id,
                title=tpl.title,
                course_name=tpl.course_name or "",
                memo=tpl.memo or "",
                deadline=deadline_dt,
                is_done=False,
                should_notify=True,
                weekly_task_id=tpl.id,
            )
            db.add(task)
            created += 1

    db.commit()
    return {"created": created, "skipped": skipped}
