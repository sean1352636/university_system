"""Compatibility façade for the split implementation."""

from . import research_grants_gui_shared as _shared
from .research_grants_gui_shared import *  # noqa: F401,F403

from .research_grants_gui_parts import researchgrantsgui_init as _part_1_1
from .research_grants_gui_parts import researchgrantsgui_load_projects as _part_1_2
from .research_grants_gui_parts import researchgrantsgui_add_team_member as _part_1_3
from .research_grants_gui_parts import researchgrantsgui_add_publication as _part_1_4
from .research_grants_gui_parts import researchgrantsgui_add_equipment as _part_1_5
class ResearchGrantsGUI(_part_1_1.ResearchGrantsGUI, _part_1_2.ResearchGrantsGUI, _part_1_3.ResearchGrantsGUI, _part_1_4.ResearchGrantsGUI, _part_1_5.ResearchGrantsGUI):
    """Research & Grants Management GUI Application"""
_shared.ResearchGrantsGUI = ResearchGrantsGUI
_shared.__all__.append("ResearchGrantsGUI") if "ResearchGrantsGUI" not in _shared.__all__ else None

from .research_grants_gui_parts import launch_research_grants_gui as _part_2
launch_research_grants_gui = _part_2.launch_research_grants_gui
_shared.launch_research_grants_gui = launch_research_grants_gui
_shared.__all__.append("launch_research_grants_gui") if "launch_research_grants_gui" not in _shared.__all__ else None

_exports = {name: globals()[name] for name in ['ResearchGrantsGUI', 'launch_research_grants_gui']}
for _module in [_part_1_1, _part_1_2, _part_1_3, _part_1_4, _part_1_5, _part_2]:
    _module.__dict__.update(_exports)


# Keep extracted callables synchronized with compatibility-module globals.
for _module in [_part_1_1, _part_1_2, _part_1_3, _part_1_4, _part_1_5, _part_2]:
    _module.__dict__.update({name: value for name, value in globals().items() if not name.startswith("__")})

__all__ = ['ResearchGrantsGUI', 'launch_research_grants_gui']
