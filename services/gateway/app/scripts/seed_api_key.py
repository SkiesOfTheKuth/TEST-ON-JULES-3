"""Seed a default API key for local development."""

from __future__ import annotations

import argparse
import asyncio
import os

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.config import GatewaySettings, get_settings
from app.database import get_engine, init_db
from app.models import APIKey
from app.security import hash_api_key

DEFAULT_API_KEY = "calculator-local-dev-key"
DEFAULT_OWNER = "Local Development"
DEFAULT_SCOPES = "calculate"


async def seed_api_key(
    settings: GatewaySettings,
    raw_key: str,
    owner: str,
    scopes: str,
    force: bool,
) -> dict[str, str]:
    await init_db(settings)
    engine = await get_engine(settings)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        key_hash = hash_api_key(raw_key)
        result = await session.execute(select(APIKey).where(APIKey.key_hash == key_hash))
        record = result.scalars().first()

        if record:
            if force:
                record.owner = owner
                record.scopes = scopes
                record.active = True
                record.expires_at = None
                await session.commit()
                status = "updated"
            else:
                status = "unchanged"
            return {"status": status, "owner": record.owner, "scopes": record.scopes}

        api_key = APIKey(
            key_hash=key_hash,
            owner=owner,
            scopes=scopes,
        )
        session.add(api_key)
        await session.commit()
        return {"status": "created", "owner": owner, "scopes": scopes}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed a default API key for the gateway service")
    parser.add_argument(
        "--api-key",
        default=os.getenv("GATEWAY_SEED_API_KEY", DEFAULT_API_KEY),
        help="Raw API key value to persist (default: %(default)s)",
    )
    parser.add_argument(
        "--owner",
        default=os.getenv("GATEWAY_SEED_API_KEY_OWNER", DEFAULT_OWNER),
        help="Owner label for the API key (default: %(default)s)",
    )
    parser.add_argument(
        "--scopes",
        default=os.getenv("GATEWAY_SEED_API_KEY_SCOPES", DEFAULT_SCOPES),
        help="Scopes to associate with the API key (default: %(default)s)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Update the existing API key if it already exists",
    )
    return parser.parse_args()


async def _async_main() -> None:
    args = _parse_args()
    settings = get_settings()
    result = await seed_api_key(settings, args.api_key, args.owner, args.scopes, args.force)
    print(
        "API key %s for owner '%s' with scopes '%s'. Raw key: %s"
        % (result["status"], result["owner"], result["scopes"], args.api_key)
    )


def main() -> None:
    asyncio.run(_async_main())


if __name__ == "__main__":
    main()
