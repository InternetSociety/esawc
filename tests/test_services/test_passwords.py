import bcrypt

from app.services.passwords import password_hasher


def test_new_passwords_use_argon2_and_legacy_bcrypt_is_supported():
    argon2_hash = password_hasher.hash("valid-password")
    bcrypt_hash = bcrypt.hashpw(b"legacy-password", bcrypt.gensalt()).decode()

    assert argon2_hash.startswith("$argon2")
    assert password_hasher.verify("valid-password", argon2_hash)
    assert password_hasher.verify("legacy-password", bcrypt_hash)
    assert not password_hasher.verify("wrong-password", bcrypt_hash)
