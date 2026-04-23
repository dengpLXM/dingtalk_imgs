import time
import hmac
import hashlib
import base64
import urllib.parse
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


def send_message(bot: DingTalkBot, msg_type: str, content: str, title: str = "统计报告") -> dict:
    url = bot.webhook_url
    if bot.secret:
        url = _sign_url(url, bot.secret)

    if msg_type == "image":
        # content is a public image URL — use markdown to embed image
        payload = {
            "msgtype": "markdown",
            "markdown": {"title": title, "text": f"![report]({content})"},
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

    resp = requests.post(url, json=payload, timeout=10)
    resp.raise_for_status()
    result = resp.json()
    if result.get("errcode", 0) != 0:
        raise RuntimeError(f"钉钉返回错误: {result.get('errmsg', result)}")
    return result
