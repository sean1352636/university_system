"""Compatibility façade for the split implementation."""

from . import report_manager_shared as _shared
from .report_manager_shared import *  # noqa: F401,F403

from .report_manager_parts import reportmanager_init as _part_1_1
from .report_manager_parts import reportmanager_export_students_to_file as _part_1_2
from .report_manager_parts import reportmanager_generate_error_analysis_report as _part_1_3
from .report_manager_parts import reportmanager_generate_performance_report as _part_1_4
from .report_manager_parts import reportmanager_generate_comprehensive_report as _part_1_5
class ReportManager(_part_1_1.ReportManager, _part_1_2.ReportManager, _part_1_3.ReportManager, _part_1_4.ReportManager, _part_1_5.ReportManager):
    """Manages reporting operations for BatchOperationsGUI."""
_shared.ReportManager = ReportManager
_shared.__all__.append("ReportManager") if "ReportManager" not in _shared.__all__ else None

_exports = {name: globals()[name] for name in ['ReportManager']}
for _module in [_part_1_1, _part_1_2, _part_1_3, _part_1_4, _part_1_5]:
    _module.__dict__.update(_exports)


# Keep extracted callables synchronized with compatibility-module globals.
for _module in [_part_1_1, _part_1_2, _part_1_3, _part_1_4, _part_1_5]:
    _module.__dict__.update({name: value for name, value in globals().items() if not name.startswith("__")})

__all__ = ['ReportManager']
