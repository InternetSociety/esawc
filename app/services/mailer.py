from email.message import EmailMessage

import aiosmtplib

from app.config import Settings


class Mailer:
    def __init__(self, settings: Settings):
        self.settings = settings

    async def send_password_reset(self, recipient: str, code: str) -> None:
        if not self.settings.smtp_enabled:
            raise RuntimeError("SMTP delivery is disabled")
        message = EmailMessage()
        message["From"] = self.settings.smtp_sender
        message["To"] = recipient
        message["Subject"] = "ESA WorldCover password reset"
        message.set_content(
            "A password reset was requested for your account.\n\n"
            f"Reset code: {code}\n\n"
            "Open /reset-password and paste this code. The code expires in 30 minutes.\n"
        )
        await aiosmtplib.send(
            message,
            hostname=self.settings.smtp_host,
            port=self.settings.smtp_port,
            start_tls=self.settings.smtp_start_tls,
        )
