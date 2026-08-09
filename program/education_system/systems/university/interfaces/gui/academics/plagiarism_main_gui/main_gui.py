"""Compatibility façade for the split implementation."""

from . import main_gui_shared as _shared
from .main_gui_shared import *  # noqa: F401,F403

from .main_gui_parts import plagiarismcheckergui_init as _part_1_1
from .main_gui_parts import plagiarismcheckergui_process_tasks as _part_1_2
from .main_gui_parts import plagiarismcheckergui_get_author_selection_dialog as _part_1_3
from .main_gui_parts import plagiarismcheckergui_create_document_card as _part_1_4
from .main_gui_parts import plagiarismcheckergui_export_documents as _part_1_5
from .main_gui_parts import plagiarismcheckergui_show_plagiarism_email_fallb as _part_1_6
class PlagiarismCheckerGUI(_part_1_1.PlagiarismCheckerGUI, _part_1_2.PlagiarismCheckerGUI, _part_1_3.PlagiarismCheckerGUI, _part_1_4.PlagiarismCheckerGUI, _part_1_5.PlagiarismCheckerGUI, _part_1_6.PlagiarismCheckerGUI):
    """Main GUI application for the plagiarism checker"""
_shared.PlagiarismCheckerGUI = PlagiarismCheckerGUI
_shared.__all__.append("PlagiarismCheckerGUI") if "PlagiarismCheckerGUI" not in _shared.__all__ else None

_exports = {name: globals()[name] for name in ['PlagiarismCheckerGUI']}
for _module in [_part_1_1, _part_1_2, _part_1_3, _part_1_4, _part_1_5, _part_1_6]:
    _module.__dict__.update(_exports)


# Keep extracted callables synchronized with compatibility-module globals.
for _module in [_part_1_1, _part_1_2, _part_1_3, _part_1_4, _part_1_5, _part_1_6]:
    _module.__dict__.update({name: value for name, value in globals().items() if not name.startswith("__")})

__all__ = ['PlagiarismCheckerGUI']
