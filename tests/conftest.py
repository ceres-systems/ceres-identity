from __future__ import annotations

import os

os.environ.setdefault(
    "CERES_IDENTITY_DATABASE_URL",
    "sqlite+aiosqlite:///:memory:",
)
os.environ.setdefault(
    "CERES_IDENTITY_REDIS_URL",
    "redis://127.0.0.1:6379/15",
)
os.environ.setdefault(
    "CERES_IDENTITY_REFRESH_JWT_SECRET",
    "unit-test-refresh-secret-at-least-thirty-two-characters",
)
os.environ.setdefault("CERES_IDENTITY_BOOTSTRAP_SEED", "false")
os.environ.setdefault(
    "CERES_SEED_DEFAULT_TENANT_ID",
    "00000000-0000-4000-8000-000000000001",
)
