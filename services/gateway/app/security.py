"""API key management helpers."""

from __future__ import annotations

import datetime as dt
import hashlib
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import APIKey


@dataclass(frozen=True)
class AuthenticatedAPIKey:
    """Wrapper containing the persisted record and the raw presented key."""

    record: APIKey
    raw_key: str


def hash_api_key(raw_key: str) -> str:
    digest = hashlib.sha256()
    digest.update(raw_key.encode("utf-8"))
    return digest.hexdigest()


async def get_api_key(session: AsyncSession, raw_key: str) -> Optional[AuthenticatedAPIKey]:
    key_hash = hash_api_key(raw_key)
    stmt = select(APIKey).where(APIKey.key_hash == key_hash)
    result = await session.execute(stmt)
    api_key = result.scalars().first()
    if not api_key:
        return None
    if not api_key.active:
        return None
    if api_key.expires_at and api_key.expires_at < dt.datetime.utcnow():
        return None
    return AuthenticatedAPIKey(record=api_key, raw_key=raw_key)
