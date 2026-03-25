"""Academic Misconduct Panel GUI module.

Thin wrapper — delegates to education_system.shared.academic_misconduct.
"""

from education_system.shared.academic_misconduct import (
    AcademicMisconductPanel,
    init_misconduct_tables,
    main,
)

__all__ = ['AcademicMisconductPanel', 'init_misconduct_tables', 'main']
