from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import Script, MongoConfig
from schemas import ScriptCreate, ScriptUpdate, ScriptOut

router = APIRouter()


@router.get("/", response_model=list[ScriptOut])
def list_scripts(db: Session = Depends(get_db)):
    return db.query(Script).all()


@router.get("/{script_id}", response_model=ScriptOut)
def get_script(script_id: int, db: Session = Depends(get_db)):
    s = db.query(Script).filter(Script.id == script_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Script not found")
    return s


@router.post("/", response_model=ScriptOut)
def create_script(data: ScriptCreate, db: Session = Depends(get_db)):
    payload = data.model_dump()
    payload["script_format"] = (payload.get("script_format") or "mongodb").lower()
    cfg = db.query(MongoConfig).filter(MongoConfig.id == payload["mongo_config_id"]).first()
    if not cfg:
        raise HTTPException(status_code=404, detail="Database config not found")
    if payload["script_format"] != (cfg.db_type or "").lower():
        raise HTTPException(status_code=400, detail="脚本格式需与数据库配置类型一致")
    s = Script(**payload)
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


@router.put("/{script_id}", response_model=ScriptOut)
def update_script(script_id: int, data: ScriptUpdate, db: Session = Depends(get_db)):
    s = db.query(Script).filter(Script.id == script_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Script not found")
    payload = data.model_dump()
    payload["script_format"] = (payload.get("script_format") or "mongodb").lower()
    cfg = db.query(MongoConfig).filter(MongoConfig.id == payload["mongo_config_id"]).first()
    if not cfg:
        raise HTTPException(status_code=404, detail="Database config not found")
    if payload["script_format"] != (cfg.db_type or "").lower():
        raise HTTPException(status_code=400, detail="脚本格式需与数据库配置类型一致")
    for k, v in payload.items():
        setattr(s, k, v)
    db.commit()
    db.refresh(s)
    return s


@router.delete("/{script_id}")
def delete_script(script_id: int, db: Session = Depends(get_db)):
    s = db.query(Script).filter(Script.id == script_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Script not found")
    db.delete(s)
    db.commit()
    return {"ok": True}
