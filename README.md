# Ceres Identity

Console IAM service: user accounts, resource grants, sessions, and RS256 JWT issuance for the Ceres stack.

## Responsibilities

- Store console user credentials (`users`)
- Store permission grants (`user_grants`)
- Manage login sessions in Redis (`sid`)
- Cache active grants in Redis for `ceres-api`
- Issue slim access tokens (`sub` + `sid`) on login and refresh
- Expose JWKS for resource servers to validate tokens

Identity does **not** store tenant/site/workspace hierarchy. Grant scopes reference UUIDs that exist in the API database.

## Grant vocabulary

| Grant | Meaning |
|-------|---------|
| `ceres:admin` | All actions on all resources |
| `tenant:<uuid>:read` | Read tenant and child sites/workspaces |
| `tenant:<uuid>:write` | Read and write under tenant (implies `:read`) |
| `site:<uuid>:read` | Read site and child workspaces |
| `site:<uuid>:write` | Read and write under site |
| `workspace:<uuid>:read` | Read workspace |
| `workspace:<uuid>:write` | Read and write workspace |

Grants are normalized on write (for example, `:read` is dropped when `:write` exists on the same resource).

## JWT contract

| Claim | Value |
|-------|-------|
| `iss` | `ceres-identity` |
| `sub` | User UUID |
| `sid` | Session UUID (validated in Redis) |
| `aud` | `ceres-api` |
| `email`, `name` | Profile fields |

Access tokens are RS256-signed and do **not** embed grants. Refresh tokens are HS256 cookies (identity-only).

## Sessions and live permission updates

- Each login creates a Redis session (`ceres:identity:session:{sid}`)
- Active grants are cached at `ceres:identity:grants:{user_id}`
- `revoke_user_auth()` invalidates grants cache, all sessions, and refresh tokens for a user

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/v1/auth/login` | Email/password → access token + refresh cookie |
| POST | `/v1/auth/refresh` | Rotate refresh cookie and session; reload grants |
| POST | `/v1/auth/logout` | Revoke refresh session |
| GET | `/v1/auth/me` | Profile + grants from DB (Bearer access token) |
| GET | `/.well-known/jwks.json` | Public signing keys |
| GET | `/health` | Health check |

Via nginx: `/api/identity/v1/auth/login`, etc.

OpenAPI docs: `http://localhost:8001/docs`

## Bootstrap seed

When `CERES_IDENTITY_BOOTSTRAP_SEED=true`:

1. Creates default user (`CERES_IDENTITY_SEED_EMAIL` / `CERES_IDENTITY_SEED_PASSWORD`)
2. Grants `tenant:{CERES_SEED_DEFAULT_TENANT_ID}:write`

Default seed UUIDs are defined in `app/config.py` (shared with ceres-api via `CERES_SEED_DEFAULT_TENANT_ID`). Do not change them after first bootstrap.

## Development

```bash
cd ceres-identity
pip install -r requirements.txt
pytest
```

Docker Compose runs identity on port 8001 as service `identity`.
