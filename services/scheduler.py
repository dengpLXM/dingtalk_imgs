"""APScheduler-based cron scheduler for tasks."""

import asyncio
import logging
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from database import SessionLocal
from models import Task

log = logging.getLogger("scheduler")

scheduler = AsyncIOScheduler(timezone="Asia/Shanghai")

_JOB_PREFIX = "task_"


def _job_id(task_id: int) -> str:
    return f"{_JOB_PREFIX}{task_id}"


async def _execute_task(task_id: int) -> None:
    """Run a single task inside the scheduler (no request context)."""
    from services.executor import run_script, render_template, render_html_template
    from services.dingtalk import send_message
    from services.html_renderer import render_html_to_image
    from services.image_host import upload_image
    from routers.task_logs import log_execution

    db = SessionLocal()
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task or not task.enabled:
            return

        log.info("Scheduler executing task %s [%s]", task.id, task.name)

        with log_execution(task.id, "scheduled", db) as log_entry:
            try:
                log_entry.stage = "script"
                result, _ = run_script(
                    task.script.content,
                    task.script.mongo_config,
                    task.script.script_format,
                )

                if task.msg_type == "image":
                    log_entry.stage = "template"
                    html = render_html_template(task.message_template, result)
                    log_entry.stage = "image_render"
                    img_bytes, _, _ = await render_html_to_image(html)
                    log_entry.stage = "upload"
                    img_url = upload_image(img_bytes, task.id)
                    log_entry.stage = "send"
                    send_message(
                        task.bot,
                        "image",
                        img_url,
                        image_intro_text=task.image_message_text,
                        at_all=task.at_all,
                    )
                else:
                    log_entry.stage = "template"
                    message = render_template(task.message_template, result)
                    log_entry.stage = "send"
                    send_message(task.bot, task.msg_type, message, at_all=task.at_all)

                task.last_run_result = "成功（定时）"
                log_entry.success = True
                log_entry.stage = "ok"
            except Exception as e:
                log.exception("Scheduled task %s failed", task_id)
                task.last_run_result = f"失败（定时）: {e}"
                log_entry.error = str(e)
                import traceback as tb
                log_entry.detail = tb.format_exc()

        task.last_run_at = datetime.utcnow()
        db.commit()
    finally:
        db.close()


def sync_jobs() -> None:
    """Read all tasks from DB and sync scheduler jobs accordingly."""
    db = SessionLocal()
    try:
        tasks = db.query(Task).all()
        existing_ids = {
            job.id for job in scheduler.get_jobs() if job.id.startswith(_JOB_PREFIX)
        }
        wanted_ids: set[str] = set()

        for task in tasks:
            jid = _job_id(task.id)
            wanted_ids.add(jid)

            if not task.enabled or not task.cron_expression:
                if jid in existing_ids:
                    scheduler.remove_job(jid)
                continue

            try:
                trigger = CronTrigger.from_crontab(
                    task.cron_expression, timezone="Asia/Shanghai"
                )
            except ValueError:
                log.warning(
                    "Task %s has invalid cron '%s', skipping",
                    task.id,
                    task.cron_expression,
                )
                if jid in existing_ids:
                    scheduler.remove_job(jid)
                continue

            if jid in existing_ids:
                scheduler.reschedule_job(jid, trigger=trigger)
            else:
                scheduler.add_job(
                    _execute_task,
                    trigger=trigger,
                    args=[task.id],
                    id=jid,
                    name=task.name,
                    replace_existing=True,
                )

        for jid in existing_ids - wanted_ids:
            scheduler.remove_job(jid)

        log.info("Scheduler synced: %d active jobs", len(scheduler.get_jobs()))
    finally:
        db.close()


def get_job_status() -> list[dict]:
    """Return a list of scheduled jobs with next run time."""
    result = []
    for job in scheduler.get_jobs():
        if not job.id.startswith(_JOB_PREFIX):
            continue
        task_id = int(job.id.removeprefix(_JOB_PREFIX))
        next_run = job.next_run_time
        result.append({
            "task_id": task_id,
            "job_id": job.id,
            "name": job.name,
            "next_run_at": next_run.isoformat() if next_run else None,
        })
    return result


def start() -> None:
    sync_jobs()
    scheduler.start()
    log.info("Scheduler started")


def shutdown() -> None:
    scheduler.shutdown(wait=False)
    log.info("Scheduler stopped")
