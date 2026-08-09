"""Compatibility façade for the split implementation."""

from . import train_station_gui_shared as _shared
from .train_station_gui_shared import *  # noqa: F401,F403

from .train_station_gui_parts import database as _part_1
Database = _part_1.Database
_shared.Database = Database
_shared.__all__.append("Database") if "Database" not in _shared.__all__ else None

from .train_station_gui_parts import trainstationapp_init as _part_2_1
from .train_station_gui_parts import trainstationapp_complete_purchase as _part_2_2
from .train_station_gui_parts import trainstationapp_show_refunds as _part_2_3
from .train_station_gui_parts import trainstationapp_add_train_refund_to_student_acco as _part_2_4
from .train_station_gui_parts import trainstationapp_export_train_refunds_to_csv as _part_2_5
class TrainStationApp(_part_2_1.TrainStationApp, _part_2_2.TrainStationApp, _part_2_3.TrainStationApp, _part_2_4.TrainStationApp, _part_2_5.TrainStationApp):
    """Main application class"""
_shared.TrainStationApp = TrainStationApp
_shared.__all__.append("TrainStationApp") if "TrainStationApp" not in _shared.__all__ else None

from .train_station_gui_parts import main as _part_3
main = _part_3.main
_shared.main = main
_shared.__all__.append("main") if "main" not in _shared.__all__ else None

_exports = {name: globals()[name] for name in ['Database', 'TrainStationApp', 'main']}
for _module in [_part_1, _part_2_1, _part_2_2, _part_2_3, _part_2_4, _part_2_5, _part_3]:
    _module.__dict__.update(_exports)


# Keep extracted callables synchronized with compatibility-module globals.
for _module in [_part_1, _part_2_1, _part_2_2, _part_2_3, _part_2_4, _part_2_5, _part_3]:
    _module.__dict__.update({name: value for name, value in globals().items() if not name.startswith("__")})

__all__ = ['Database', 'TrainStationApp', 'main']

if __name__ == "__main__":
    main()
