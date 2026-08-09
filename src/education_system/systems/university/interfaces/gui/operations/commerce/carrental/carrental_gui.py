"""Compatibility façade for the split implementation."""

from . import carrental_gui_shared as _shared
from .carrental_gui_shared import *  # noqa: F401,F403

from .carrental_gui_parts import carrentalgui_init as _part_1_1
from .carrental_gui_parts import carrentalgui_create_reports_tab as _part_1_2
from .carrental_gui_parts import carrentalgui_return_vehicle_with_payment as _part_1_3
from .carrental_gui_parts import carrentalgui_email_admin_report as _part_1_4
from .carrental_gui_parts import carrentalgui_complete_carrental_refund as _part_1_5
from .carrental_gui_parts import carrentalgui_export_refunds_to_csv as _part_1_6
class CarRentalGUI(_part_1_1.CarRentalGUI, _part_1_2.CarRentalGUI, _part_1_3.CarRentalGUI, _part_1_4.CarRentalGUI, _part_1_5.CarRentalGUI, _part_1_6.CarRentalGUI):
    """Car Rental System GUI - 25 functions"""
_shared.CarRentalGUI = CarRentalGUI
_shared.__all__.append("CarRentalGUI") if "CarRentalGUI" not in _shared.__all__ else None

from .carrental_gui_parts import launch_carrental_gui as _part_2
launch_carrental_gui = _part_2.launch_carrental_gui
_shared.launch_carrental_gui = launch_carrental_gui
_shared.__all__.append("launch_carrental_gui") if "launch_carrental_gui" not in _shared.__all__ else None

_exports = {name: globals()[name] for name in ['CarRentalGUI', 'launch_carrental_gui']}
for _module in [_part_1_1, _part_1_2, _part_1_3, _part_1_4, _part_1_5, _part_1_6, _part_2]:
    _module.__dict__.update(_exports)


# Keep extracted callables synchronized with compatibility-module globals.
for _module in [_part_1_1, _part_1_2, _part_1_3, _part_1_4, _part_1_5, _part_1_6, _part_2]:
    _module.__dict__.update({name: value for name, value in globals().items() if not name.startswith("__")})

__all__ = ['CarRentalGUI', 'launch_carrental_gui']
