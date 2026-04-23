from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import Script
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
    s = Script(**data.model_dump())
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


@router.put("/{script_id}", response_model=ScriptOut)
def update_script(script_id: int, data: ScriptUpdate, db: Session = Depends(get_db)):
    s = db.query(Script).filter(Script.id == script_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Script not found")
    for k, v in data.model_dump().items():
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
