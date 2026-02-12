# backend/app/api/v1/endpoints/weekly_tasks.py

from datetime import date, datetime, timedelta, timezone
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import and_
from fastapi import Body

from app.services.weekly_materialize import materialize_weekly_tasks_for_user

from app.models.task import Task
from app.db.session import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.weekly_task import WeeklyTask
from app.schemas.weekly_task import (
    WeeklyTaskCreate,
    WeeklyTaskUpdate,
    WeeklyTaskResponse,
)

router = APIRouter()

JST = timezone(timedelta(hours=9))

def normalize_weekly_time(
    weekday: int,
    time_hour: int,
    time_minute: int,
):
    """
    UI から送られてきた曜日/時刻を DB 保存用に正規化する。

    - 24:00 が指定された場合 → weekday+1 の 00:00 に変換
      （例: 月曜(0)の24:00 → 火曜(1)の0:00）
    - 24:xx（00分以外）は不正として 400 を返す
    """
    if time_hour == 24:
        if time_minute != 0:
            # 念のためガード（UIでは24:00しか出さない想定）
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="24時は 24:00 のみ指定できます（24:xx は無効です）",
            )
        weekday = (weekday + 1) % 7
        time_hour = 0

    return weekday, time_hour, time_minute

@router.get("", response_model=List[WeeklyTaskResponse])
@router.get("/", response_model=List[WeeklyTaskResponse])
def list_weekly_tasks(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    ログインユーザーの毎週タスクテンプレ一覧を取得
    """
    tasks = (
        db.query(WeeklyTask)
        .filter(WeeklyTask.user_id == current_user.id)
        .order_by(WeeklyTask.weekday.asc(), WeeklyTask.time_hour.asc(), WeeklyTask.time_minute.asc())
        .all()
    )
    return tasks

@router.post("/", response_model=WeeklyTaskResponse, status_code=status.HTTP_201_CREATED)
def create_weekly_task(
    body: WeeklyTaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    毎週タスクテンプレを新規作成
    """

    # 24:00 → 翌日0:00 への正規化
    weekday, time_hour, time_minute = normalize_weekly_time(
        body.weekday,
        body.time_hour,
        body.time_minute,
    )

    task = WeeklyTask(
        user_id=current_user.id,
        title=body.title,
        course_name=body.course_name,
        memo=body.memo,
        weekday=weekday,
        time_hour=time_hour,
        time_minute=time_minute,
        is_active=body.is_active,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task

@router.post("/materialize")
def materialize_weekly_tasks_to_real_tasks(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    向こう7日分の weekly_tasks を tasks に実体化する（存在してたら作らない）
    ※ Dashboard 初期ロードで呼ぶ想定
    """
    result = materialize_weekly_tasks_for_user(db, user_id=current_user.id, days=7)
    return result

@router.patch("/{weekly_task_id}", response_model=WeeklyTaskResponse)
def update_weekly_task(
    weekly_task_id: int,
    body: WeeklyTaskUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    毎週タスクテンプレを更新
    """
    task = (
        db.query(WeeklyTask)
        .filter(
            WeeklyTask.id == weekly_task_id,
            WeeklyTask.user_id == current_user.id,
        )
        .first()
    )

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="毎週タスクが見つかりません",
        )

    update_data = body.model_dump(exclude_unset=True)

    # 曜日 or 時刻のいずれかが更新される場合は、まとめて正規化する
    if any(k in update_data for k in ("weekday", "time_hour", "time_minute")):
        weekday = update_data.get("weekday", task.weekday)
        time_hour = update_data.get("time_hour", task.time_hour)
        time_minute = update_data.get("time_minute", task.time_minute)

        weekday, time_hour, time_minute = normalize_weekly_time(
            weekday,
            time_hour,
            time_minute,
        )

        task.weekday = weekday
        task.time_hour = time_hour
        task.time_minute = time_minute

        # このあと for で二重に上書きしないように消しておく
        for key in ("weekday", "time_hour", "time_minute"):
            update_data.pop(key, None)


    for field, value in update_data.items():
        setattr(task, field, value)

    db.commit()
    db.refresh(task)
    return task


@router.delete("/{weekly_task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_weekly_task(
    weekly_task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    毎週タスクテンプレを削除
    """
    task = (
        db.query(WeeklyTask)
        .filter(
            WeeklyTask.id == weekly_task_id,
            WeeklyTask.user_id == current_user.id,
        )
        .first()
    )

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="毎週タスクが見つかりません",
        )

    db.delete(task)
    db.commit()
    return None