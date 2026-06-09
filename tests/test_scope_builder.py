import uuid

from app.services.scope_builder import scope_claim_from_grant_list
from app.services.scopes import ADMIN_SCOPE, site_scope, tenant_scope


def test_scope_claim_joins_grants() -> None:
    tenant_a = uuid.UUID("10000000-0000-4000-8000-000000000001")
    site_b1 = uuid.UUID("20000000-0000-4000-8000-000000000001")
    scopes = [tenant_scope(tenant_a), site_scope(site_b1)]
    assert scope_claim_from_grant_list(scopes) == (
        f"tenant:{tenant_a} site:{site_b1}"
    )


def test_mixed_tenant_and_site_grants_example() -> None:
    tenant_a = uuid.UUID("aaaaaaaa-aaaa-4000-8000-000000000001")
    site_b1 = uuid.UUID("bbbbbbbb-bbbb-4000-8000-000000000001")
    claim = scope_claim_from_grant_list([tenant_scope(tenant_a), site_scope(site_b1)])
    assert f"tenant:{tenant_a}" in claim
    assert f"site:{site_b1}" in claim
    assert f"site:{uuid.UUID('bbbbbbbb-bbbb-4000-8000-000000000002')}" not in claim


def test_admin_scope_short_circuits_other_grants() -> None:
    tenant_id = uuid.uuid4()
    scopes = [tenant_scope(tenant_id), ADMIN_SCOPE, site_scope(uuid.uuid4())]
    assert scope_claim_from_grant_list(scopes) == ADMIN_SCOPE


def test_empty_grants_produce_empty_claim() -> None:
    assert scope_claim_from_grant_list([]) == ""
