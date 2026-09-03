import asyncio
import hashlib
from datetime import UTC, datetime, timedelta

from app.config import settings
from app.services.passwords import password_hasher


async def test_valid_sign_in_sets_configured_cookie_and_updates_last_login(context):
    user = await context.create_user("Admin@Example.com", admin=True)

    response = await context.login("ADMIN@example.com")

    assert response.status_code == 303
    assert settings.session_cookie_name in response.cookies
    assert response.cookies[settings.session_cookie_name]
    assert user.last_login_at is not None


async def test_invalid_or_inactive_credentials_do_not_create_session(context):
    await context.create_user("active@example.com")
    await context.create_user("inactive@example.com", active=False)

    wrong = await context.login("active@example.com", "wrong-password")
    inactive = await context.login("inactive@example.com")

    assert wrong.status_code == inactive.status_code == 303
    assert settings.session_cookie_name not in wrong.cookies
    assert settings.session_cookie_name not in inactive.cookies


async def test_reset_request_has_same_response_for_unknown_inactive_and_active(context):
    await context.create_user("inactive@example.com", active=False)
    await context.create_user("active@example.com")

    responses = [
        await context.client.post("/forgot-password", data={"email": address})
        for address in (
            "unknown@example.com",
            "inactive@example.com",
            "active@example.com",
        )
    ]

    assert {response.status_code for response in responses} == {200}
    assert len({response.text for response in responses}) == 1
    assert "eligible" in responses[0].text


async def test_reset_email_contains_code_and_database_stores_only_digest(context):
    user = await context.create_user("user@example.com")

    response = await context.client.post("/forgot-password", data={"email": "USER@example.com"})

    recipient, code = context.mailer.messages[-1]
    assert response.status_code == 200
    assert recipient == "user@example.com"
    assert len(code) >= 48
    assert user.reset_token_hash == hashlib.sha256(code.encode()).hexdigest()
    assert code != user.reset_token_hash
    assert user.reset_token_expires_at is not None
    expires = user.reset_token_expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=UTC)
    remaining = expires - datetime.now(UTC)
    assert timedelta(minutes=29) < remaining <= timedelta(minutes=30)


async def test_valid_reset_is_single_use_and_changes_password(context):
    user = await context.create_user("user@example.com", "old-password")
    await context.client.post("/forgot-password", data={"email": user.email})
    code = context.mailer.messages[-1][1]

    response = await context.client.post(
        "/reset-password",
        data={"code": code, "password": "new-password"},
        follow_redirects=False,
    )
    reused = await context.client.post(
        "/reset-password",
        data={"code": code, "password": "other-password"},
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/?reset=success"
    assert reused.status_code == 400
    assert password_hasher.verify("new-password", user.password_hash)
    assert user.reset_token_hash is None
    assert user.reset_token_expires_at is None


async def test_invalid_expired_and_inactive_reset_codes_do_not_change_password(context):
    user = await context.create_user("user@example.com", "old-password")

    invalid = await context.client.post(
        "/reset-password",
        data={"code": "not-a-code", "password": "new-password"},
    )
    await context.client.post("/forgot-password", data={"email": user.email})
    code = context.mailer.messages[-1][1]
    user.reset_token_expires_at = datetime.now(UTC) - timedelta(seconds=1)
    expired = await context.client.post(
        "/reset-password", data={"code": code, "password": "new-password"}
    )
    user.reset_token_expires_at = datetime.now(UTC) + timedelta(minutes=30)
    user.is_active = False
    inactive = await context.client.post(
        "/reset-password", data={"code": code, "password": "new-password"}
    )

    assert invalid.status_code == expired.status_code == inactive.status_code == 400
    assert password_hasher.verify("old-password", user.password_hash)


async def test_second_reset_request_invalidates_first_code(context):
    user = await context.create_user("user@example.com")
    await context.client.post("/forgot-password", data={"email": user.email})
    first = context.mailer.messages[-1][1]
    await context.client.post("/forgot-password", data={"email": user.email})
    second = context.mailer.messages[-1][1]

    old_response = await context.client.post(
        "/reset-password", data={"code": first, "password": "new-password"}
    )
    new_response = await context.client.post(
        "/reset-password",
        data={"code": second, "password": "new-password"},
        follow_redirects=False,
    )

    assert first != second
    assert old_response.status_code == 400
    assert new_response.status_code == 303


async def test_delivery_is_nonblocking_and_failure_clears_state(context):
    user = await context.create_user("user@example.com")
    context.mailer.fail = True
    context.mailer.release = asyncio.Event()

    request = asyncio.create_task(
        context.client.post("/forgot-password", data={"email": user.email})
    )
    await asyncio.wait_for(context.mailer.entered.wait(), timeout=1)
    marker_ran = False

    async def marker() -> None:
        nonlocal marker_ran
        await asyncio.sleep(0)
        marker_ran = True

    await marker()
    assert marker_ran
    assert not request.done()
    context.mailer.release.set()
    response = await request
    unknown = await context.client.post("/forgot-password", data={"email": "unknown@example.com"})

    assert response.status_code == 200
    assert response.text == unknown.text
    assert user.reset_token_hash is None
    assert user.reset_token_expires_at is None
