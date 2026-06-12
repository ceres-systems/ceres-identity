import uuid

from app.services.grant_normalize import normalize_grants
from app.services.scopes import ADMIN_SCOPE, site_grant, tenant_grant


def test_normalize_drops_read_when_write_exists() -> None:
    tenant_id = uuid.uuid4()
    scopes = [tenant_grant(tenant_id, "read"), tenant_grant(tenant_id, "write")]
    assert normalize_grants(scopes) == [tenant_grant(tenant_id, "write")]


def test_admin_scope_short_circuits_other_grants() -> None:
    tenant_id = uuid.uuid4()
    scopes = [tenant_grant(tenant_id, "read"), ADMIN_SCOPE, site_grant(uuid.uuid4(), "read")]
    assert normalize_grants(scopes) == [ADMIN_SCOPE]


def test_empty_grants_stay_empty() -> None:
    assert normalize_grants([]) == []
