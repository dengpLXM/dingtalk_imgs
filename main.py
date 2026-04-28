import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

_ENV_FILE = Path(".env")

# Load .env before importing modules that may read settings.
if _ENV_FILE.exists():
    for _line in _ENV_FILE.read_text().splitlines():
        if "=" in _line and not _line.startswith("#"):
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

from contextlib import asynccontextmanager
from database import engine, Base
from routers import mongo_configs, scripts, dingtalk_bots, tasks, execute, task_logs
from services import scheduler as sched_service

Base.metadata.create_all(bind=engine)
Path("static/reports").mkdir(parents=True, exist_ok=True)

with engine.connect() as conn:
    from sqlalchemy import text, inspect as sa_inspect
    cols = [c["name"] for c in sa_inspect(engine).get_columns("tasks")]
    if "cron_expression" not in cols:
        conn.execute(text("ALTER TABLE tasks ADD COLUMN cron_expression VARCHAR(100)"))
        conn.commit()
    if "image_message_text" not in cols:
        conn.execute(text("ALTER TABLE tasks ADD COLUMN image_message_text TEXT"))
        conn.commit()


@asynccontextmanager
async def lifespan(application: FastAPI):
    sched_service.start()
    yield
    sched_service.shutdown()


app = FastAPI(title="DingTalk Stats Reporter", version="1.0.0", lifespan=lifespan)

app.include_router(mongo_configs.router, prefix="/api/mongo-configs", tags=["MongoDB"])
app.include_router(scripts.router, prefix="/api/scripts", tags=["Scripts"])
app.include_router(dingtalk_bots.router, prefix="/api/bots", tags=["DingTalk"])
app.include_router(tasks.router, prefix="/api/tasks", tags=["Tasks"])
app.include_router(task_logs.router, prefix="/api/tasks", tags=["TaskLogs"])
app.include_router(execute.router, prefix="/api/execute", tags=["Execute"])

app.mount("/static", StaticFiles(directory="static"), name="static")


def _env_set(key: str, value: str) -> None:
    os.environ[key] = value
    lines = []
    if _ENV_FILE.exists():
        lines = [l for l in _ENV_FILE.read_text().splitlines()
                 if not l.startswith(f"{key}=")]
    lines.append(f"{key}={value}")
    _ENV_FILE.write_text("\n".join(lines) + "\n")


@app.get("/api/settings/github")
def get_github_settings():
    return {
        "token": os.getenv("GITHUB_TOKEN", ""),
        "repo": os.getenv("GITHUB_REPO", ""),
    }


@app.post("/api/settings/github")
def set_github_settings(body: dict):
    token = body.get("token", "").strip()
    repo = body.get("repo", "").strip()
    _env_set("GITHUB_TOKEN", token)
    _env_set("GITHUB_REPO", repo)
    return {"ok": True}


@app.get("/api/settings/base-url")
def get_base_url():
    return {"base_url": os.getenv("REPORT_BASE_URL", "")}


@app.post("/api/settings/base-url")
def set_base_url(body: dict):
    url = body.get("base_url", "").rstrip("/")
    _env_set("REPORT_BASE_URL", url)
    return {"ok": True, "base_url": url}


@app.get("/api/scheduler/status")
def scheduler_status():
    return sched_service.get_job_status()


@app.post("/api/scheduler/sync")
def scheduler_sync():
    sched_service.sync_jobs()
    return {"ok": True, "jobs": len(sched_service.get_job_status())}


@app.get("/")
async def root():
    return FileResponse("static/index.html")
