"""Academic Misconduct Panel — shared across all education systems.

Provides case management, evidence handling with chain-of-custody tracking,
hearing scheduling, decisions, analytics, and notifications.
"""

from education_system.shared.academic_misconduct.academic_misconduct_gui import AcademicMisconductPanel, main
from education_system.shared.academic_misconduct.database import init_misconduct_tables

__all__ = ['AcademicMisconductPanel', 'init_misconduct_tables', 'main']
