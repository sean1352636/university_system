"""Compatibility façade for the split implementation."""

from . import lms_tab_shared as _shared
from .lms_tab_shared import *  # noqa: F401,F403

from .lms_tab_parts import lmstabmixin_lms_switch_to_cli as _part_1_1
from .lms_tab_parts import lmstabmixin_lms_add_video as _part_1_2
from .lms_tab_parts import lmstabmixin_lms_create_quiz as _part_1_3
from .lms_tab_parts import lmstabmixin_create_lms_modules_subtab as _part_1_4
from .lms_tab_parts import lmstabmixin_sh_start_quiz as _part_1_5
class LMSTabMixin(_part_1_1.LMSTabMixin, _part_1_2.LMSTabMixin, _part_1_3.LMSTabMixin, _part_1_4.LMSTabMixin, _part_1_5.LMSTabMixin):
    """Adds an LMS tab with sub-notebook to the course management GUI."""
_shared.LMSTabMixin = LMSTabMixin
_shared.__all__.append("LMSTabMixin") if "LMSTabMixin" not in _shared.__all__ else None

_exports = {name: globals()[name] for name in ['LMSTabMixin']}
for _module in [_part_1_1, _part_1_2, _part_1_3, _part_1_4, _part_1_5]:
    _module.__dict__.update(_exports)


# Keep extracted callables synchronized with compatibility-module globals.
for _module in [_part_1_1, _part_1_2, _part_1_3, _part_1_4, _part_1_5]:
    _module.__dict__.update({name: value for name, value in globals().items() if not name.startswith("__")})

__all__ = ['LMSTabMixin']
