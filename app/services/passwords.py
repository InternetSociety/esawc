import bcrypt
from argon2 import PasswordHasher as Argon2PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError


class PasswordHasher:
    """Argon2 password adapter with bcrypt verification for legacy rows."""

    def __init__(self) -> None:
        self._argon2 = Argon2PasswordHasher()

    def hash(self, password: str) -> str:
        return self._argon2.hash(password)

    def verify(self, password: str, encoded_hash: str) -> bool:
        if encoded_hash.startswith("$argon2"):
            try:
                return self._argon2.verify(encoded_hash, password)
            except InvalidHashError, VerificationError, VerifyMismatchError:
                return False
        if encoded_hash.startswith(("$2a$", "$2b$", "$2y$")):
            try:
                return bcrypt.checkpw(password.encode(), encoded_hash.encode())
            except ValueError:
                return False
        return False


password_hasher = PasswordHasher()
