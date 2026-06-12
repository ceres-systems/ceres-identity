import uuid

ADMIN_SCOPE = "ceres:admin"


def tenant_grant(tenant_id: uuid.UUID, action: str = "read") -> str:
    return f"tenant:{tenant_id}:{action}"


def site_grant(site_id: uuid.UUID, action: str = "read") -> str:
    return f"site:{site_id}:{action}"


def workspace_grant(workspace_id: uuid.UUID, action: str = "read") -> str:
    return f"workspace:{workspace_id}:{action}"
