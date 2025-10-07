from __future__ import annotations

import multiprocessing as mp
import platform
from typing import Any, Callable


class SandboxError(RuntimeError):
    """Raised when sandbox execution fails."""


class SandboxTimeout(SandboxError):
    """Raised when sandboxed work exceeds the configured time budget."""


class SandboxMemoryExceeded(SandboxError):
    """Raised when sandboxed work exceeds the configured memory budget."""


class SandboxRunner:
    def __init__(self, timeout_seconds: float, memory_mb: int):
        self._timeout = timeout_seconds
        self._memory_mb = memory_mb
        self._ctx = mp.get_context("spawn")

    def run(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        queue: mp.Queue[Any] = self._ctx.Queue()
        process = self._ctx.Process(
            target=_worker,
            args=(queue, func, args, kwargs, self._memory_mb),
        )
        process.start()
        process.join(self._timeout)
        if process.is_alive():
            process.kill()
            process.join()
            raise SandboxTimeout(f"Function {func.__name__} exceeded {self._timeout}s budget")

        if not queue.empty():
            status, payload = queue.get_nowait()
            if status == "error":
                if isinstance(payload, MemoryError):
                    raise SandboxMemoryExceeded("Symbolic execution exceeded memory budget")
                if isinstance(payload, BaseException):
                    raise payload
                raise SandboxError(str(payload))
            if status == "memory":
                raise SandboxMemoryExceeded(payload)
            return payload

        if process.exitcode not in (0, None):
            raise SandboxError(f"Sandboxed process exited with code {process.exitcode}")
        raise SandboxError("Sandboxed process produced no result")


def _apply_memory_limit(memory_mb: int) -> None:
    if memory_mb <= 0:
        return
    if platform.system() == "Windows":
        return  # Hard memory limits require Job Objects / psutil; documented as a follow-up.
    try:
        import resource
    except ImportError:  # pragma: no cover
        return

    bytes_limit = memory_mb * 1024 * 1024
    resource.setrlimit(resource.RLIMIT_AS, (bytes_limit, bytes_limit))


def _worker(
    queue: mp.Queue[Any],
    func: Callable[..., Any],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    memory_mb: int,
) -> None:
    try:
        _apply_memory_limit(memory_mb)
        result = func(*args, **kwargs)
        queue.put(("ok", result))
    except MemoryError as exc:  # pragma: no cover - platform dependent
        queue.put(("error", exc))
    except Exception as exc:  # propagate actual exception objects
        queue.put(("error", exc))
