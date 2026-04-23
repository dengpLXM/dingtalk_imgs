from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import DingTalkBot
from schemas import DingTalkBotCreate, DingTalkBotUpdate, DingTalkBotOut

router = APIRouter()


@router.get("/", response_model=list[DingTalkBotOut])
def list_bots(db: Session = Depends(get_db)):
    return db.query(DingTalkBot).all()


@router.get("/{bot_id}", response_model=DingTalkBotOut)
def get_bot(bot_id: int, db: Session = Depends(get_db)):
    bot = db.query(DingTalkBot).filter(DingTalkBot.id == bot_id).first()
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")
    return bot


@router.post("/", response_model=DingTalkBotOut)
def create_bot(data: DingTalkBotCreate, db: Session = Depends(get_db)):
    bot = DingTalkBot(**data.model_dump())
    db.add(bot)
    db.commit()
    db.refresh(bot)
    return bot


@router.put("/{bot_id}", response_model=DingTalkBotOut)
def update_bot(bot_id: int, data: DingTalkBotUpdate, db: Session = Depends(get_db)):
    bot = db.query(DingTalkBot).filter(DingTalkBot.id == bot_id).first()
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")
    for k, v in data.model_dump().items():
        setattr(bot, k, v)
    db.commit()
    db.refresh(bot)
    return bot


@router.delete("/{bot_id}")
def delete_bot(bot_id: int, db: Session = Depends(get_db)):
    bot = db.query(DingTalkBot).filter(DingTalkBot.id == bot_id).first()
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")
    db.delete(bot)
    db.commit()
    return {"ok": True}


@router.post("/{bot_id}/test")
def test_bot(bot_id: int, db: Session = Depends(get_db)):
    bot = db.query(DingTalkBot).filter(DingTalkBot.id == bot_id).first()
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")
    try:
        from services.dingtalk import send_message
        send_message(bot, "text", "测试消息 - DingTalk Stats Reporter", title="测试")
        return {"ok": True, "message": "消息发送成功"}
    except Exception as e:
        return {"ok": False, "message": str(e)}
