from app.config import settings
from app.dependencies import get_worldcover_service
from app.main import app
from app.services.tokens import TokenService

ORIGIN = "http://testserver"


class PointService:
    async def get_land_cover_type(self, _lat: float, _lon: float) -> int:
        return 10


async def test_persistent_token_and_access_jwt_authenticate(context):
    user = await context.create_user("user@example.com")
    app.dependency_overrides[get_worldcover_service] = PointService
    persistent = await context.client.get(
        "/api/land-cover?lat=0&lon=0",
        headers={"Authorization": f"Bearer {user.bearer_token}"},
    )
    token_response = await context.client.post(
        "/token", data={"username": user.email, "password": "valid-password"}
    )
    jwt_response = await context.client.get(
        "/api/land-cover?lat=0&lon=0",
        headers={"Authorization": f"Bearer {token_response.json()['access_token']}"},
    )

    assert persistent.status_code == 200
    assert persistent.json() == {"class": 10}
    assert token_response.status_code == 200
    assert jwt_response.status_code == 200


async def test_jwt_credential_types_are_not_interchangeable(context):
    user = await context.create_user("user@example.com")
    token_service = TokenService(settings)
    session_token = token_service.create(user.email, "session")
    access_token = token_service.create(user.email, "access")

    header_response = await context.client.get(
        "/openapi.json", headers={"Authorization": f"Bearer {session_token}"}
    )
    context.client.cookies.set(settings.session_cookie_name, access_token)
    cookie_response = await context.client.get("/openapi.json")

    assert header_response.status_code == 401
    assert cookie_response.status_code == 401


async def test_inactive_user_cannot_sign_in_or_use_api(context):
    user = await context.create_user("inactive@example.com", active=False)

    login = await context.login(user.email)
    api = await context.client.get(
        "/openapi.json", headers={"Authorization": f"Bearer {user.bearer_token}"}
    )

    assert login.status_code == 303
    assert settings.session_cookie_name not in login.cookies
    assert api.status_code == 403


async def test_anonymous_protection_contract(context):
    docs = await context.client.get("/docs", follow_redirects=False)
    openapi = await context.client.get("/openapi.json")
    guide = await context.client.get("/app-docs", follow_redirects=False)
    users = await context.client.get("/manage-users", follow_redirects=False)

    assert docs.status_code == 303
    assert docs.headers["location"] == "/"
    assert openapi.status_code == 401
    assert openapi.headers["www-authenticate"] == "Bearer"
    assert guide.status_code == 303
    assert users.status_code == 303


async def test_non_admin_sees_only_own_account_and_cannot_administer(context):
    user = await context.create_user("user@example.com")
    await context.create_user("other@example.com")
    await context.login(user.email)

    page = await context.client.get("/manage-users")
    forbidden = await context.client.post(
        "/users/create",
        data={"email": "new@example.com", "password": "valid-password"},
        headers={"Origin": ORIGIN},
    )

    assert page.status_code == 200
    assert user.email in page.text
    assert "other@example.com" not in page.text
    assert forbidden.status_code == 403


async def test_pages_never_render_password_hashes(context):
    admin = await context.create_user("admin@example.com", admin=True)
    user = await context.create_user("user@example.com")
    await context.login(admin.email)

    page = await context.client.get("/manage-users")
    openapi = await context.client.get("/openapi.json")

    assert admin.password_hash not in page.text
    assert user.password_hash not in page.text
    assert "password_hash" not in page.text
    assert "password_hash" not in openapi.text


async def test_all_ui_pages_have_required_navigation_before_main(context):
    public_pages = ["/", "/forgot-password", "/reset-password"]
    for path in public_pages:
        response = await context.client.get(path)
        assert_navigation(response.text, authenticated=False)

    admin = await context.create_user("admin@example.com", admin=True)
    await context.login(admin.email)
    for path in ["/", "/app-docs", "/manage-users", "/tile-cache", "/docs"]:
        response = await context.client.get(path)
        assert response.status_code == 200
        assert_navigation(response.text, authenticated=True)


async def test_swagger_preauthorizes_api_users_but_not_administrators(context):
    user = await context.create_user("user@example.com")
    await context.login(user.email)
    user_docs = await context.client.get("/docs")

    context.client.cookies.clear()
    admin = await context.create_user("admin@example.com", admin=True)
    await context.login(admin.email)
    admin_docs = await context.client.get("/docs")

    assert "preauthorizeApiKey" in user_docs.text
    assert user.bearer_token in user_docs.text
    assert "preauthorizeApiKey" not in admin_docs.text


def assert_navigation(html: str, *, authenticated: bool) -> None:
    nav = '<nav class="navbar navbar-expand-lg bg-dark navbar-dark">'
    assert nav in html
    assert html.index(nav) < html.index("<main")
    if authenticated:
        navigation = html[html.index(nav) : html.index("</nav>")]
        controls = [">API<", ">Guide<", ">Users<", ">Tile cache<", ">Sign out<"]
        positions = [navigation.index(control) for control in controls]
        assert positions == sorted(positions)
        assert 'class="navbar-nav ms-auto flex-row gap-3"' in html
        assert 'action="/logout" method="post"' in html


async def test_cookie_mutations_require_same_origin_and_success_uses_303(context):
    admin = await context.create_user("admin@example.com", admin=True)
    login = await context.login(admin.email)
    cookie = login.headers["set-cookie"]

    rejected = await context.client.post(
        "/users/create",
        data={"email": "blocked@example.com", "password": "valid-password"},
    )
    accepted = await context.client.post(
        "/users/create",
        data={"email": "created@example.com", "password": "valid-password"},
        headers={"Origin": ORIGIN},
        follow_redirects=False,
    )
    logout = await context.client.post(
        "/logout", headers={"Origin": ORIGIN}, follow_redirects=False
    )

    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie
    assert "Path=/" in cookie
    assert "Max-Age=" in cookie
    assert rejected.status_code == 403
    assert accepted.status_code == 303
    assert accepted.headers["location"] == "/manage-users"
    assert logout.status_code == 303
    assert "Max-Age=0" in logout.headers["set-cookie"]
