from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import MongoConfig
from schemas import MongoConfigCreate, MongoConfigUpdate, MongoConfigOut, MongoConfigBase

router = APIRouter()


@router.get("/", response_model=list[MongoConfigOut])
def list_configs(db: Session = Depends(get_db)):
    return db.query(MongoConfig).all()


@router.get("/{config_id}", response_model=MongoConfigOut)
def get_config(config_id: int, db: Session = Depends(get_db)):
    cfg = db.query(MongoConfig).filter(MongoConfig.id == config_id).first()
    if not cfg:
        raise HTTPException(status_code=404, detail="Config not found")
    return cfg


@router.post("/", response_model=MongoConfigOut)
def create_config(data: MongoConfigCreate, db: Session = Depends(get_db)):
    cfg = MongoConfig(**data.model_dump())
    db.add(cfg)
    db.commit()
    db.refresh(cfg)
    return cfg


@router.put("/{config_id}", response_model=MongoConfigOut)
def update_config(config_id: int, data: MongoConfigUpdate, db: Session = Depends(get_db)):
    cfg = db.query(MongoConfig).filter(MongoConfig.id == config_id).first()
    if not cfg:
        raise HTTPException(status_code=404, detail="Config not found")
    for k, v in data.model_dump().items():
        setattr(cfg, k, v)
    db.commit()
    db.refresh(cfg)
    return cfg


@router.delete("/{config_id}")
def delete_config(config_id: int, db: Session = Depends(get_db)):
    cfg = db.query(MongoConfig).filter(MongoConfig.id == config_id).first()
    if not cfg:
        raise HTTPException(status_code=404, detail="Config not found")
    db.delete(cfg)
    db.commit()
    return {"ok": True}


@router.post("/test-connection")
def test_connection(data: MongoConfigBase):
    """Test connection using form values directly (no save required)."""
    try:
        from pymongo import MongoClient
        uri = _build_uri_from_data(data)
        client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        client.server_info()
        client.close()
        return {"ok": True, "message": "连接成功"}
    except Exception as e:
        return {"ok": False, "message": _friendly_error(e)}


@router.post("/{config_id}/test")
def test_config(config_id: int, db: Session = Depends(get_db)):
    cfg = db.query(MongoConfig).filter(MongoConfig.id == config_id).first()
    if not cfg:
        raise HTTPException(status_code=404, detail="Config not found")
    try:
        from pymongo import MongoClient
        uri = _build_uri(cfg)
        client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        client.server_info()
        client.close()
        return {"ok": True, "message": "连接成功"}
    except Exception as e:
        return {"ok": False, "message": _friendly_error(e)}


def _build_uri(cfg: MongoConfig) -> str:
    if cfg.uri:
        return cfg.uri
    if cfg.username and cfg.password:
        from urllib.parse import quote_plus
        auth = f"{quote_plus(cfg.username)}:{quote_plus(cfg.password)}@"
        auth_source = cfg.auth_source or "admin"
    else:
        auth = ""
        auth_source = cfg.auth_source or None
    uri = f"mongodb://{auth}{cfg.host}:{cfg.port}/{cfg.database}"
    if auth_source:
        uri += f"?authSource={auth_source}"
    return uri


def _friendly_error(e: Exception) -> str:
    msg = str(e).lower()
    if "connection refused" in msg or "errno 61" in msg or "errno 111" in msg:
        return "连接被拒绝：MongoDB 服务未启动，或主机/端口填写有误"
    if "authentication failed" in msg or "auth failed" in msg:
        return "认证失败：用户名或密码错误，请检查认证信息"
    if "timed out" in msg or "timeout" in msg:
        return "连接超时：主机不可达，请检查 IP 地址和防火墙设置"
    if "name or service not known" in msg or "nodename nor servname" in msg or "getaddrinfo" in msg:
        return "主机名解析失败：无法找到该主机，请检查地址是否正确"
    if "ssl" in msg or "tls" in msg:
        return "SSL/TLS 错误：请检查是否需要开启或关闭 SSL 连接"
    if "unauthorized" in msg:
        return "权限不足：当前用户无权访问该数据库"
    raw = str(e).split("Topology Description")[0].strip().rstrip(",")
    return f"连接失败：{raw}"


def _build_uri_from_data(data: MongoConfigBase) -> str:
    if data.uri:
        return data.uri
    if data.username and data.password:
        from urllib.parse import quote_plus
        auth = f"{quote_plus(data.username)}:{quote_plus(data.password)}@"
        auth_source = data.auth_source or "admin"
    else:
        auth = ""
        auth_source = data.auth_source or None
    uri = f"mongodb://{auth}{data.host}:{data.port}/{data.database}"
    if auth_source:
        uri += f"?authSource={auth_source}"
    return uri
