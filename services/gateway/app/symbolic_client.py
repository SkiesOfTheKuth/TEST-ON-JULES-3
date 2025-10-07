from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import httpx

from .config import SymbolicEngineSettings

logger = logging.getLogger(__name__)


class SymbolicEngineError(RuntimeError):
    """Raised when the symbolic engine returns an error."""


class SymbolicEngineClient:
    """HTTP client for interacting with the symbolic engine service."""

    def __init__(
        self,
        settings: SymbolicEngineSettings,
        *,
        async_client: Optional[httpx.AsyncClient] = None,
        sync_client: Optional[httpx.Client] = None,
    ) -> None:
        self._settings = settings
        self._async_client = async_client or httpx.AsyncClient(
            base_url=settings.base_url,
            timeout=settings.request_timeout_seconds,
        )
        self._sync_client = sync_client or httpx.Client(
            base_url=settings.base_url,
            timeout=settings.request_timeout_seconds,
        )
        self._owns_async = async_client is None
        self._owns_sync = sync_client is None

    async def compute(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Perform an asynchronous symbolic computation."""

        try:
            response = await self._async_client.post(
                "/symbolic/compute",
                json=payload,
                timeout=self._settings.request_timeout_seconds,
            )
        except httpx.HTTPError as exc:  # pragma: no cover - network issues
            logger.warning("Symbolic engine request failed", exc_info=exc)
            raise SymbolicEngineError(str(exc)) from exc
        return self._handle_response(response)

    def compute_sync(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Perform a synchronous symbolic computation (for Celery workers)."""

        try:
            response = self._sync_client.post(
                "/symbolic/compute",
                json=payload,
                timeout=self._settings.request_timeout_seconds,
            )
        except httpx.HTTPError as exc:  # pragma: no cover - network issues
            logger.warning("Symbolic engine request failed", exc_info=exc)
            raise SymbolicEngineError(str(exc)) from exc
        return self._handle_response(response)

    async def aclose(self) -> None:
        if self._owns_async:
            await self._async_client.aclose()
        if self._owns_sync:
            self._sync_client.close()

    def close(self) -> None:
        if self._owns_sync:
            self._sync_client.close()

    def _handle_response(self, response: httpx.Response) -> Dict[str, Any]:
        if response.status_code == httpx.codes.OK:
            try:
                data = response.json()
            except ValueError as exc:
                raise SymbolicEngineError("symbolic engine returned invalid JSON") from exc
            if not isinstance(data, dict):
                raise SymbolicEngineError("symbolic engine returned unexpected payload")
            return data

        detail: Any
        try:
            detail = response.json()
        except ValueError:
            detail = response.text or response.reason_phrase
        raise SymbolicEngineError(f"symbolic engine error {response.status_code}: {detail}")
