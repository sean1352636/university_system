"""
Mental Health & Wellness Module

Provides comprehensive wellness tracking including:
- Mental health check-ins
- Mood tracking with pattern recognition
- Sleep and wellness goals
- Crisis resources
- Exercise and hydration tracking
"""

from education_system.systems.university.domain.pastoral.wellbeing.wellness.services.wellness_service import WellnessService
from education_system.systems.university.interfaces.cli.pastoral.wellbeing.wellness.wellness_cli import WellnessCLI

__all__ = ['WellnessService', 'WellnessCLI', 'WellnessGUI']

# The GUI classes live in the interfaces layer, which imports back into this
# domain package, so an eager re-export here is a circular import. PEP 562
# lazy lookup keeps these names on the package's public surface without the
# cycle: the interfaces module is only imported on first attribute access.
_LAZY_GUI_EXPORTS = {
    "WellnessGUI": "education_system.systems.university.interfaces.gui.pastoral.wellbeing.wellness.wellness_gui",
}


def __getattr__(name: str):
    module_path = _LAZY_GUI_EXPORTS.get(name)
    if module_path is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    import importlib
    value = getattr(importlib.import_module(module_path), name)
    globals()[name] = value  # cache so subsequent access skips __getattr__
    return value
