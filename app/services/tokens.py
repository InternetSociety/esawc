from datetime import UTC, datetime, timedelta
from typing import Literal

from jose import JWTError, jwt

from app.config import Settings

CredentialType = Literal["session", "access"]


class TokenService:
    def __init__(self, settings: Settings):
        self.settings = settings

    def create(self, email: str, credential_type: CredentialType) -> str:
        minutes = (
            self.settings.session_expire_minutes
            if credential_type == "session"
            else self.settings.access_token_expire_minutes
        )
        payload = {
            "sub": email,
            "exp": datetime.now(UTC) + timedelta(minutes=minutes),
            "credential_type": credential_type,
        }
        return jwt.encode(
            payload,
            self.settings.jwt_secret.get_secret_value(),
            algorithm=self.settings.jwt_algorithm,
        )

    def decode(self, token: str, expected_type: CredentialType) -> str | None:
        try:
            payload = jwt.decode(
                token,
                self.settings.jwt_secret.get_secret_value(),
                algorithms=[self.settings.jwt_algorithm],
            )
        except JWTError:
            return None
        subject = payload.get("sub")
        if (
            not isinstance(subject, str)
            or not isinstance(payload.get("exp"), (int, float))
            or payload.get("credential_type") != expected_type
        ):
            return None
        return subject.lower()
