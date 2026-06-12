from __future__ import annotations

import uuid

import pytest

INTERNAL_KEY = "unit-test-internal-api-key-at-least-thirty-two-characters"
INTERNAL_HEADERS = {"X-Ceres-Internal-Key": INTERNAL_KEY}


@pytest.mark.asyncio
async def test_internal_requires_api_key(client) -> None:
    ac, _ = client
    site_id = uuid.uuid4()
    res = await ac.get(f"/internal/v1/site-members?site_id={site_id}")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_create_list_patch_delete_site_member(client) -> None:
    ac, _ = client
    site_id = uuid.uuid4()

    create = await ac.post(
        "/internal/v1/site-members",
        headers=INTERNAL_HEADERS,
        json={
            "site_id": str(site_id),
            "email": "staff@localhost",
            "password": "password-12chars",
            "display_name": "Staff User",
            "grant_action": "read",
        },
    )
    assert create.status_code == 201
    created = create.json()
    user_id = created["id"]
    assert created["email"] == "staff@localhost"
    assert created["grant_action"] == "read"

    listing = await ac.get(
        f"/internal/v1/site-members?site_id={site_id}",
        headers=INTERNAL_HEADERS,
    )
    assert listing.status_code == 200
    assert len(listing.json()) == 1

    patch = await ac.patch(
        f"/internal/v1/site-members/{user_id}",
        headers=INTERNAL_HEADERS,
        json={
            "site_id": str(site_id),
            "grant_action": "write",
            "display_name": "Staff Lead",
        },
    )
    assert patch.status_code == 200
    assert patch.json()["grant_action"] == "write"
    assert patch.json()["display_name"] == "Staff Lead"

    delete = await ac.delete(
        f"/internal/v1/site-members/{user_id}?site_id={site_id}",
        headers=INTERNAL_HEADERS,
    )
    assert delete.status_code == 204

    listing_after = await ac.get(
        f"/internal/v1/site-members?site_id={site_id}",
        headers=INTERNAL_HEADERS,
    )
    assert listing_after.json() == []


@pytest.mark.asyncio
async def test_create_duplicate_email_returns_409(client) -> None:
    ac, _ = client
    site_id = uuid.uuid4()
    payload = {
        "site_id": str(site_id),
        "email": "dup@localhost",
        "password": "password-12chars",
        "display_name": "First",
        "grant_action": "write",
    }
    first = await ac.post(
        "/internal/v1/site-members",
        headers=INTERNAL_HEADERS,
        json=payload,
    )
    assert first.status_code == 201

    second = await ac.post(
        "/internal/v1/site-members",
        headers=INTERNAL_HEADERS,
        json={**payload, "display_name": "Second"},
    )
    assert second.status_code == 409
