"""CLI flow for Multi-Language (Nursery System) — the shared platform selector."""

from __future__ import annotations

import logging
from typing import Any

from education_system.systems.nursery.interfaces import multi_language as data

logger = logging.getLogger(__name__)


def _pause() -> None:
    try:
        input("\n  Press Enter to continue...")
    except (EOFError, KeyboardInterrupt):
        pass


def run(auth: Any = None) -> None:
    """Pick a language from the shared list and save it as the preference."""
    before, _ = data.current_language()
    code = data.open_selector_cli()
    now, name = data.current_language()
    if code and now != before:
        print(f"\n  Language set to {name} ({now}).")
    else:
        print(f"\n  Language unchanged: {name} ({now}).")


def dispatch(label: str, auth=None) -> bool:
    if label != data.FEATURE_NAME:
        return False
    try:
        run(auth)
    except Exception as e:
        logger.exception("Multi-Language CLI handler crashed")
        print(f"\n  ✗ Could not open {label}: {e}")
        _pause()
    return True
