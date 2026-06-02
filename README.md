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
