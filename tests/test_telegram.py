from unittest.mock import patch, MagicMock
import urllib.parse
import pytest


def test_send_calls_telegram_api():
    mock_settings = MagicMock()
    mock_settings.telegram_bot_token = "TOKEN"
    mock_settings.telegram_chat_id = "123"

    with patch("app.notifications.telegram.urllib.request.urlopen") as mock_open, \
         patch("app.notifications.telegram.settings", mock_settings):
        from app.notifications import telegram
        telegram.send("hello")
        assert mock_open.called
        req = mock_open.call_args[0][0]
        assert "TOKEN" in req.full_url
        assert b"hello" in req.data


def test_send_silent_on_error():
    mock_settings = MagicMock()
    mock_settings.telegram_bot_token = "TOKEN"
    mock_settings.telegram_chat_id = "123"

    with patch("app.notifications.telegram.urllib.request.urlopen", side_effect=Exception("network error")), \
         patch("app.notifications.telegram.settings", mock_settings):
        from app.notifications import telegram
        telegram.send("hello")  # must not raise


def test_send_skips_when_no_token():
    mock_settings = MagicMock()
    mock_settings.telegram_bot_token = ""
    mock_settings.telegram_chat_id = "123"

    with patch("app.notifications.telegram.urllib.request.urlopen") as mock_open, \
         patch("app.notifications.telegram.settings", mock_settings):
        from app.notifications import telegram
        telegram.send("hello")
        assert not mock_open.called


def test_alert_prepends_emoji():
    mock_settings = MagicMock()
    mock_settings.telegram_bot_token = "TOKEN"
    mock_settings.telegram_chat_id = "123"

    with patch("app.notifications.telegram.urllib.request.urlopen") as mock_open, \
         patch("app.notifications.telegram.settings", mock_settings):
        from app.notifications import telegram
        telegram.alert("pipeline down")
        req = mock_open.call_args[0][0]
        assert "🚨" in urllib.parse.unquote_plus(req.data.decode())
