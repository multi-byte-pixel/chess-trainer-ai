"""Timing and metrics helpers."""
from __future__ import annotations

import time
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

F = TypeVar("F", bound=Callable[..., Any])


def timed(logger_name: str | None = None) -> Callable[[F], F]:
    """Decorator that logs the duration of a function call."""
    import structlog

    def decorator(func: F) -> F:
        log = structlog.get_logger(logger_name or func.__module__)

        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            start = time.perf_counter()
            try:
                result = await func(*args, **kwargs)
                elapsed = time.perf_counter() - start
                log.debug("function_completed", function=func.__name__, elapsed_ms=round(elapsed * 1000, 2))
                return result
            except Exception as exc:
                elapsed = time.perf_counter() - start
                log.warning("function_failed", function=func.__name__, elapsed_ms=round(elapsed * 1000, 2), error=str(exc))
                raise

        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            start = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                elapsed = time.perf_counter() - start
                log.debug("function_completed", function=func.__name__, elapsed_ms=round(elapsed * 1000, 2))
                return result
            except Exception as exc:
                elapsed = time.perf_counter() - start
                log.warning("function_failed", function=func.__name__, elapsed_ms=round(elapsed * 1000, 2), error=str(exc))
                raise

        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore[return-value]
        return sync_wrapper  # type: ignore[return-value]

    return decorator


class Timer:
    """Simple context-manager timer."""

    def __init__(self) -> None:
        self.elapsed_ms: float = 0.0
        self._start: float = 0.0

    def __enter__(self) -> "Timer":
        self._start = time.perf_counter()
        return self

    def __exit__(self, *_: Any) -> None:
        self.elapsed_ms = round((time.perf_counter() - self._start) * 1000, 2)
