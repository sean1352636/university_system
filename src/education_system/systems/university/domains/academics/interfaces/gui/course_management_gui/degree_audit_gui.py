"""Compatibility façade for the split implementation."""

from . import degree_audit_gui_shared as _shared
from .degree_audit_gui_shared import *  # noqa: F401,F403

from .degree_audit_gui_parts import degreeauditgui_init as _part_1_1
from .degree_audit_gui_parts import degreeauditgui_create_advising_tab as _part_1_2
from .degree_audit_gui_parts import degreeauditgui_update_progress as _part_1_3
from .degree_audit_gui_parts import degreeauditgui_analyze_whatif as _part_1_4
from .degree_audit_gui_parts import degreeauditgui_run_graduation_audit as _part_1_5
class DegreeAuditGUI(_part_1_1.DegreeAuditGUI, _part_1_2.DegreeAuditGUI, _part_1_3.DegreeAuditGUI, _part_1_4.DegreeAuditGUI, _part_1_5.DegreeAuditGUI):
    """Main GUI for Degree Audit & Academic Advising System"""
_shared.DegreeAuditGUI = DegreeAuditGUI
_shared.__all__.append("DegreeAuditGUI") if "DegreeAuditGUI" not in _shared.__all__ else None

from .degree_audit_gui_parts import launch_degree_audit_gui as _part_2
launch_degree_audit_gui = _part_2.launch_degree_audit_gui
_shared.launch_degree_audit_gui = launch_degree_audit_gui
_shared.__all__.append("launch_degree_audit_gui") if "launch_degree_audit_gui" not in _shared.__all__ else None

_exports = {name: globals()[name] for name in ['DegreeAuditGUI', 'launch_degree_audit_gui']}
for _module in [_part_1_1, _part_1_2, _part_1_3, _part_1_4, _part_1_5, _part_2]:
    _module.__dict__.update(_exports)


# Keep extracted callables synchronized with compatibility-module globals.
for _module in [_part_1_1, _part_1_2, _part_1_3, _part_1_4, _part_1_5, _part_2]:
    _module.__dict__.update({name: value for name, value in globals().items() if not name.startswith("__")})

__all__ = ['DegreeAuditGUI', 'launch_degree_audit_gui']
