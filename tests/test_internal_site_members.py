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
            "grant_action": "read",
        },
    )
    assert create.status_code == 201
    created = create.json()
    user_id = created["id"]
    assert created["email"] == "staff@localhost"
    assert created["display_name"] == "staff"
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
        },
    )
    assert patch.status_code == 200
    assert patch.json()["grant_action"] == "write"

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
async def test_create_existing_email_returns_409(client) -> None:
    ac, _ = client
    site_id = uuid.uuid4()
    payload = {
        "site_id": str(site_id),
        "email": "exists@localhost",
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
        json={**payload, "site_id": str(uuid.uuid4())},
    )
    assert second.status_code == 409
    assert second.json()["detail"] == "Email already registered"


@pytest.mark.asyncio
async def test_add_existing_user_to_second_site(client) -> None:
    ac, _ = client
    site_a = uuid.uuid4()
    site_b = uuid.uuid4()
    payload = {
        "email": "multi@localhost",
        "grant_action": "write",
    }
    first = await ac.post(
        "/internal/v1/site-members",
        headers=INTERNAL_HEADERS,
        json={**payload, "site_id": str(site_a)},
    )
    assert first.status_code == 201
    first_body = first.json()

    second = await ac.post(
        "/internal/v1/site-members/add",
        headers=INTERNAL_HEADERS,
        json={**payload, "site_id": str(site_b)},
    )
    assert second.status_code == 201
    second_body = second.json()
    assert second_body["id"] == first_body["id"]
    assert second_body["email"] == "multi@localhost"

    site_a_members = await ac.get(
        f"/internal/v1/site-members?site_id={site_a}",
        headers=INTERNAL_HEADERS,
    )
    site_b_members = await ac.get(
        f"/internal/v1/site-members?site_id={site_b}",
        headers=INTERNAL_HEADERS,
    )
    assert len(site_a_members.json()) == 1
    assert len(site_b_members.json()) == 1


@pytest.mark.asyncio
async def test_add_unknown_email_returns_404(client) -> None:
    ac, _ = client
    res = await ac.post(
        "/internal/v1/site-members/add",
        headers=INTERNAL_HEADERS,
        json={
            "site_id": str(uuid.uuid4()),
            "email": "missing@localhost",
            "grant_action": "read",
        },
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_add_duplicate_site_membership_returns_409(client) -> None:
    ac, _ = client
    site_id = uuid.uuid4()
    payload = {
        "site_id": str(site_id),
        "email": "dup@localhost",
        "grant_action": "write",
    }
    create = await ac.post(
        "/internal/v1/site-members",
        headers=INTERNAL_HEADERS,
        json=payload,
    )
    assert create.status_code == 201

    add = await ac.post(
        "/internal/v1/site-members/add",
        headers=INTERNAL_HEADERS,
        json={**payload, "grant_action": "read"},
    )
    assert add.status_code == 409
    assert add.json()["detail"] == "Already a member of this site"
