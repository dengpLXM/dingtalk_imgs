import base64
import hashlib
import hmac
import os
import re
import time
import urllib.parse
from typing import Optional

import requests
from models import DingTalkBot

# 钉钉 webhook 直传图片（msgtype=image）对原始二进制大小有限制，实测约 2MB；超限则回退 markdown+外链。
_MAX_WEBHOOK_IMAGE_BYTES = int(
    os.getenv("DINGTALK_WEBHOOK_IMAGE_MAX_BYTES", str(2 * 1024 * 1024 - 4096))
)


def _sign_url(webhook_url: str, secret: str) -> str:
    timestamp = str(round(time.time() * 1000))
    string_to_sign = f"{timestamp}\n{secret}"
    hmac_code = hmac.new(
        secret.encode("utf-8"),
        string_to_sign.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()
    sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
    connector = "&" if "?" in webhook_url else "?"
    return f"{webhook_url}{connector}timestamp={timestamp}&sign={sign}"


def format_dingtalk_markdown_text(text: str) -> str:
    """DingTalk markdown collapses plain single newlines; use trailing two spaces (GFM hard line break).

    See: https://open.dingtalk.com/document/robots/ — line breaks:建议 \\n 前后加空格
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        return text
    # Paragraphs separated by blank line stay as \n\n; within each paragraph, "  \n" = hard break
    parts = re.split(r"\n{2,}", text)
    out = []
    for p in parts:
        lines = [line.rstrip() for line in p.split("\n")]
        out.append("  \n".join(lines))
    return "\n\n".join(out)


def _post_signed(bot: DingTalkBot, payload: dict, timeout: int = 30) -> dict:
    url = bot.webhook_url
    if bot.secret:
        url = _sign_url(url, bot.secret)
    resp = requests.post(url, json=payload, timeout=timeout)
    resp.raise_for_status()
    result = resp.json()
    if result.get("errcode", 0) != 0:
        raise RuntimeError(f"钉钉返回错误: {result.get('errmsg', result)}")
    return result


def send_report_image(
    bot: DingTalkBot,
    img_bytes: bytes,
    *,
    title: str = "统计报告",
    image_intro_text: Optional[str] = None,
    at_all: bool = False,
    image_url_fallback: Optional[str] = None,
) -> dict:
    """先发可选 markdown 导语，再用 msgtype=image 直传 JPEG（钉钉客户端拉不到内网 URL 时也不会空白）。

    超过 `_MAX_WEBHOOK_IMAGE_BYTES` 且提供 `image_url_fallback` 时，回退为 markdown + ![img](url)。
    """
    import logging

    log = logging.getLogger(__name__)

    if len(img_bytes) > _MAX_WEBHOOK_IMAGE_BYTES:
        if not image_url_fallback:
            raise RuntimeError(
                f"报告图片过大 ({len(img_bytes)} bytes)，超过钉钉 webhook 直传上限 "
                f"({_MAX_WEBHOOK_IMAGE_BYTES})，且未配置可访问的图片 URL"
            )
        log.warning(
            "Report JPEG %s bytes > limit %s; falling back to markdown image URL",
            len(img_bytes),
            _MAX_WEBHOOK_IMAGE_BYTES,
        )
        return send_message(
            bot,
            "image",
            image_url_fallback,
            title=title,
            image_intro_text=image_intro_text,
            at_all=at_all,
        )

    intro = (image_intro_text or "").strip()
    if intro:
        intro_fmt = format_dingtalk_markdown_text(intro)
        md_payload: dict = {
            "msgtype": "markdown",
            "markdown": {"title": title, "text": intro_fmt},
        }
        if at_all:
            md_payload["at"] = {"isAtAll": True}
        _post_signed(bot, md_payload, timeout=15)

    img_b64 = base64.b64encode(img_bytes).decode("ascii")
    img_md5 = hashlib.md5(img_bytes).hexdigest()
    img_payload: dict = {
        "msgtype": "image",
        "image": {"base64": img_b64, "md5": img_md5},
    }
    if at_all and not intro:
        img_payload["at"] = {"isAtAll": True}
    return _post_signed(bot, img_payload, timeout=90)


def send_message(
    bot: DingTalkBot,
    msg_type: str,
    content: str,
    title: str = "统计报告",
    image_intro_text: Optional[str] = None,
    at_all: bool = False,
) -> dict:
    if msg_type == "image":
        # content is a public image URL — use markdown: optional intro, then image
        intro = (image_intro_text or "").strip()
        if intro:
            intro_fmt = format_dingtalk_markdown_text(intro)
            text = f"{intro_fmt}\n\n![report]({content})"
        else:
            text = f"![report]({content})"
        payload = {
            "msgtype": "markdown",
            "markdown": {"title": title, "text": text},
        }
    elif msg_type == "markdown":
        payload = {
            "msgtype": "markdown",
            "markdown": {"title": title, "text": content},
        }
    else:
        payload = {
            "msgtype": "text",
            "text": {"content": content},
        }

    if at_all:
        payload["at"] = {"isAtAll": True}

    return _post_signed(bot, payload, timeout=10)


def send_report_image_by_bot_id(
    bot_id: int,
    img_bytes: bytes,
    *,
    title: str = "统计报告",
    image_intro_text: Optional[str] = None,
    at_all: bool = False,
    image_url_fallback: Optional[str] = None,
) -> dict:
    """线程池内调用：独立 Session 加载机器人。"""
    from database import SessionLocal

    db = SessionLocal()
    try:
        bot = db.get(DingTalkBot, bot_id)
        if bot is None:
            raise ValueError("钉钉机器人不存在")
        return send_report_image(
            bot,
            img_bytes,
            title=title,
            image_intro_text=image_intro_text,
            at_all=at_all,
            image_url_fallback=image_url_fallback,
        )
    finally:
        db.close()


def send_message_by_bot_id(
    bot_id: int,
    msg_type: str,
    content: str,
    *,
    title: str = "统计报告",
    image_intro_text: Optional[str] = None,
    at_all: bool = False,
) -> dict:
    """独立 Session 加载机器人后发送；供 asyncio.to_thread，避免跨线程使用 ORM。"""
    from database import SessionLocal

    db = SessionLocal()
    try:
        bot = db.get(DingTalkBot, bot_id)
        if bot is None:
            raise ValueError("钉钉机器人不存在")
        return send_message(
            bot,
            msg_type,
            content,
            title=title,
            image_intro_text=image_intro_text,
            at_all=at_all,
        )
    finally:
        db.close()
