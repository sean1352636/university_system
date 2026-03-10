"""Academic Misconduct Panel GUI module."""

from .academic_misconduct_gui import AcademicMisconductPanel, main
from .database import init_misconduct_tables

__all__ = ['AcademicMisconductPanel', 'init_misconduct_tables', 'main']
