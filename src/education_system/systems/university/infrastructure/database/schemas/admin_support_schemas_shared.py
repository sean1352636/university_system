"""Shared imports and module state for the split implementation."""

from __future__ import annotations

from datetime import datetime

from education_system.systems.university.infrastructure.database.db import get_connection, sqlite3

from education_system.systems.university.infrastructure.i18n import get_text as _t, init_i18n

init_i18n()

__all__ = [name for name in globals() if not name.startswith("__") and name != "__all__"]
