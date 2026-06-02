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

v1.55 adds the membership foundation migration:

```text
0010_membership_foundation
```

It creates:

- `subscriptions`
- `entitlements`

Apply through the protected migration path only:

```bash
python3 -m alembic upgrade head
```

Do not reintroduce the v1.54.5 unauthenticated migration bootstrap endpoint for
this or future migrations.

## v1.55.1 Production Migration Finalize

v1.55.1 verifies that production PostgreSQL has moved from
`0009_supabase_account_link` to `0010_membership_foundation`.

Temporary verification endpoint:

```text
GET /admin/migration-status
```

This endpoint is read-only. It reports:

- current Alembic revision
- expected revision
- Alembic heads
- presence of `users`, `accounts`, `account_memberships`,
  `subscriptions`, and `entitlements`

It must not execute migrations and must not expose secrets or database URLs.
It is temporary internal debug only and should be removed after production
migration verification is complete or replaced with protected ops tooling.

Expected successful production result:

```json
{
  "ok": true,
  "currentRevision": "0010_membership_foundation",
  "expectedRevision": "0010_membership_foundation",
  "tables": {
    "accounts": true,
    "account_memberships": true,
    "users": true,
    "subscriptions": true,
    "entitlements": true
  }
}
```

## v1.55.2 Production Migration Execution

Production status before v1.55.2 execution was observed as either `0009` during
manual inspection or `0008` during follow-up verification. The Alembic chain is
linear:

```text
0008_fcn_coupon_sched
→ 0009_supabase_account_link
→ 0010_membership_foundation
```

Observed production state:

```text
currentRevision = 0008_fcn_coupon_sched or 0009_supabase_account_link
expectedRevision = 0010_membership_foundation
subscriptions = false
entitlements = false
```

Because Render Free may not provide Shell / One-Off Jobs, v1.55.2 adds a
temporary protected migration executor:

```text
POST /admin/run-membership-migration
```

Security model:

- Requires `MIGRATION_BOOTSTRAP_TOKEN` to be set in the backend environment.
- Requires request header `X-IXAI-MIGRATION-TOKEN`.
- Returns `403` if the token env var is missing.
- Returns `403` if the caller token does not match.
- Runs only `alembic upgrade head`.
- Refuses execution unless the current revision is `0008_fcn_coupon_sched`,
  `0009_supabase_account_link`, or the database is already migrated.
- Does not expose database URLs, secrets, or token values.

Render execution sequence:

1. Deploy backend containing v1.55.2.
2. In Render environment variables, temporarily set:

```text
MIGRATION_BOOTSTRAP_TOKEN=<strong one-time token>
```

3. Verify status:

```bash
curl https://ixai-backend.onrender.com/admin/migration-status
```

4. Execute migration:

```bash
curl -X POST https://ixai-backend.onrender.com/admin/run-membership-migration \
  -H "X-IXAI-MIGRATION-TOKEN: <strong one-time token>"
```

5. Verify status again:

```bash
curl https://ixai-backend.onrender.com/admin/migration-status
```

Expected final result:

```text
currentRevision = 0010_membership_foundation
subscriptions = true
entitlements = true
```

6. Verify account-link and membership:

```bash
curl -X POST https://ixai-backend.onrender.com/api/v1/integrations/supabase/account-link \
  -H "content-type: application/json" \
  -d '{"provider":"supabase","external_user_id":"<test-id>","email":"<masked-test-email>","name":"Migration Check"}'

curl "https://ixai-backend.onrender.com/api/v1/membership/me?provider=supabase&external_user_id=<test-id>"
```

7. Remove `MIGRATION_BOOTSTRAP_TOKEN` from Render.
8. Deploy cleanup code that removes both temporary admin migration endpoints.

Risk assessment:

- The endpoint is temporary and should never remain in production long-term.
- Token must be strong, one-time, and removed immediately after migration.
- If migration returns a non-0010 status, stop and inspect Render logs before
  retrying.
- Do not use this endpoint for future routine migrations; prefer protected
  CI/CD, Render paid Shell / Jobs, Railway one-off commands, or internal ops
  tooling with strong authentication.

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

After v1.55 membership migration is applied, the frontend can also verify the
sanitized membership proxy:

```text
GET /api/pro/membership
```

This route requires a valid Supabase Bearer token from the IXAI App browser
session and must not unlock Portfolio / FCN unless backend entitlements allow it.

## Security Notes

- Do not commit secrets.
- Do not expose backend protected routes directly to browsers.
- Keep account linking separate from paid Pro entitlement.
- Keep membership lookup behind the IXAI App Next API proxy.
- Linked account defaults to Free; paid Pro requires future entitlement or billing.
- Add trusted server-to-server authentication before exposing sensitive
  integration endpoints beyond the current controlled foundation.
