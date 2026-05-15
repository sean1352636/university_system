"""CLI flow for the About screen."""

from __future__ import annotations

import logging
from typing import Any
from education_system.primarysch_system.modules.shared import about as data

logger = logging.getLogger(__name__)


def _pause() -> None:
    try:
        input("\n  Press Enter to continue...")
    except (EOFError, KeyboardInterrupt):
        pass


def run(auth: Any = None) -> None:
    info = data.build(auth=auth)
    print()
    print(data.text_report(info))
    _pause()


def dispatch(label: str, auth=None) -> bool:
    if label != "About":
        return False
    try:
        run(auth)
    except Exception as e:
        logger.exception("About CLI handler crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
