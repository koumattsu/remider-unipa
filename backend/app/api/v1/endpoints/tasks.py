from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.task import Task
from app.schemas.task import TaskCreate, TaskUpdate, TaskResponse

router = APIRouter()


@router.get("/", response_model=List[TaskResponse])
async def get_tasks(
    start_date: Optional[datetime] = Query(None, description="開始日時（フィルタ）"),
    end_date: Optional[datetime] = Query(None, description="終了日時（フィルタ）"),
    is_done: Optional[bool] = Query(None, description="完了状態でフィルタ"),
    skip: int = Query(0, ge=0, description="スキップ件数"),
    limit: int = Query(100, ge=1, le=1000, description="最大取得件数"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """課題一覧を取得"""
    filters = [Task.user_id == current_user.id]

    if start_date:
        filters.append(Task.deadline >= start_date)
    if end_date:
        filters.append(Task.deadline <= end_date)
    if is_done is not None:
        filters.append(Task.is_done == is_done)

    query = (
        db.query(Task)
        .filter(*filters)
        .order_by(Task.deadline.asc())
        .offset(skip)
        .limit(limit)
    )

    tasks = query.all()
    return tasks


@router.post("/", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    task_data: TaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """課題を新規作成"""
    task = Task(
        user_id=current_user.id,
        **task_data.model_dump(),
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.patch("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: int,
    task_data: TaskUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """課題を更新"""
    task = (
        db.query(Task)
        .filter(and_(Task.id == task_id, Task.user_id == current_user.id))
        .first()
    )

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="課題が見つかりません",
        )

    update_data = task_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(task, field, value)

    db.commit()
    db.refresh(task)
    return task


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """課題を削除"""
    task = (
        db.query(Task)
        .filter(and_(Task.id == task_id, Task.user_id == current_user.id))
        .first()
    )

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="課題が見つかりません",
        )

    db.delete(task)
    db.commit()
    return None
