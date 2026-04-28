import re
import time
import hmac
import hashlib
import base64
import urllib.parse
from typing import Optional

import requests
from models import DingTalkBot


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


def send_message(
    bot: DingTalkBot,
    msg_type: str,
    content: str,
    title: str = "统计报告",
    image_intro_text: Optional[str] = None,
    at_all: bool = False,
) -> dict:
    url = bot.webhook_url
    if bot.secret:
        url = _sign_url(url, bot.secret)

    if msg_type == "image":
        # content is a public image URL — use markdown: optional intro, then image
        intro = (image_intro_text or "").strip()
        if intro:
            intro = format_dingtalk_markdown_text(intro)
            text = f"{intro}\n\n![report]({content})"
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

    resp = requests.post(url, json=payload, timeout=10)
    resp.raise_for_status()
    result = resp.json()
    if result.get("errcode", 0) != 0:
        raise RuntimeError(f"钉钉返回错误: {result.get('errmsg', result)}")
    return result
