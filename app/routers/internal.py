from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.schemas.internal import (
    SetUserPinRequest,
    SiteMemberAdd,
    SiteMemberCreate,
    SiteMemberRead,
    SiteMemberUpdate,
)
from app.security.internal_auth import verify_internal_api_key
from app.services.site_members import (
    add_site_member,
    create_site_member,
    delete_site_member,
    list_site_members,
    set_user_pin,
    update_site_member,
)

router = APIRouter(
    prefix="/internal/v1",
    tags=["internal"],
    dependencies=[Depends(verify_internal_api_key)],
)

SessionDep = Annotated[AsyncSession, Depends(get_session)]


def _redis(request: Request) -> Redis:
    return request.app.state.redis


RedisDep = Annotated[Redis, Depends(_redis)]


@router.get("/site-members", response_model=list[SiteMemberRead])
async def get_site_members(
    session: SessionDep,
    site_id: Annotated[UUID, Query()],
) -> list[SiteMemberRead]:
    return await list_site_members(session, site_id)


@router.post(
    "/site-members",
    response_model=SiteMemberRead,
    status_code=status.HTTP_201_CREATED,
)
async def post_site_member(
    body: SiteMemberCreate,
    session: SessionDep,
    redis: RedisDep,
) -> SiteMemberRead:
    return await create_site_member(session, redis, body)


@router.post(
    "/site-members/add",
    response_model=SiteMemberRead,
    status_code=status.HTTP_201_CREATED,
)
async def post_site_member_add(
    body: SiteMemberAdd,
    session: SessionDep,
    redis: RedisDep,
) -> SiteMemberRead:
    return await add_site_member(session, redis, body)


@router.patch("/site-members/{user_id}", response_model=SiteMemberRead)
async def patch_site_member(
    user_id: UUID,
    body: SiteMemberUpdate,
    session: SessionDep,
    redis: RedisDep,
) -> SiteMemberRead:
    return await update_site_member(session, redis, user_id, body)


@router.put("/users/{user_id}/pin", status_code=status.HTTP_204_NO_CONTENT)
async def put_user_pin(
    user_id: UUID,
    body: SetUserPinRequest,
    session: SessionDep,
    redis: RedisDep,
) -> None:
    await set_user_pin(session, redis, user_id, body.site_id, body.pin)


@router.delete("/site-members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_site_member(
    user_id: UUID,
    session: SessionDep,
    redis: RedisDep,
    site_id: Annotated[UUID, Query()],
) -> None:
    await delete_site_member(session, redis, user_id, site_id)
