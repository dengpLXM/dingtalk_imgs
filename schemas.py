from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field


class MongoConfigBase(BaseModel):
    name: str
    host: str = "localhost"
    port: int = 27017
    database: str
    username: Optional[str] = None
    password: Optional[str] = None
    auth_source: Optional[str] = None
    uri: Optional[str] = None


class MongoConfigCreate(MongoConfigBase):
    pass


class MongoConfigUpdate(MongoConfigBase):
    pass


class MongoConfigOut(MongoConfigBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ScriptBase(BaseModel):
    name: str
    description: Optional[str] = None
    mongo_config_id: int
    content: str


class ScriptCreate(ScriptBase):
    pass


class ScriptUpdate(ScriptBase):
    pass


class ScriptOut(ScriptBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DingTalkBotBase(BaseModel):
    name: str
    webhook_url: str
    secret: Optional[str] = None
    description: Optional[str] = None


class DingTalkBotCreate(DingTalkBotBase):
    pass


class DingTalkBotUpdate(DingTalkBotBase):
    pass


class DingTalkBotOut(DingTalkBotBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TaskBase(BaseModel):
    name: str
    script_id: int
    bot_id: int
    message_template: str
    image_message_text: Optional[str] = Field(
        default=None,
        description="图片播报时与图片一并推送的文案（多行，支持 markdown；不写入截图）",
    )
    msg_type: str = "markdown"
    cron_expression: Optional[str] = None
    enabled: bool = True


class TaskCreate(TaskBase):
    pass


class TaskUpdate(TaskBase):
    pass


class TaskOut(TaskBase):
    id: int
    last_run_at: Optional[datetime] = None
    last_run_result: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TaskLogOut(BaseModel):
    id: int
    task_id: int
    trigger: str
    success: bool
    stage: Optional[str] = None
    duration_ms: Optional[float] = None
    error: Optional[str] = None
    detail: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ExecuteResult(BaseModel):
    success: bool
    result: Any = None
    message_sent: bool = False
    error: Optional[str] = None
