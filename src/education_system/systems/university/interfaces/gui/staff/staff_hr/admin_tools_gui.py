"""Compatibility façade for the split implementation."""

from . import admin_tools_gui_shared as _shared
from .admin_tools_gui_shared import *  # noqa: F401,F403

from .admin_tools_gui_parts import admintoolsgui_init as _part_1_1
from .admin_tools_gui_parts import admintoolsgui_process_approval as _part_1_2
from .admin_tools_gui_parts import admintoolsgui_edit_request as _part_1_3
from .admin_tools_gui_parts import admintoolsgui_issue_card as _part_1_4
from .admin_tools_gui_parts import admintoolsgui_return_key as _part_1_5
from .admin_tools_gui_parts import admintoolsgui_check_out_visitor as _part_1_6
class AdminToolsGUI(_part_1_1.AdminToolsGUI, _part_1_2.AdminToolsGUI, _part_1_3.AdminToolsGUI, _part_1_4.AdminToolsGUI, _part_1_5.AdminToolsGUI, _part_1_6.AdminToolsGUI):
    """Administrative tools GUI with document approvals, requests, keys, and visitors."""
_shared.AdminToolsGUI = AdminToolsGUI
_shared.__all__.append("AdminToolsGUI") if "AdminToolsGUI" not in _shared.__all__ else None

from .admin_tools_gui_parts import main as _part_2
main = _part_2.main
_shared.main = main
_shared.__all__.append("main") if "main" not in _shared.__all__ else None

_exports = {name: globals()[name] for name in ['AdminToolsGUI', 'main']}
for _module in [_part_1_1, _part_1_2, _part_1_3, _part_1_4, _part_1_5, _part_1_6, _part_2]:
    _module.__dict__.update(_exports)


# Keep extracted callables synchronized with compatibility-module globals.
for _module in [_part_1_1, _part_1_2, _part_1_3, _part_1_4, _part_1_5, _part_1_6, _part_2]:
    _module.__dict__.update({name: value for name, value in globals().items() if not name.startswith("__")})

__all__ = ['AdminToolsGUI', 'main']

if __name__ == "__main__":
    main()
