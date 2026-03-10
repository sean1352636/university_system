"""
Student Union database utilities.

This module now acts as a compatibility shim, importing from the centralized
database schemas module. All functionality has been moved to:
    university_system.infrastructure.database.schemas
"""

from __future__ import annotations

# Import from centralized schemas
from education_system.university_system.infrastructure.database.schemas.student_union_schemas import init_student_union_db

__all__ = ['init_student_union_db']
