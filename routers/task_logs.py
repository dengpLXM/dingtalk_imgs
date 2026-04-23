from __future__ import annotations

import time
import traceback
from contextlib import contextmanager
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database import get_db, SessionLocal
from models import TaskLog
from schemas import TaskLogOut

router = APIRouter()

MAX_LOGS_PER_TASK = 100


@contextmanager
def log_execution(task_id: int, trigger: str, db: Optional[Session] = None):
    """Context manager that records a TaskLog entry.

    Usage::

        with log_execution(task.id, "manual", db) as entry:
            entry.stage = "script"
            ...run script...
            entry.stage = "send"
            ...send message...
            entry.success = True

    If an exception escapes, the log is saved with ``success=False`` and the
    traceback captured in ``detail``.
    """
    own_db = db is None
    if own_db:
        db = SessionLocal()

    entry = TaskLog(
        task_id=task_id,
        trigger=trigger,
        success=False,
        created_at=datetime.utcnow(),
    )
    t0 = time.perf_counter()
    try:
        yield entry
    except Exception as exc:
        entry.success = False
        entry.error = str(exc)
        entry.detail = traceback.format_exc()
        raise
    finally:
        entry.duration_ms = round((time.perf_counter() - t0) * 1000, 1)
        db.add(entry)
        db.commit()
        _prune(task_id, db)
        if own_db:
            db.close()


def _prune(task_id: int, db: Session) -> None:
    """Keep only the latest MAX_LOGS_PER_TASK logs per task."""
    count = db.query(TaskLog).filter(TaskLog.task_id == task_id).count()
    if count > MAX_LOGS_PER_TASK:
        oldest = (
            db.query(TaskLog)
            .filter(TaskLog.task_id == task_id)
            .order_by(TaskLog.created_at.asc())
            .limit(count - MAX_LOGS_PER_TASK)
            .all()
        )
        for log in oldest:
            db.delete(log)
        db.commit()


@router.get("/{task_id}/logs", response_model=list[TaskLogOut])
def get_task_logs(
    task_id: int,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    success: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
):
    q = db.query(TaskLog).filter(TaskLog.task_id == task_id)
    if success is not None:
        q = q.filter(TaskLog.success == success)
    return q.order_by(TaskLog.created_at.desc()).offset(offset).limit(limit).all()


@router.delete("/{task_id}/logs")
def clear_task_logs(task_id: int, db: Session = Depends(get_db)):
    count = db.query(TaskLog).filter(TaskLog.task_id == task_id).delete()
    db.commit()
    return {"ok": True, "deleted": count}
