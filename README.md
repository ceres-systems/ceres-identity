# Ceres Identity

Console IAM service: user accounts, resource grants, and RS256 JWT issuance for the Ceres stack.

## Responsibilities

- Store console user credentials (`users`)
- Store permission grants as opaque scope strings (`user_grants`)
- Issue access tokens with `aud` and `scope` claims on login and refresh
- Expose JWKS for resource servers (e.g. `ceres-api`) to validate tokens

Identity does **not** store tenant/site/workspace hierarchy. Grant scopes reference UUIDs that exist in the API database.

## Scope vocabulary

| Scope | Meaning |
|-------|---------|
| `tenant:<uuid>` | Tenant and all sites/workspaces under it (enforced by API via hierarchy) |
| `site:<uuid>` | Site and all workspaces under it |
| `workspace:<uuid>` | Single workspace |
| `ceres:admin` | All resources |

## JWT contract

| Claim | Value |
|-------|-------|
| `iss` | `ceres-identity` |
| `sub` | User UUID |
| `aud` | `ceres-api` |
| `scope` | Space-delimited active grants |
| `email`, `name` | Profile fields |

Access tokens are RS256-signed. Refresh tokens are HS256 cookies (identity-only).

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/v1/auth/login` | Email/password → access token + refresh cookie |
| POST | `/v1/auth/refresh` | Rotate refresh cookie; re-load grants into new access token |
| POST | `/v1/auth/logout` | Revoke refresh session |
| GET | `/v1/auth/me` | Profile + scopes (Bearer access token) |
| GET | `/.well-known/jwks.json` | Public signing keys |
| GET | `/health` | Health check |

Via nginx: `/api/identity/v1/auth/login`, etc.

## Bootstrap seed

When `CERES_IDENTITY_BOOTSTRAP_SEED=true`:

1. Creates default user (`CERES_IDENTITY_SEED_EMAIL` / `CERES_IDENTITY_SEED_PASSWORD`)
2. Grants `tenant:{CERES_SEED_DEFAULT_TENANT_ID}`

Align `CERES_SEED_DEFAULT_TENANT_ID` and `CERES_SEED_DEFAULT_SITE_ID` with the API seed in `template.env`. Do not change these UUIDs after first bootstrap.

## Hierarchy resolution (API phase 2)

The API validates tokens without calling identity. Inheritance rules:

- `ceres:admin` → allow all
- `tenant:T` → allow tenant T, its sites, and their workspaces
- `site:S` → allow site S and its workspaces
- `workspace:W` → allow workspace W only

Example grants `tenant:tenantA` + `site:siteB1` allow siteA1, siteA2 (via tenantA) and siteB1, but not siteB2.

## Development

```bash
cd ceres-identity
pip install -r requirements.txt
pytest
```

Docker Compose runs identity on port 8001 as service `identity`.

## Phase 2

- `ceres-api` validates identity JWTs and replaces `console_users` / `console_visibility`
- `ceres-console` login targets `/api/identity/v1/auth/*`
- API orchestrates grant management when inviting users to tenants/sites
