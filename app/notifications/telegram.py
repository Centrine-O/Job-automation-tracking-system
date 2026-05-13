"""Telegram Bot API notifications. Uses urllib only — no extra dependencies."""
import logging
import urllib.parse
import urllib.request

from app.config import settings

log = logging.getLogger("telegram")


def send(text: str) -> None:
    """Send a message to the configured Telegram chat. Silently fails on error."""
    token = settings.telegram_bot_token
    chat_id = settings.telegram_chat_id
    if not token or not chat_id:
        log.debug("Telegram not configured — skipping notification")
        return
    try:
        data = urllib.parse.urlencode({
            "chat_id": chat_id,
            "text": text,
        }).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data=data,
            method="POST",
        )
        urllib.request.urlopen(req, timeout=10)
    except Exception as exc:
        log.warning(f"Telegram send failed: {exc}")


def alert(text: str) -> None:
    """Send an urgent alert — prepends 🚨."""
    send(f"🚨 {text}")
