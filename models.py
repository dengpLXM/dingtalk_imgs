from datetime import datetime
from typing import Optional
from sqlalchemy import Integer, String, Text, Boolean, DateTime, Float, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base


class MongoConfig(Base):
    __tablename__ = "mongo_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    db_type: Mapped[str] = mapped_column(String(20), default="mongodb")
    host: Mapped[str] = mapped_column(String(200), default="localhost")
    port: Mapped[int] = mapped_column(Integer, default=27017)
    database: Mapped[str] = mapped_column(String(100), nullable=False)
    username: Mapped[Optional[str]] = mapped_column(String(100))
    password: Mapped[Optional[str]] = mapped_column(String(200))
    auth_source: Mapped[Optional[str]] = mapped_column(String(100))
    uri: Mapped[Optional[str]] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    scripts: Mapped[list["Script"]] = relationship("Script", back_populates="mongo_config")


class Script(Base):
    __tablename__ = "scripts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    mongo_config_id: Mapped[int] = mapped_column(Integer, ForeignKey("mongo_configs.id"), nullable=False)
    script_format: Mapped[str] = mapped_column(String(20), default="mongodb")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    mongo_config: Mapped["MongoConfig"] = relationship("MongoConfig", back_populates="scripts")
    tasks: Mapped[list["Task"]] = relationship("Task", back_populates="script")


class DingTalkBot(Base):
    __tablename__ = "dingtalk_bots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    webhook_url: Mapped[str] = mapped_column(String(500), nullable=False)
    secret: Mapped[Optional[str]] = mapped_column(String(200))
    description: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    tasks: Mapped[list["Task"]] = relationship("Task", back_populates="bot")


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    script_id: Mapped[int] = mapped_column(Integer, ForeignKey("scripts.id"), nullable=False)
    bot_id: Mapped[int] = mapped_column(Integer, ForeignKey("dingtalk_bots.id"), nullable=False)
    message_template: Mapped[str] = mapped_column(Text, nullable=False)
    # 图片播报时：与图片一并推送的钉钉 markdown 文本（不写入截图）
    image_message_text: Mapped[Optional[str]] = mapped_column(Text)
    msg_type: Mapped[str] = mapped_column(String(20), default="markdown")
    cron_expression: Mapped[Optional[str]] = mapped_column(String(100))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    at_all: Mapped[bool] = mapped_column(Boolean, default=False)
    last_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    last_run_result: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    script: Mapped["Script"] = relationship("Script", back_populates="tasks")
    bot: Mapped["DingTalkBot"] = relationship("DingTalkBot", back_populates="tasks")
    logs: Mapped[list["TaskLog"]] = relationship("TaskLog", back_populates="task", cascade="all, delete-orphan")


class TaskLog(Base):
    __tablename__ = "task_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    task_id: Mapped[int] = mapped_column(Integer, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    trigger: Mapped[str] = mapped_column(String(20), nullable=False)  # manual / scheduled
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    stage: Mapped[Optional[str]] = mapped_column(String(30))  # script / template / image_render / send
    duration_ms: Mapped[Optional[float]] = mapped_column(Float)
    error: Mapped[Optional[str]] = mapped_column(Text)
    detail: Mapped[Optional[str]] = mapped_column(Text)  # extra debug info / traceback
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    task: Mapped["Task"] = relationship("Task", back_populates="logs")
