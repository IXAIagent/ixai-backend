# IXAI Website

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
