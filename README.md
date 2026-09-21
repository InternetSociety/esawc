# ESA WorldCover 2021 v2 API

This FastAPI service returns ESA WorldCover 2021 v200 land-cover classes for points, circular areas, and uploaded GeoJSON. It also includes authenticated Swagger, a user-administration UI, and an administrator tile-cache page.

WorldCover 2021 v200 data © ESA WorldCover project 2021. It contains modified Copernicus Sentinel data processed by the ESA WorldCover consortium. See <https://doi.org/10.5281/zenodo.7254221>.

## How it Works

The service gets land-cover data from ESA WorldCover GeoTIFF raster tiles. Each tile covers a 3×3-degree area and has a 10-metre resolution. The service calculates the tile identifier from the requested longitude and latitude, then gets that tile from its cache or downloads it from the ESA WorldCover S3 bucket.

All geographic input uses longitude and latitude in WGS 84 coordinates. A point query returns one ESA WorldCover class number in `{"class": 10}`. Area queries return a mapping of class numbers to fractions, such as `{"10": 0.75, "40": 0.25}`. Fractions are calculated from pixel counts and sum to `1.0`.

`GET /api/land-cover` selects the 3×3-degree tile for `lat` and `lon`. Rasterio samples the matching cell and returns its class number. A masked NoData cell returns `0`.

`GET /api/land-cover-fractions` makes a true circle in metres around the requested point. PyProj first creates an azimuthal-equidistant projection centred on that point, so the radius remains accurate at any latitude. The service converts the circle back to WGS 84, finds every intersecting tile, and calculates the fraction of valid pixels in each land-cover class. The supported radius is greater than `0` and at most `100,000` metres.

`POST /api/land-cover-geojson` accepts a multipart `geojson_file`. It accepts GeoJSON geometries, Features, and FeatureCollections. A single Point returns one class number. Other geometry types return class fractions. The service rejects invalid JSON and GeoJSON that does not cover available tile data with HTTP 422.

For circle and GeoJSON queries, Rasterio reads only the raster window that overlaps the geometry. The service processes large windows in chunks, applies a geometry mask, ignores NoData and class `0` pixels, and counts the remaining class numbers. It moves blocking raster reads and tile-file writes to worker threads.

The service checks coverage against the rectangular bounds of WorldCover tiles. A circle or GeoJSON geometry can span several tiles. It includes valid pixels from every intersecting tile, including tiles across a country boundary.

| Library | Use |
| --- | --- |
| HTTPX | Download ESA WorldCover GeoTIFF tiles. |
| Rasterio | Open GeoTIFF tiles, sample point cells, read raster windows, and make geometry masks. |
| Shapely | Read GeoJSON, identify intersecting tiles, and construct geometries. |
| PyProj | Create the metre-based circle and convert it to WGS 84. |
| NumPy | Select valid pixels and calculate land-cover class fractions. |

## Run the service

Docker Compose is the only supported application environment. CPython and all application tools run in the `app` container.

1. Copy `docker-compose.yml.example` to `docker-compose.yml`.
2. Copy `.env.example` to `.env`.
3. Replace `JWT_SECRET` with a long, random value. Set `COOKIE_SECURE=true` for production HTTPS.
4. Build and start the service:

```bash
docker compose up --build
```

5. Create the first administrator. The command prompts for a password without displaying it:

```bash
docker compose run --rm app python manage_users.py create admin@example.com
```

The application is available at <http://localhost:8001>. The SQLite database and downloaded tiles remain in the bind-mounted `app/data` directory.

Do not install Python packages or run Python tools on the host. Declare dependencies in `requirements.txt`, then rebuild the image.

## API

All application endpoints use the `/api` prefix and require an active account:

| Method | Endpoint | Input | Result |
| --- | --- | --- | --- |
| `GET` | `/api/land-cover` | `lat`, `lon` | The class at one point. |
| `GET` | `/api/land-cover-fractions` | `lat`, `lon`, `radius` in metres | Class fractions in a circle. |
| `POST` | `/api/land-cover-geojson` | `geojson_file` multipart field | One class for a Point, or class fractions for other geometries. |

For example:

```bash
curl -H "Authorization: Bearer TOKEN" \
  "http://localhost:8001/api/land-cover?lat=-41.2865&lon=174.7762"
```

Send API credentials in `Authorization: Bearer TOKEN`. The application tries a persistent token first, then accepts an access-type JWT from `POST /token`. Inactive accounts receive HTTP 403.

## Configuration

Copy `.env.example` to `.env`. Change the values there, then restart the app container. `app/config.py` defines the settings, their types, and their defaults. Environment variables override those defaults.

| Setting | Default | Purpose |
| --- | ---: | --- |
| `DATABASE_URL` | Required | SQLAlchemy database connection URL. |
| `TILE_CACHE_DIR` | Required | Directory for downloaded WorldCover GeoTIFF tiles. |
| `TILE_EXPIRY_DAYS` | `365` | Days before an unused cached tile expires. |
| `JWT_SECRET` | Required | Secret used to sign JWTs. Use a long random value. |
| `JWT_ALGORITHM` | `HS256` | JWT signing algorithm. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | Lifetime of a short-lived API JWT. |
| `SESSION_EXPIRE_MINUTES` | `10080` (7 days) | Lifetime of a browser session. |
| `COOKIE_SECURE` | `false` | Send session cookies only over HTTPS when `true`. |
| `SMTP_ENABLED` | `false` | Enable password-reset email delivery. |
| `SMTP_HOST` | Empty | SMTP server host. Required when SMTP is enabled. |
| `SMTP_PORT` | `587` | SMTP server port. |
| `SMTP_SENDER` | Empty | Password-reset sender address. Required when SMTP is enabled. |
| `SMTP_START_TLS` | `true` | Use STARTTLS for SMTP delivery. |

## Authentication and UI

Open `/` and sign in with an administrator account. Authenticated users can access these pages:

- `/docs` for Swagger
- `/app-docs` for this guide
- `/manage-users` for their visible account information

Administrators manage all users and the `/tile-cache` page. API users get a random persistent bearer token. Administrators never get one. `/token` exchanges a valid email and password for a short-lived JWT. Browser sessions use a separate typed JWT in an HTTP-only cookie.

Use `/forgot-password` to request a reset code. When SMTP delivery is enabled, the service emails a one-time code. The code expires after 30 minutes. Paste it into `/reset-password`. The request acknowledgement is the same whether or not an eligible account exists.

## Checks

Run every check through Compose:

```bash
docker compose run --rm app pytest
docker compose run --rm app pytest --cov=app
docker compose run --rm app ruff check .
docker compose run --rm app ruff format --check .
docker compose run --rm app mypy app/
```

Tests use a separate SQLite database. Rollback transactions isolate database changes.

## Structure

```text
app/
├── main.py
├── config.py
├── database.py
├── dependencies.py
├── models/
├── schemas/
├── routers/
├── services/
├── repositories/
└── templates/
tests/
├── conftest.py
├── test_routers/
└── test_services/
migrations/
```

## Database and first administrator

The container applies Alembic migrations when it starts. Use these commands for explicit migration work:

```bash
docker compose run --rm app alembic upgrade head
docker compose run --rm app alembic revision --autogenerate -m "description"
```

Create or remove an account with the shared user service:

```bash
docker compose run --rm app python manage_users.py create admin@example.com
docker compose run --rm app python manage_users.py remove user@example.com
```

For a database created by a pre-Alembic version, first back it up and verify that it has the legacy `users` and `cached_tiles` tables. Then stamp the baseline revision and upgrade. Do this only once:

```bash
docker compose run --rm app alembic stamp 20260902_0001
docker compose run --rm app alembic upgrade head
```

The account-management command does not print a password, password hash, JWT, or persistent token.
