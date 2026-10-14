"""Compatibility façade for the split implementation."""

from . import musicshop_gui_shared as _shared
from .musicshop_gui_shared import *  # noqa: F401,F403

from .musicshop_gui_parts import musicshopgui_init as _part_1_1
from .musicshop_gui_parts import musicshopgui_create_inventory_tab as _part_1_2
from .musicshop_gui_parts import musicshopgui_view_order_details as _part_1_3
from .musicshop_gui_parts import musicshopgui_create_refunds_tab as _part_1_4
from .musicshop_gui_parts import musicshopgui_notify_musicshop_finance_gui as _part_1_5
class MusicShopGUI(_part_1_1.MusicShopGUI, _part_1_2.MusicShopGUI, _part_1_3.MusicShopGUI, _part_1_4.MusicShopGUI, _part_1_5.MusicShopGUI):
    """Music Shop GUI - 25 functions with email, finance, and i18n integration"""
_shared.MusicShopGUI = MusicShopGUI
_shared.__all__.append("MusicShopGUI") if "MusicShopGUI" not in _shared.__all__ else None

from .musicshop_gui_parts import launch_musicshop_gui as _part_2
launch_musicshop_gui = _part_2.launch_musicshop_gui
_shared.launch_musicshop_gui = launch_musicshop_gui
_shared.__all__.append("launch_musicshop_gui") if "launch_musicshop_gui" not in _shared.__all__ else None

_exports = {name: globals()[name] for name in ['MusicShopGUI', 'launch_musicshop_gui']}
for _module in [_part_1_1, _part_1_2, _part_1_3, _part_1_4, _part_1_5, _part_2]:
    _module.__dict__.update(_exports)


# Keep extracted callables synchronized with compatibility-module globals.
for _module in [_part_1_1, _part_1_2, _part_1_3, _part_1_4, _part_1_5, _part_2]:
    _module.__dict__.update({name: value for name, value in globals().items() if not name.startswith("__")})

__all__ = ['MusicShopGUI', 'launch_musicshop_gui']
