"""Compatibility façade for the split implementation."""

from . import butcher_gui_shared as _shared
from .butcher_gui_shared import *  # noqa: F401,F403

from .butcher_gui_parts import send_butcher_email as _part_1
_send_butcher_email = _part_1._send_butcher_email
_shared._send_butcher_email = _send_butcher_email
_shared.__all__.append("_send_butcher_email") if "_send_butcher_email" not in _shared.__all__ else None

from .butcher_gui_parts import butchergui_init as _part_2_1
from .butcher_gui_parts import butchergui_create_orders_tab as _part_2_2
from .butcher_gui_parts import butchergui_process_butcher_refund as _part_2_3
from .butcher_gui_parts import butchergui_populate_orders_tree as _part_2_4
from .butcher_gui_parts import butchergui_process_order_payment as _part_2_5
class ButcherGUI(_part_2_1.ButcherGUI, _part_2_2.ButcherGUI, _part_2_3.ButcherGUI, _part_2_4.ButcherGUI, _part_2_5.ButcherGUI):
    """Main GUI class for Butcher Shop operations"""
_shared.ButcherGUI = ButcherGUI
_shared.__all__.append("ButcherGUI") if "ButcherGUI" not in _shared.__all__ else None

from .butcher_gui_parts import launch_butcher_gui as _part_3
launch_butcher_gui = _part_3.launch_butcher_gui
_shared.launch_butcher_gui = launch_butcher_gui
_shared.__all__.append("launch_butcher_gui") if "launch_butcher_gui" not in _shared.__all__ else None

_exports = {name: globals()[name] for name in ['ButcherGUI', '_send_butcher_email', 'launch_butcher_gui']}
for _module in [_part_1, _part_2_1, _part_2_2, _part_2_3, _part_2_4, _part_2_5, _part_3]:
    _module.__dict__.update(_exports)


# Keep extracted callables synchronized with compatibility-module globals.
for _module in [_part_1, _part_2_1, _part_2_2, _part_2_3, _part_2_4, _part_2_5, _part_3]:
    _module.__dict__.update({name: value for name, value in globals().items() if not name.startswith("__")})

__all__ = ['ButcherGUI', '_send_butcher_email', 'launch_butcher_gui']
