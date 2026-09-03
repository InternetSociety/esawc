# ESA WorldCover 2021 v2 API

This FastAPI service returns ESA WorldCover 2021 v200 land-cover classes for points, circular areas, and uploaded GeoJSON. It also includes a server-rendered administration UI.

WorldCover 2021 v200 data © ESA WorldCover project 2021. It contains modified Copernicus Sentinel data processed by the ESA WorldCover consortium. See <https://doi.org/10.5281/zenodo.7254221>.

## Requirements

Use Docker Engine and Docker Compose. Do not install or run the Python toolchain on the host.

## First start

1. Copy `docker-compose.yml.example` to the untracked file `docker-compose.yml`.
2. Copy `.env.example` to the untracked file `.env`.
3. Replace `JWT_SECRET` with a long random value. Set `COOKIE_SECURE=true` for production HTTPS.
4. Start the service. The container applies pending database migrations before it starts:

```console
docker compose up --build -d
```

5. Create the first administrator. The command prompts for the password without displaying it:

```console
docker compose run --rm app python manage_users.py create admin@example.com
```

The application listens on <http://localhost:8001>. Authenticated users can open `/docs`, `/app-docs`, and `/manage-users`.

For a database created by a pre-Alembic version, back it up, verify that it has the legacy `users` and `cached_tiles` tables, stamp the baseline revision, and then upgrade. Do this only once:

```console
docker compose run --rm app alembic stamp 20260902_0001
docker compose run --rm app alembic upgrade head
```

## API

All application endpoints use the `/api` prefix:

- `GET /api/land-cover?lat=...&lon=...`
- `GET /api/land-cover-fractions?lat=...&lon=...&radius=...`
- `POST /api/land-cover-geojson` with a `geojson_file` multipart field

API users authenticate with their persistent bearer token. A short-lived JWT from `POST /token` is also accepted. Administrators use a browser session and do not receive persistent tokens.

## Password recovery

Configure `SMTP_ENABLED`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_SENDER`, and `SMTP_START_TLS` in `.env`. The public recovery flow always gives the same acknowledgement, whether or not an account is eligible. Reset codes expire after 30 minutes and are stored only as SHA-256 digests.

## Operations

```console
docker compose up --build
docker compose down
docker compose run --rm app alembic upgrade head # apply migrations manually, if required
docker compose run --rm app pytest
docker compose run --rm app pytest --cov=app
docker compose run --rm app ruff check .
docker compose run --rm app ruff format --check .
docker compose run --rm app mypy app/
docker compose run --rm app python manage_users.py remove user@example.com
```

The SQLite database and downloaded tiles are stored under the bind-mounted `app/data` directory.

## Architecture

- Routers parse HTTP input and call services.
- Services contain normalization, lifecycle, authentication-independent business rules, and geospatial operations.
- Repositories contain all SQLAlchemy persistence operations.
- The request database dependency commits successful work and rolls back failures.
- Alembic owns all schema creation and changes.
- Blocking Rasterio and file operations run in worker threads.

The three application API responses use Pydantic models. The UI uses Jinja templates and Bootstrap 5. Swagger and the OpenAPI document require an active account.
