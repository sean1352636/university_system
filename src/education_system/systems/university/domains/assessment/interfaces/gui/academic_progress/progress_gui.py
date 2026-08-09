"""Compatibility façade for the split implementation."""

from . import progress_gui_shared as _shared
from .progress_gui_shared import *  # noqa: F401,F403

from .progress_gui_parts import academicprogressgui_init as _part_1_1
from .progress_gui_parts import academicprogressgui_create_milestones_tab as _part_1_2
from .progress_gui_parts import academicprogressgui_create_warnings_tab as _part_1_3
from .progress_gui_parts import academicprogressgui_render_transcript as _part_1_4
class AcademicProgressGUI(_part_1_1.AcademicProgressGUI, _part_1_2.AcademicProgressGUI, _part_1_3.AcademicProgressGUI, _part_1_4.AcademicProgressGUI):
    """Graphical interface for Academic Progress Dashboard."""
    _LETTER_THRESHOLDS = [
        (97, 'A+'), (93, 'A'), (90, 'A-'),
        (87, 'B+'), (83, 'B'), (80, 'B-'),
        (77, 'C+'), (73, 'C'), (70, 'C-'),
        (67, 'D+'), (63, 'D'), (60, 'D-'),
        (0, 'F'),
    ]
_shared.AcademicProgressGUI = AcademicProgressGUI
_shared.__all__.append("AcademicProgressGUI") if "AcademicProgressGUI" not in _shared.__all__ else None

_exports = {name: globals()[name] for name in ['AcademicProgressGUI']}
for _module in [_part_1_1, _part_1_2, _part_1_3, _part_1_4]:
    _module.__dict__.update(_exports)


# Keep extracted callables synchronized with compatibility-module globals.
for _module in [_part_1_1, _part_1_2, _part_1_3, _part_1_4]:
    _module.__dict__.update({name: value for name, value in globals().items() if not name.startswith("__")})

__all__ = ['AcademicProgressGUI']

if __name__ == "__main__":
    gui = AcademicProgressGUI()
    gui.run()
