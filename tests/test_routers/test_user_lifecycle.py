import pytest

from app.exceptions import ProhibitedLifecycleError

ORIGIN = "http://testserver"


async def test_administrator_can_make_each_permitted_lifecycle_change(context):
    admin = await context.create_user("admin@example.com", admin=True)
    await context.login(admin.email)

    created = await context.client.post(
        "/users/create",
        data={"email": "new@example.com", "password": "valid-password"},
        headers={"Origin": ORIGIN},
        follow_redirects=False,
    )
    user = await context.service.repository.get_by_email("new@example.com")
    assert user is not None
    regenerated = await context.client.post(
        f"/users/{user.id}/regen-token",
        headers={"Origin": ORIGIN},
        follow_redirects=False,
    )
    deactivated = await context.client.post(
        f"/users/{user.id}/toggle-active",
        headers={"Origin": ORIGIN},
        follow_redirects=False,
    )
    promoted = await context.client.post(
        f"/users/{user.id}/toggle-admin",
        headers={"Origin": ORIGIN},
        follow_redirects=False,
    )
    deleted = await context.client.post(
        f"/users/{user.id}/delete",
        headers={"Origin": ORIGIN},
        follow_redirects=False,
    )

    assert {created.status_code, regenerated.status_code, deactivated.status_code} == {303}
    assert promoted.status_code == 303
    assert deleted.status_code == 303
    assert await context.service.repository.get_by_id(user.id) is None


async def test_self_protection_rules_are_enforced_and_controls_are_hidden(context):
    admin = await context.create_user("admin@example.com", admin=True)
    await context.login(admin.email)

    responses = [
        await context.client.post(f"/users/{admin.id}/{action}", headers={"Origin": ORIGIN})
        for action in ("toggle-active", "toggle-admin", "delete")
    ]
    page = await context.client.get("/manage-users")

    assert {response.status_code for response in responses} == {400}
    assert f"/users/{admin.id}/toggle-active" not in page.text
    assert f"/users/{admin.id}/toggle-admin" not in page.text
    assert f"/users/{admin.id}/delete" not in page.text


async def test_last_active_administrator_is_protected_by_service(context):
    admin = await context.create_user("admin@example.com", admin=True)
    inactive_actor = await context.create_user(
        "inactive-admin@example.com", admin=True, active=False
    )

    with pytest.raises(ProhibitedLifecycleError):
        await context.service.toggle_active(inactive_actor, admin.id)
    with pytest.raises(ProhibitedLifecycleError):
        await context.service.toggle_admin(inactive_actor, admin.id)
    with pytest.raises(ProhibitedLifecycleError):
        await context.service.delete_user(None, admin.id)


async def test_missing_duplicate_and_prohibited_operations_have_required_statuses(context):
    admin = await context.create_user("admin@example.com", admin=True)
    await context.login(admin.email)

    duplicate = await context.client.post(
        "/users/create",
        data={"email": admin.email, "password": "valid-password"},
        headers={"Origin": ORIGIN},
    )
    missing = await context.client.post("/users/999999/delete", headers={"Origin": ORIGIN})
    prohibited = await context.client.post(
        f"/users/{admin.id}/regen-token", headers={"Origin": ORIGIN}
    )

    assert duplicate.status_code == 409
    assert missing.status_code == 404
    assert prohibited.status_code == 400


async def test_replacement_token_works_and_old_token_fails(context):
    admin = await context.create_user("admin@example.com", admin=True)
    user = await context.create_user("user@example.com")
    old_token = user.bearer_token
    await context.login(admin.email)

    response = await context.client.post(
        f"/users/{user.id}/regen-token",
        headers={"Origin": ORIGIN},
        follow_redirects=False,
    )
    new_token = user.bearer_token
    context.client.cookies.clear()
    old_access = await context.client.get(
        "/openapi.json", headers={"Authorization": f"Bearer {old_token}"}
    )
    new_access = await context.client.get(
        "/openapi.json", headers={"Authorization": f"Bearer {new_token}"}
    )

    assert response.status_code == 303
    assert old_token != new_token
    assert old_access.status_code == 401
    assert new_access.status_code == 200


async def test_promotion_removes_token_and_demotion_creates_new_one(context):
    admin = await context.create_user("admin@example.com", admin=True)
    user = await context.create_user("user@example.com")
    original = user.bearer_token
    await context.login(admin.email)

    promoted = await context.client.post(
        f"/users/{user.id}/toggle-admin",
        headers={"Origin": ORIGIN},
        follow_redirects=False,
    )
    assert promoted.status_code == 303
    assert user.is_admin
    assert user.bearer_token is None

    demoted = await context.client.post(
        f"/users/{user.id}/toggle-admin",
        headers={"Origin": ORIGIN},
        follow_redirects=False,
    )
    assert demoted.status_code == 303
    assert not user.is_admin
    assert user.bearer_token
    assert user.bearer_token != original
