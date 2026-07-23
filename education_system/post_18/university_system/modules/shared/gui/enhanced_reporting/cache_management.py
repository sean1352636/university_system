"""Cache management wrappers for the enhanced reporting GUI.

This module provides a simple functional interface for cache
operations.  Functions mirror the methods on the GUI class and
delegate to them.  These wrappers allow external callers to interact
with cached reports without directly referencing the GUI class.
"""

from __future__ import annotations

from typing import Any

from education_system.post_18.university_system.modules.shared.gui.enhanced_reporting.core import ReportingSystemGUI


def cache_report(gui: ReportingSystemGUI, *args: Any, **kwargs: Any) -> None:
    gui.cache_report(*args, **kwargs)


def get_cached_report(gui: ReportingSystemGUI, *args: Any, **kwargs: Any):
    return gui.get_cached_report(*args, **kwargs)


def get_cache_key(gui: ReportingSystemGUI, *args: Any, **kwargs: Any):
    return gui.get_cache_key(*args, **kwargs)


def cleanup_cache_dialog(gui: ReportingSystemGUI) -> None:
    gui.cleanup_cache_dialog()


__all__ = [
    "cache_report",
    "get_cached_report",
    "get_cache_key",
    "cleanup_cache_dialog",
]