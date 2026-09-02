from pathlib import Path

from pydantic import SecretStr

from app.config import Settings
from app.services.mailer import Mailer


async def test_reset_email_is_plain_text_and_tells_user_where_to_enter_code(monkeypatch):
    captured = {}

    async def fake_send(message, **kwargs):
        captured["message"] = message
        captured["kwargs"] = kwargs

    monkeypatch.setattr("app.services.mailer.aiosmtplib.send", fake_send)
    mailer = Mailer(
        Settings(
            database_url="sqlite+aiosqlite:////tmp/test.db",
            tile_cache_dir=Path("/tmp/tiles"),
            jwt_secret=SecretStr("test-secret"),
            smtp_enabled=True,
            smtp_host="smtp.example.com",
            smtp_sender="noreply@example.com",
        )
    )

    await mailer.send_password_reset("user@example.com", "reset-code")

    message = captured["message"]
    assert message.get_content_type() == "text/plain"
    assert "reset-code" in message.get_content()
    assert "/reset-password" in message.get_content()
    assert captured["kwargs"]["hostname"] == "smtp.example.com"
