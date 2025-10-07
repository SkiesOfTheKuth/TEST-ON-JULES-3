"""Quota enforcement helpers."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Quota


class QuotaExceededError(RuntimeError):
    """Raised when an API key exceeds its allotted quota."""


@dataclass
class QuotaConfig:
    limit: int
    window_seconds: int


async def consume_quota(session: AsyncSession, api_key_id: int, config: QuotaConfig) -> None:
    """Consume a quota unit for the API key if possible."""

    if config.limit <= 0:
        return

    now = dt.datetime.utcnow()
    window_seconds = max(config.window_seconds, 1)

    tx = session.get_transaction()
    context = session.begin_nested if tx is not None else session.begin

    async with context():
        stmt = (
            select(Quota)
            .where(
                Quota.api_key_id == api_key_id,
                Quota.window_start <= now,
                Quota.window_end > now,
            )
            .with_for_update()
        )
        result = await session.execute(stmt)
        quota = result.scalars().first()

        if quota is None or quota.window_end <= now:
            if quota is None:
                quota = Quota(
                    api_key_id=api_key_id,
                    window_start=now,
                    window_end=now + dt.timedelta(seconds=window_seconds),
                    usage=0,
                    limit=config.limit,
                )
                session.add(quota)
            else:
                quota.window_start = now
                quota.window_end = now + dt.timedelta(seconds=window_seconds)
                quota.usage = 0
                quota.limit = config.limit

        if quota.limit > 0 and quota.usage >= quota.limit:
            raise QuotaExceededError("Quota exceeded for API key")

        quota.usage += 1
