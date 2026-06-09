import uuid

ADMIN_SCOPE = "ceres:admin"


def tenant_scope(tenant_id: uuid.UUID) -> str:
    return f"tenant:{tenant_id}"


def site_scope(site_id: uuid.UUID) -> str:
    return f"site:{site_id}"


def workspace_scope(workspace_id: uuid.UUID) -> str:
    return f"workspace:{workspace_id}"


def parse_scope_list(scope_claim: str) -> list[str]:
    if not scope_claim.strip():
        return []
    return scope_claim.split()
