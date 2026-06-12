from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.services.scopes import ADMIN_SCOPE


@dataclass(frozen=True)
class ParsedGrant:
    resource_type: str
    resource_id: uuid.UUID | None
    action: str | None


def parse_grant(scope: str) -> ParsedGrant:
    if scope == ADMIN_SCOPE:
        return ParsedGrant("ceres", None, None)
    parts = scope.split(":")
    if len(parts) != 3:
        raise ValueError(f"Invalid grant format: {scope}")
    resource_type, raw_id, action = parts
    if resource_type not in {"tenant", "site", "workspace"}:
        raise ValueError(f"Invalid grant resource type: {scope}")
    if action not in {"read", "write"}:
        raise ValueError(f"Invalid grant action: {scope}")
    return ParsedGrant(resource_type, uuid.UUID(raw_id), action)


def _grant_key(parsed: ParsedGrant) -> tuple[str, uuid.UUID | None]:
    return parsed.resource_type, parsed.resource_id


def normalize_grants(scopes: list[str]) -> list[str]:
    if ADMIN_SCOPE in scopes:
        return [ADMIN_SCOPE]

    parsed: list[ParsedGrant] = []
    for scope in scopes:
        try:
            parsed.append(parse_grant(scope))
        except ValueError:
            continue

    best_action: dict[tuple[str, uuid.UUID | None], str] = {}
    for item in parsed:
        key = _grant_key(item)
        if item.action is None:
            continue
        current = best_action.get(key)
        if current is None or (current == "read" and item.action == "write"):
            best_action[key] = item.action

    normalized: list[str] = []
    for (resource_type, resource_id), action in sorted(
        best_action.items(), key=lambda entry: (entry[0][0], str(entry[0][1]))
    ):
        normalized.append(f"{resource_type}:{resource_id}:{action}")
    return normalized
