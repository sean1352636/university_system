"""
Primary School Management System

A management platform for primary schools (Reception–Year 6, ages 4–11)
covering EYFS, KS1/KS2, phonics, SATs, pupil wellbeing, parent engagement,
and the wider primary-school lifecycle.

Python: 3.11+
Database: SQLite (default)
Architecture: 4-layer domain-driven design — interface → service → infrastructure → data

Part of the Education System monorepo (university, college, secondary, primary).
"""

# Version is authoritative in pyproject.toml; this must stay in sync.
__version__ = "8.70.0"
__author__ = "Education System Team"
__license__ = "MIT"

__all__ = [
    "__version__",
    "__author__",
    "__license__",
]
