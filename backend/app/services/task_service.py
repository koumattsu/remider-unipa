# app/services/task_service.py

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import Task
from app.schemas.task import TaskCreate


async def upsert_task_from_moodle(
    db: AsyncSession,
    *,
    user_id: int,
    task_in: TaskCreate,
) -> Task:
    """
    Moodle から取り込んだ課題を upsert する。
    user_id + course_name + title が同じタスクがあれば「更新」、なければ「新規作成」。
    """

    stmt = (
        select(Task)
        .where(
            Task.user_id == user_id,
            Task.course_name == task_in.course_name,
            Task.title == task_in.title,
        )
        .limit(1)
    )
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing:
        # 既存レコードを「最新の状態」に更新
        existing.deadline = task_in.deadline
        existing.memo = task_in.memo

        # created_at / updated_at は DB 側の server_default / onupdate に任せる
        await db.commit()
        await db.refresh(existing)
        return existing

    # なければ新規作成
    task = Task(
        user_id=user_id,
        title=task_in.title,
        course_name=task_in.course_name,
        deadline=task_in.deadline,
        memo=task_in.memo,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


async def upsert_tasks_from_moodle_list(
    db: AsyncSession,
    *,
    user_id: int,
    tasks_in: List[TaskCreate],
) -> int:
    """
    Moodle からパースした TaskCreate のリストを一括 upsert する。
    戻り値は「処理した件数」。
    """
    count = 0
    for task_in in tasks_in:
        await upsert_task_from_moodle(db, user_id=user_id, task_in=task_in)
        count += 1

    return count

async def get_tasks_for_user(
    db: AsyncSession,
    *,
    user_id: int,
) -> List[Task]:
    """
    ログインユーザーのタスク一覧を締切順で取得する。
    """
    stmt = (
        select(Task)
        .where(Task.user_id == user_id)
        .order_by(Task.deadline)
    )
    result = await db.execute(stmt)
    tasks = result.scalars().all()
    return list(tasks)


async def update_task_is_done(
    db: AsyncSession,
    *,
    user_id: int,
    task_id: int,
    is_done: bool,
) -> Optional[Task]:
    """
    特定タスクの is_done を更新する。
    見つからなければ None を返す（404 はエンドポイント側で返す想定）。
    """
    stmt = (
        select(Task)
        .where(
            Task.id == task_id,
            Task.user_id == user_id,
        )
        .limit(1)
    )
    result = await db.execute(stmt)
    task = result.scalar_one_or_none()

    if task is None:
        return None

    task.is_done = is_done
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task