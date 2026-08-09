"""Shared imports and module state for the split implementation."""

from __future__ import annotations

import os

from education_system.systems.university.infrastructure.database.db import sqlite3

from datetime import datetime

# Canonical runtime reports directory (ADR 0018). The old relative walk
# resolved to `systems/data/reports` -- inside the importable package, and
# not where anything else reads reports from.
from education_system.paths import UNIVERSITY_REPORTS_DIR as _REPORTS_DIR

_DATA_REPORTS_DIR = str(_REPORTS_DIR)

import numpy as np

from education_system.systems.university.infrastructure.database.db import get_connection

from education_system.systems.university.infrastructure.i18n import get_text

__all__ = [name for name in globals() if not name.startswith("__") and name != "__all__"]
