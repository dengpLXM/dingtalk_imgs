# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

DingTalk Stats Reporter — a FastAPI app that queries MongoDB, renders data via Jinja2 templates (markdown, text, or HTML-to-image), and pushes messages to DingTalk group chat bots on a cron schedule or on-demand.

## Development Commands

```bash
# Setup
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium  # needed for image message type

# Run dev server
uvicorn main:app --host 0.0.0.0 --port 8765 --reload

# Production deploy (on server)
./deploy.sh   # git pull + pip install + playwright install + systemctl restart
```

No test suite or linter is configured.

## Architecture

**Entry point:** `main.py` — loads `.env`, initializes SQLite DB (including inline migration for `cron_expression` column), registers routers, starts/stops APScheduler in the lifespan.

**Data model** (`models.py`): Five SQLAlchemy tables with FK relationships:
- `MongoConfig` → `Script` → `Task` → `DingTalkBot`
- `Task` → `TaskLog` (cascade delete)

**Request/response schemas** (`schemas.py`): Pydantic v2 models with `from_attributes = True`.

**Routers** (`routers/`): Six `APIRouter` modules under `/api/`. The `execute` router contains the core pipeline — script execution, template preview, and full task execution with DingTalk sending.

**Services** (`services/`): Business logic layer:
- `executor.py` — Connects to MongoDB via PyMongo, runs user scripts via `exec()` with `db` variable, renders Jinja2 templates. When result is a dict, its keys are injected into the template context; when it's a list of dicts, `items` is available.
- `dingtalk.py` — Sends messages to DingTalk webhooks with HMAC-SHA256 signing.
- `scheduler.py` — `AsyncIOScheduler` (timezone `Asia/Shanghai`). `sync_jobs()` reads all tasks from DB and adds/removes/reschedules cron jobs. The `_execute_task` coroutine mirrors the manual execute pipeline but runs without request context (creates its own DB session).
- `html_renderer.py` — Singleton Playwright Chromium instance, renders HTML to JPEG.
- `image_host.py` — SFTP upload via Paramiko.
- `image_renderer.py` — PIL/Pillow-based image generation (alternative to Playwright).

**Frontend** (`static/index.html`): Single-page admin UI with Bootstrap 5 + CodeMirror.

## Execution Pipeline

```
MongoDB → exec(script, db=result) → Jinja2 template → rendered message
                                                            │
                                       ┌───────────────────┼───────────────────┐
                                       │ markdown/text     │ image type        │
                                       │                   │ HTML → Playwright │
                                       │                   │ → SFTP upload     │
                                       └───────────────────┼───────────────────┘
                                                           │
                                                     DingTalk webhook
```

The `log_execution` context manager in `routers/task_logs.py` tracks stages (`script` → `template` → `image_render` → `upload` → `send` → `ok`) and records success/failure with timing.

## Key Conventions

- Scheduler timezone is hardcoded to `Asia/Shanghai`; cron expressions use standard 5-field format.
- `.env` is loaded manually at startup (not via python-dotenv) — the `_env_set()` helper in `main.py` persists settings changes back to `.env`.
- The Playwright browser is a singleton — `html_renderer.py` lazily initializes on first use.
- Image messages upload via SFTP then send the HTTP URL to DingTalk; non-image messages send rendered text directly.
- Task logs auto-trim to the most recent 100 entries per task.
