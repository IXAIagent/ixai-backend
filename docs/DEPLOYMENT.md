# IXAI Backend Deployment

This document records the deployment foundation for `backend/ixai_agent`.

## Runtime

- Framework: FastAPI
- Entry point: `app.main:app`
- Production server command:

```bash
python3 -m uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Local development can use:

```bash
APP_ENV=development python3 -m uvicorn app.main:app --reload --port 8000
```

`APP_ENV=development` is required for the local development secret fallback.
Production-like environments must set a real `SECRET_KEY`.

## Required Environment Variables

```text
DATABASE_URL
SECRET_KEY
BACKEND_CORS_ORIGINS
ENVIRONMENT=production
```

Recommended optional alias:

```text
APP_ENV=production
```

Notes:

- `DATABASE_URL` supports PostgreSQL. `postgres://...` is normalized to
  `postgresql://...` by backend config.
- `BACKEND_CORS_ORIGINS` should include the active frontend origin, for example
  `https://app.ixuan.ai`.
- Do not use `*` for CORS because credentials are enabled.

## Database

Production should use PostgreSQL.

Before serving production traffic, run:

```bash
python3 -m alembic upgrade head
```

SQLite is acceptable for local development and isolated E2E verification only.
Do not deploy production IXAI Pro / account-link workflows on SQLite.

## Migration Operations

Current production state:

- Production PostgreSQL was migrated to `0009_supabase_account_link (head)`.
- The v1.54.5 temporary unauthenticated migration endpoint was used once for
  Render Free bootstrap.
- That endpoint was removed in v1.54.6 and must not be reintroduced as a
  long-lived production route.

Future migrations should use a protected operational path:

- CI/CD migration step
- paid Render Shell / Jobs
- Railway one-off command
- admin-only internal migration mechanism with strong authentication

## Health Checks

Use:

```text
GET /health
GET /readyz
```

`/health` confirms process availability.
`/readyz` confirms database connectivity.

## Render Deployment

1. Create a new Render Web Service from the backend repository.
2. Runtime: Python.
3. Build command:

```bash
pip install -r requirements.txt
```

4. Start command:

```bash
python3 -m uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

5. Health check path:

```text
/health
```

6. Add environment variables:

```text
ENVIRONMENT=production
APP_ENV=production
DATABASE_URL=<Render PostgreSQL connection string>
SECRET_KEY=<strong generated secret>
BACKEND_CORS_ORIGINS=https://app.ixuan.ai
```

7. Run migration before first production use:

```bash
python3 -m alembic upgrade head
```

Render may support pre-deploy commands depending on plan / setup. If not,
run the migration manually from a secure shell before opening traffic.

## Railway Deployment

1. Create a Railway project from the backend repository.
2. Add a PostgreSQL database plugin.
3. Set environment variables:

```text
ENVIRONMENT=production
APP_ENV=production
DATABASE_URL=<Railway PostgreSQL connection string>
SECRET_KEY=<strong generated secret>
BACKEND_CORS_ORIGINS=https://app.ixuan.ai
```

4. Configure start command:

```bash
python3 -m uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

5. Run migrations:

```bash
python3 -m alembic upgrade head
```

6. Verify:

```bash
curl https://<backend-public-url>/health
curl https://<backend-public-url>/readyz
```

## Frontend Connection

After backend deployment succeeds, configure the production frontend Vercel
project with:

```text
IXAI_BACKEND_URL=https://<backend-public-url>
```

Then redeploy `app/ixai-web-app`.

The frontend should verify:

```text
GET /api/backend/health
```

Expected:

```json
{
  "ok": true,
  "backendUrlConfigured": true,
  "source": "ixai-backend"
}
```

## Security Notes

- Do not commit secrets.
- Do not expose backend protected routes directly to browsers.
- Keep account linking separate from paid Pro entitlement.
- Add trusted server-to-server authentication before exposing sensitive
  integration endpoints beyond the current controlled foundation.
