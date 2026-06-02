# IXAI Website

## v1.54.4 Backend Deployment Foundation

The backend is deployment-ready as a FastAPI service with:

- Entry point: `app.main:app`
- Production start command:

```bash
python3 -m uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

- Health checks:

```text
GET /health
GET /readyz
```

Required production environment variables:

```text
DATABASE_URL
SECRET_KEY
BACKEND_CORS_ORIGINS
ENVIRONMENT=production
```

Recommended:

```text
APP_ENV=production
```

Deployment notes:

- Use PostgreSQL for production.
- Run migrations before production traffic:

```bash
python3 -m alembic upgrade head
```

- `DATABASE_URL` supports PostgreSQL; `postgres://` URLs are normalized to
  `postgresql://`.
- `SECRET_KEY` is required in production-like environments.
- `APP_ENV=development` is required if using the local development secret
  fallback.
- CORS must explicitly include the production frontend origin, such as
  `https://app.ixuan.ai`.

See `docs/DEPLOYMENT.md` for Render / Railway deployment steps.

After deployment, set the frontend Vercel environment variable:

```text
IXAI_BACKEND_URL=https://<backend-public-url>
```

Then redeploy `app/ixai-web-app` and verify:

```text
GET /api/backend/health
```

## v1.54.6 Migration Bootstrap Endpoint Removed

v1.54.5 temporarily added `POST /admin/run-migrations` because the Render Free
plan did not provide Shell / One-Off Jobs for running `alembic upgrade head`.

Production result:

- The temporary endpoint was used successfully.
- Production PostgreSQL is migrated to `0009_supabase_account_link (head)`.
- `/account` confirmed backend connectivity and linked account status.

v1.54.6 removed the unauthenticated temporary endpoint. It must not remain
exposed in production.

Future migration operations should use one of:

- protected CI/CD migration step
- paid Render Shell / Jobs
- admin-only internal migration mechanism with strong authentication
- Railway / Render deployment workflow that supports one-off commands

## v1.55.0 Membership Foundation

The backend now includes the first membership / entitlement foundation for IXAI
App ↔ IXAI Pro access control.

New backend tables:

- `subscriptions`
- `entitlements`

Linked Supabase accounts default to:

```text
plan_code = free
status = active
provider = manual
```

Default Free entitlements:

```text
daily_brief = true
weekly_brief = true
watchlist = true
pro_preview = false
portfolio = false
fcn_monitoring = false
risk_engine = false
ai_copilot = false
```

New endpoint:

```text
GET /api/v1/membership/me
```

Supported lookup parameters:

```text
provider=supabase
external_user_id=<supabase_user_id>
```

Response:

```json
{
  "account_id": "...",
  "plan_code": "free",
  "status": "active",
  "entitlements": {
    "daily_brief": true,
    "weekly_brief": true,
    "watchlist": true,
    "pro_preview": false,
    "portfolio": false,
    "fcn_monitoring": false,
    "risk_engine": false,
    "ai_copilot": false
  }
}
```

Important boundaries:

- Linked account does not activate paid Pro access.
- Portfolio and FCN remain disabled by default.
- Stripe / paid entitlement is future work.
- This endpoint is intended for the IXAI App Next API proxy.
- Add trusted server-to-server authentication before exposing sensitive
  membership or account data.

Production migration:

```bash
python3 -m alembic upgrade head
```

The v1.54.5 unauthenticated migration bootstrap endpoint was removed and must
not be reintroduced for v1.55 migrations.

## v1.53 Supabase Account Link Endpoint

The backend now exposes the minimum server-side account-link endpoint expected by
the production IXAI App:

```text
POST /api/v1/integrations/supabase/account-link
```

Request:

```json
{
  "provider": "supabase",
  "external_user_id": "<supabase_user_id>",
  "email": "<email>",
  "name": "<optional display name>"
}
```

Response:

```json
{
  "backend_account_id": "...",
  "backend_user_id": "...",
  "pro_access_status": "connected",
  "created": true
}
```

Important boundaries:

- Supabase remains the primary App identity source.
- This endpoint creates or finds a backend account link only.
- Account linking does not activate paid Pro access.
- `pro_access_status` defaults to `connected`, never `active`.
- Portfolio, FCN, broker data, subscription, and trading workflows remain closed.
- The endpoint does not create a legacy JWT password login for Supabase users.
- Stripe / paid entitlement is future work.

Production security TODO:

- Add trusted server-to-server authentication before production external use.
- Accept requests only from the IXAI App Next server through a shared internal
  token, signed request, mTLS, or equivalent control.
- Do not expose this endpoint as a browser-direct public API.

## v1.53.1 Account Link E2E Verification

Local backend verification used a temporary SQLite database:

```text
/tmp/ixai_v1531_e2e.db
```

Results:

- `GET /health` returned `{"status":"ok"}`.
- `GET /readyz` returned `{"status":"ready","database":"ok"}`.
- First `POST /api/v1/integrations/supabase/account-link` with the test
  Supabase payload returned `created: true`.
- Repeating the same payload returned `created: false`.
- The backend created / found `User`, `Account`, and owner `AccountMembership`.
- `pro_access_status` remained `connected`, not `active`.

Local DB note:

- The existing local `ixai.db` was backed up and then restored because its
  Alembic marker was behind existing tables.
- No destructive local data migration was kept.

## v1.54 Real Account Linking Verification

Local backend verification used a fresh temporary SQLite database:

```text
/tmp/ixai_v154_e2e.db
```

Results:

- Alembic upgraded the temporary DB to `0009_supabase_account_link`.
- `GET /health` returned `{"status":"ok"}`.
- `GET /readyz` returned ready database state.
- First direct `POST /api/v1/integrations/supabase/account-link` returned
  `created: true`.
- Repeating the same payload returned `created: false`.
- The backend created / found `User`, `Account`, and owner `AccountMembership`.
- `pro_access_status` remained `connected`, not `active`.

Frontend verification note:

- The production app health proxy reached this backend when `IXAI_BACKEND_URL`
  was configured.
- Full browser-click linking still requires a real Supabase App session.

## v1.54.1 Real Supabase Session Button Test

Local backend verification used:

```text
/tmp/ixai_v1541_e2e.db
```

Results:

- Alembic upgraded the temporary DB to `0009_supabase_account_link`.
- `GET /health` returned `{"status":"ok"}`.
- `GET /readyz` returned ready database state.
- The frontend health proxy reached this backend with `IXAI_BACKEND_URL`
  configured.
- The frontend account-link route remained closed without a Supabase session.

Blocked:

- No authenticated Supabase App browser session was available locally or in
  production, so the `/account` button-click flow could not be completed.
