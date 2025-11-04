"""
Grade system database utilities.

This module now acts as a compatibility shim, importing from the centralized
database schemas module. All functionality has been moved to:
    university_system.infrastructure.database.schemas
"""

from __future__ import annotations

# Import from centralized schemas
from university_system.infrastructure.database.schemas import (
    init_grade_system_db as init_basic_database
)

__all__ = ['init_basic_database']
