"""Compatibility façade for the split implementation."""

from . import nailbar_gui_shared as _shared
from .nailbar_gui_shared import *  # noqa: F401,F403

from .nailbar_gui_parts import nailbargui_init as _part_1_1
from .nailbar_gui_parts import nailbargui_create_reports_tab as _part_1_2
from .nailbar_gui_parts import nailbargui_process_payment as _part_1_3
from .nailbar_gui_parts import nailbargui_add_treatment as _part_1_4
from .nailbar_gui_parts import nailbargui_process_nailbar_refund as _part_1_5
from .nailbar_gui_parts import nailbargui_view_refund_transaction_details as _part_1_6
class NailBarGUI(_part_1_1.NailBarGUI, _part_1_2.NailBarGUI, _part_1_3.NailBarGUI, _part_1_4.NailBarGUI, _part_1_5.NailBarGUI, _part_1_6.NailBarGUI):
    """Main GUI class for Nail Bar/Salon operations"""
_shared.NailBarGUI = NailBarGUI
_shared.__all__.append("NailBarGUI") if "NailBarGUI" not in _shared.__all__ else None

from .nailbar_gui_parts import launch_nailbar_gui as _part_2
launch_nailbar_gui = _part_2.launch_nailbar_gui
_shared.launch_nailbar_gui = launch_nailbar_gui
_shared.__all__.append("launch_nailbar_gui") if "launch_nailbar_gui" not in _shared.__all__ else None

_exports = {name: globals()[name] for name in ['NailBarGUI', 'launch_nailbar_gui']}
for _module in [_part_1_1, _part_1_2, _part_1_3, _part_1_4, _part_1_5, _part_1_6, _part_2]:
    _module.__dict__.update(_exports)


# Keep extracted callables synchronized with compatibility-module globals.
for _module in [_part_1_1, _part_1_2, _part_1_3, _part_1_4, _part_1_5, _part_1_6, _part_2]:
    _module.__dict__.update({name: value for name, value in globals().items() if not name.startswith("__")})

__all__ = ['NailBarGUI', 'launch_nailbar_gui']
