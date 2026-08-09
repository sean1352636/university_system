"""Measured deprecation registry for replaced shared implementations."""

from __future__ import annotations

import threading
import warnings
from collections import Counter

_lock = threading.Lock()
_calls: Counter[str] = Counter()


def record_legacy_call(capability: str, implementation: str) -> None:
    key = f"{capability}:{implementation}"
    with _lock:
        _calls[key] += 1
    warnings.warn(
        f"{implementation} is deprecated; use the platform {capability} port",
        DeprecationWarning,
        stacklevel=2,
    )


def legacy_usage() -> dict[str, int]:
    with _lock:
        return dict(_calls)


def removable(capability: str, implementation: str) -> bool:
    """Removal is permitted only when the observation window reports zero."""
    with _lock:
        return _calls[f"{capability}:{implementation}"] == 0


__all__ = ["legacy_usage", "record_legacy_call", "removable"]
