"""Compatibility façade for the split implementation."""

from . import admin_tools_manager_shared as _shared
from .admin_tools_manager_shared import *  # noqa: F401,F403

from .admin_tools_manager_parts import admintoolsmanager_init as _part_1_1
from .admin_tools_manager_parts import admintoolsmanager_load_integrity_cases as _part_1_2
from .admin_tools_manager_parts import admintoolsmanager_show_accommodations as _part_1_3
from .admin_tools_manager_parts import admintoolsmanager_remove_ta_assignment as _part_1_4
from .admin_tools_manager_parts import admintoolsmanager_build_ta_permissions_tab as _part_1_5
class AdminToolsManager(_part_1_1.AdminToolsManager, _part_1_2.AdminToolsManager, _part_1_3.AdminToolsManager, _part_1_4.AdminToolsManager, _part_1_5.AdminToolsManager):
    """Admin tools for assignment system management"""
    PERMISSION_TYPES = [
        ('grade_assignments', 'Grade Assignments'),
        ('take_attendance', 'Take Attendance'),
        ('upload_materials', 'Upload Materials'),
        ('manage_discussions', 'Manage Discussions'),
        ('view_student_info', 'View Student Info'),
    ]
_shared.AdminToolsManager = AdminToolsManager
_shared.__all__.append("AdminToolsManager") if "AdminToolsManager" not in _shared.__all__ else None

_exports = {name: globals()[name] for name in ['AdminToolsManager']}
for _module in [_part_1_1, _part_1_2, _part_1_3, _part_1_4, _part_1_5]:
    _module.__dict__.update(_exports)


# Keep extracted callables synchronized with compatibility-module globals.
for _module in [_part_1_1, _part_1_2, _part_1_3, _part_1_4, _part_1_5]:
    _module.__dict__.update({name: value for name, value in globals().items() if not name.startswith("__")})

__all__ = ['AdminToolsManager']
