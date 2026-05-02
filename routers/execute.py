import asyncio
import functools
import os
import json
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import Script, Task, DingTalkBot, MongoConfig
from schemas import ExecuteResult
from services.executor import (
    run_script,
    run_script_isolated,
    render_template,
    render_html_template,
    format_result,
)
from services.dingtalk import send_message_by_bot_id
from services.html_renderer import render_html_to_image
from services.image_host import upload_image

router = APIRouter()

REPORTS_DIR = Path("static/reports")
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

def _get_base_url() -> str:
    return os.getenv("REPORT_BASE_URL", "").rstrip("/")


def _save_report_image(task_id: int, img_bytes: bytes) -> str:
    """Save image, return filename (without base URL)."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"task_{task_id}_{ts}.jpg"
    (REPORTS_DIR / filename).write_bytes(img_bytes)
    # keep only last 20 files to avoid disk bloat
    files = sorted(REPORTS_DIR.glob("*.jpg"), key=lambda f: f.stat().st_mtime)
    for old in files[:-20]:
        old.unlink(missing_ok=True)
    return filename


@router.post("/script/{script_id}")
def execute_script(script_id: int, db: Session = Depends(get_db)):
    script = db.query(Script).filter(Script.id == script_id).first()
    if not script:
        raise HTTPException(status_code=404, detail="Script not found")
    try:
        result, debug = run_script(
            script.content,
            script.mongo_config,
            script.script_format,
        )
        return {"success": True, "result": result, "debug": debug}
    except Exception as e:
        return {"success": False, "error": str(e), "result": None, "debug": None}


@router.post("/task/{task_id}/preview")
async def preview_task(task_id: int, db: Session = Depends(get_db)):
    """Run script + render template, return image preview and variable info. Does NOT send to DingTalk."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    try:
        result, debug = await asyncio.to_thread(
            run_script_isolated,
            task.script.content,
            task.script.mongo_config_id,
            task.script.script_format,
        )
    except Exception as e:
        return {"success": False, "stage": "script", "error": str(e),
                "result": None, "rendered": None, "image_data": None}

    try:
        if task.msg_type == "image":
            rendered = render_html_template(task.message_template, result)
        else:
            rendered = render_template(task.message_template, result)
    except Exception as e:
        return {"success": False, "stage": "template", "error": str(e),
                "result": result, "rendered": None, "image_data": None}

    image_data = None
    if task.msg_type == "image":
        try:
            img_bytes, _, _ = await render_html_to_image(rendered)
            import base64
            image_data = "data:image/jpeg;base64," + base64.b64encode(img_bytes).decode()
        except Exception as e:
            return {"success": False, "stage": "image_render", "error": str(e),
                    "result": result, "rendered": rendered, "image_data": None}

    # extract field names for template hints
    fields: list[str] = []
    if isinstance(result, list) and result and isinstance(result[0], dict):
        fields = list(result[0].keys())
    elif isinstance(result, dict):
        fields = list(result.keys())

    return {
        "success": True,
        "stage": "ok",
        "error": None,
        "result": result,
        "rendered": rendered,
        "image_data": image_data,
        "fields": fields,
    }


@router.post("/task/{task_id}", response_model=ExecuteResult)
async def execute_task(task_id: int, db: Session = Depends(get_db)):
    from routers.task_logs import log_execution

    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    result = None
    error = None
    message_sent = False

    with log_execution(task.id, "manual", db) as log_entry:
        try:
            log_entry.stage = "script"
            result, _ = await asyncio.to_thread(
                run_script_isolated,
                task.script.content,
                task.script.mongo_config_id,
                task.script.script_format,
            )

            if task.msg_type == "image":
                log_entry.stage = "template"
                html = render_html_template(task.message_template, result)
                log_entry.stage = "image_render"
                img_bytes, _, _ = await render_html_to_image(html)
                log_entry.stage = "upload"
                img_url = await asyncio.to_thread(
                    upload_image, img_bytes, task.id
                )
                log_entry.stage = "send"
                await asyncio.to_thread(
                    functools.partial(
                        send_message_by_bot_id,
                        task.bot_id,
                        "image",
                        img_url,
                        image_intro_text=task.image_message_text,
                        at_all=task.at_all,
                    )
                )
            else:
                log_entry.stage = "template"
                message = render_template(task.message_template, result)
                log_entry.stage = "send"
                await asyncio.to_thread(
                    functools.partial(
                        send_message_by_bot_id,
                        task.bot_id,
                        task.msg_type,
                        message,
                        at_all=task.at_all,
                    )
                )

            message_sent = True
            task.last_run_result = "成功"
            log_entry.success = True
            log_entry.stage = "ok"
        except Exception as e:
            error = str(e)
            task.last_run_result = f"失败: {error}"
            log_entry.error = error
            import traceback
            log_entry.detail = traceback.format_exc()

    task.last_run_at = datetime.utcnow()
    db.commit()

    return ExecuteResult(
        success=error is None,
        result=result,
        message_sent=message_sent,
        error=error,
    )
