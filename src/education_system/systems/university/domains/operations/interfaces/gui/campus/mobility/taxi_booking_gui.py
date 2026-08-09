"""Compatibility façade for the split implementation."""

from . import taxi_booking_gui_shared as _shared
from .taxi_booking_gui_shared import *  # noqa: F401,F403

from .taxi_booking_gui_parts import database as _part_1
Database = _part_1.Database
_shared.Database = Database
_shared.__all__.append("Database") if "Database" not in _shared.__all__ else None

from .taxi_booking_gui_parts import modernstyle as _part_2
ModernStyle = _part_2.ModernStyle
_shared.ModernStyle = ModernStyle
_shared.__all__.append("ModernStyle") if "ModernStyle" not in _shared.__all__ else None

from .taxi_booking_gui_parts import taxibookingapp_init as _part_3_1
from .taxi_booking_gui_parts import taxibookingapp_create_service_card as _part_3_2
from .taxi_booking_gui_parts import taxibookingapp_show_receipt as _part_3_3
from .taxi_booking_gui_parts import taxibookingapp_process_taxi_refund as _part_3_4
from .taxi_booking_gui_parts import taxibookingapp_notify_taxi_finance_gui as _part_3_5
class TaxiBookingApp(_part_3_1.TaxiBookingApp, _part_3_2.TaxiBookingApp, _part_3_3.TaxiBookingApp, _part_3_4.TaxiBookingApp, _part_3_5.TaxiBookingApp):
    """Main application class"""
_shared.TaxiBookingApp = TaxiBookingApp
_shared.__all__.append("TaxiBookingApp") if "TaxiBookingApp" not in _shared.__all__ else None

from .taxi_booking_gui_parts import main as _part_4
main = _part_4.main
_shared.main = main
_shared.__all__.append("main") if "main" not in _shared.__all__ else None

_exports = {name: globals()[name] for name in ['Database', 'ModernStyle', 'TaxiBookingApp', 'main']}
for _module in [_part_1, _part_2, _part_3_1, _part_3_2, _part_3_3, _part_3_4, _part_3_5, _part_4]:
    _module.__dict__.update(_exports)


# Keep extracted callables synchronized with compatibility-module globals.
for _module in [_part_1, _part_2, _part_3_1, _part_3_2, _part_3_3, _part_3_4, _part_3_5, _part_4]:
    _module.__dict__.update({name: value for name, value in globals().items() if not name.startswith("__")})

__all__ = ['Database', 'ModernStyle', 'TaxiBookingApp', 'main']

if __name__ == "__main__":
    main()
