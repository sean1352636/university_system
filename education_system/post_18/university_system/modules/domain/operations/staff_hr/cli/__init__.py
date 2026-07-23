"""
Staff HR CLI

Command-line interface for Staff HR features.
"""

from education_system.post_18.university_system.modules.domain.operations.staff_hr.cli.staff_hr_cli import (
    init_staff_hr_db,
    setup_staff_hr_permissions,
    display_staff_hr_menu,
    set_auth,
)

__all__ = [
    'init_staff_hr_db',
    'setup_staff_hr_permissions',
    'display_staff_hr_menu',
    'set_auth',
]
