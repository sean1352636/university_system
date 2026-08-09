"""Compatibility façade for the split implementation."""

from . import dialogs_shared as _shared
from .dialogs_shared import *  # noqa: F401,F403

from .dialogs_parts import addscheduledialog_init as _part_1_1
from .dialogs_parts import addscheduledialog_save_schedule as _part_1_2
class AddScheduleDialog(_part_1_1.AddScheduleDialog, _part_1_2.AddScheduleDialog):
    pass
_shared.AddScheduleDialog = AddScheduleDialog
_shared.__all__.append("AddScheduleDialog") if "AddScheduleDialog" not in _shared.__all__ else None

from .dialogs_parts import addroomdialog as _part_2
AddRoomDialog = _part_2.AddRoomDialog
_shared.AddRoomDialog = AddRoomDialog
_shared.__all__.append("AddRoomDialog") if "AddRoomDialog" not in _shared.__all__ else None

from .dialogs_parts import addinstructordialog as _part_3
AddInstructorDialog = _part_3.AddInstructorDialog
_shared.AddInstructorDialog = AddInstructorDialog
_shared.__all__.append("AddInstructorDialog") if "AddInstructorDialog" not in _shared.__all__ else None

from .dialogs_parts import editscheduledialog as _part_4
EditScheduleDialog = _part_4.EditScheduleDialog
_shared.EditScheduleDialog = EditScheduleDialog
_shared.__all__.append("EditScheduleDialog") if "EditScheduleDialog" not in _shared.__all__ else None

from .dialogs_parts import editroomdialog as _part_5
EditRoomDialog = _part_5.EditRoomDialog
_shared.EditRoomDialog = EditRoomDialog
_shared.__all__.append("EditRoomDialog") if "EditRoomDialog" not in _shared.__all__ else None

from .dialogs_parts import editinstructordialog as _part_6
EditInstructorDialog = _part_6.EditInstructorDialog
_shared.EditInstructorDialog = EditInstructorDialog
_shared.__all__.append("EditInstructorDialog") if "EditInstructorDialog" not in _shared.__all__ else None

from .dialogs_parts import addholidaydialog as _part_7
AddHolidayDialog = _part_7.AddHolidayDialog
_shared.AddHolidayDialog = AddHolidayDialog
_shared.__all__.append("AddHolidayDialog") if "AddHolidayDialog" not in _shared.__all__ else None

from .dialogs_parts import gridviewwindow as _part_8
GridViewWindow = _part_8.GridViewWindow
_shared.GridViewWindow = GridViewWindow
_shared.__all__.append("GridViewWindow") if "GridViewWindow" not in _shared.__all__ else None

_exports = {name: globals()[name] for name in ['AddHolidayDialog', 'AddInstructorDialog', 'AddRoomDialog', 'AddScheduleDialog', 'EditInstructorDialog', 'EditRoomDialog', 'EditScheduleDialog', 'GridViewWindow']}
for _module in [_part_1_1, _part_1_2, _part_2, _part_3, _part_4, _part_5, _part_6, _part_7, _part_8]:
    _module.__dict__.update(_exports)


# Keep extracted callables synchronized with compatibility-module globals.
for _module in [_part_1_1, _part_1_2, _part_2, _part_3, _part_4, _part_5, _part_6, _part_7, _part_8]:
    _module.__dict__.update({name: value for name, value in globals().items() if not name.startswith("__")})

__all__ = ['AddHolidayDialog', 'AddInstructorDialog', 'AddRoomDialog', 'AddScheduleDialog', 'EditInstructorDialog', 'EditRoomDialog', 'EditScheduleDialog', 'GridViewWindow']
