# DingTalk Stats Reporter

从 MongoDB 查询数据，通过 Jinja2 模板渲染消息（支持 Markdown、纯文本、图片播报），定时或手动推送到钉钉群机器人。

## 功能特性

- **MongoDB 数据源管理** — 支持多个 MongoDB 连接配置，可使用 URI 或分字段填写
- **Python 查询脚本** — 在线编写 Python 脚本查询 MongoDB，通过 `db` 变量操作数据库，结果赋值给 `result`
- **钉钉机器人管理** — 支持 Webhook + 加签（HmacSHA256）安全认证
- **消息模板** — 使用 Jinja2 语法编写消息模板，支持三种消息类型：
  - `markdown` — 钉钉 Markdown 消息
  - `text` — 纯文本消息
  - `image` — HTML 模板渲染为图片（通过 Playwright 截图），上传至 SFTP 图床后以图片形式发送
- **定时调度** — 基于 APScheduler 的 Cron 表达式定时执行，支持常用预设
- **任务预览** — 执行脚本 + 渲染模板，预览最终效果（不发送到钉钉）
- **执行日志** — 记录每次执行的触发方式、耗时、阶段、错误详情，自动保留最近 100 条
- **Web 管理界面** — 基于 Bootstrap 5 的单页管理后台，集成 CodeMirror 代码编辑器

## 技术栈

| 组件 | 技术 |
|------|------|
| Web 框架 | FastAPI + Uvicorn |
| 数据库 | SQLite（SQLAlchemy ORM） |
| 数据源 | MongoDB（PyMongo） |
| 模板引擎 | Jinja2 |
| 图片渲染 | Playwright（Headless Chromium） |
| 图片上传 | SFTP（Paramiko） |
| 定时调度 | APScheduler |
| 前端 | Bootstrap 5 + CodeMirror |

## 快速开始

### 安装依赖

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

如需使用图片播报功能，还需安装 Playwright 浏览器：

```bash
playwright install chromium
```

### 启动服务

```bash
uvicorn main:app --host 0.0.0.0 --port 8765 --reload
```

访问 http://localhost:8765 进入管理界面。

### 配置流程

1. **添加 MongoDB 连接** — 在「MongoDB 配置」标签页中新增数据库连接
2. **编写查询脚本** — 在「查询脚本」标签页中编写 Python 脚本，通过 `db` 操作 MongoDB
3. **配置钉钉机器人** — 在「钉钉机器人」标签页中添加机器人 Webhook 和加签密钥
4. **创建任务** — 在「任务映射」标签页中关联脚本、机器人和消息模板，可选配置 Cron 定时

## 环境变量

通过项目根目录 `.env` 文件配置（自动加载）：

| 变量 | 说明 |
|------|------|
| `UPLOAD_SFTP_HOST` | SFTP 图床服务器地址 |
| `UPLOAD_SFTP_PORT` | SFTP 端口（默认 22） |
| `UPLOAD_SFTP_USER` | SFTP 用户名 |
| `UPLOAD_SFTP_PASS` | SFTP 密码 |
| `UPLOAD_REMOTE_DIR` | 远程存储目录（默认 `/home/imgs`） |
| `UPLOAD_HTTP_BASE` | 图片 HTTP 访问基础 URL |
| `REPORT_BASE_URL` | 服务访问地址（用于生成报告链接） |
| `PLAYWRIGHT_BROWSERS_PATH` | Playwright 浏览器安装路径（可选） |

## 项目结构

```
├── main.py                  # 应用入口，FastAPI 实例与路由注册
├── database.py              # SQLAlchemy 数据库配置
├── models.py                # ORM 模型定义
├── schemas.py               # Pydantic 请求/响应模型
├── requirements.txt         # Python 依赖
├── routers/
│   ├── mongo_configs.py     # MongoDB 配置 CRUD
│   ├── scripts.py           # 查询脚本 CRUD
│   ├── dingtalk_bots.py     # 钉钉机器人 CRUD
│   ├── tasks.py             # 任务 CRUD
│   ├── task_logs.py         # 执行日志查询与清理
│   └── execute.py           # 脚本执行、任务预览与发送
├── services/
│   ├── executor.py          # MongoDB 脚本执行 + Jinja2 模板渲染
│   ├── dingtalk.py          # 钉钉消息发送（含加签）
│   ├── scheduler.py         # APScheduler 定时调度管理
│   ├── html_renderer.py     # Playwright HTML 转图片
│   ├── html_template.py     # HTML 报表基础样式
│   ├── image_host.py        # SFTP 图片上传
│   └── image_renderer.py    # 图片渲染辅助
└── static/
    └── index.html           # Web 管理界面
```

## API 概览

| 路径 | 说明 |
|------|------|
| `GET/POST /api/mongo-configs/` | MongoDB 连接配置管理 |
| `GET/POST /api/scripts/` | 查询脚本管理 |
| `GET/POST /api/bots/` | 钉钉机器人管理 |
| `GET/POST /api/tasks/` | 任务管理 |
| `GET /api/tasks/{id}/logs` | 任务执行日志 |
| `POST /api/execute/script/{id}` | 执行脚本并返回结果 |
| `POST /api/execute/task/{id}` | 执行任务（发送到钉钉） |
| `POST /api/execute/task/{id}/preview` | 预览任务（不发送） |
| `GET /api/scheduler/status` | 查看调度状态 |
| `POST /api/scheduler/sync` | 同步调度任务 |

完整 API 文档访问 http://localhost:8765/docs（Swagger UI）。
