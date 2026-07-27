"""
Campus Navigation Module

Provides interactive campus maps, accessible route planning, and location finding
for students, staff, and visitors.

Features:
- Building directory with search and filtering
- Interactive campus map visualization
- Route planning with accessible route options
- "Find nearest" functionality for amenities
- Points of interest (POI) database
- User favorites for frequently visited locations
- Navigation history tracking
- Accessibility features reporting

Sub-modules:
- services: Navigation service layer with pathfinding algorithms
- cli: Command-line interface
- gui: Graphical user interface with interactive map
"""

from education_system.systems.university.domain.operations.campus.campus_navigation.services.navigation_service import NavigationService
from education_system.systems.university.interfaces.cli.operations.campus.campus_navigation.navigation_cli import NavigationCLI

__all__ = [
    'NavigationService',
    'NavigationCLI',
    'NavigationGUI'
]

__version__ = '1.0.0'

# The GUI classes live in the interfaces layer, which imports back into this
# domain package, so an eager re-export here is a circular import. PEP 562
# lazy lookup keeps these names on the package's public surface without the
# cycle: the interfaces module is only imported on first attribute access.
_LAZY_GUI_EXPORTS = {
    "NavigationGUI": "education_system.systems.university.interfaces.gui.operations.campus.campus_navigation.navigation_gui",
}


def __getattr__(name: str):
    module_path = _LAZY_GUI_EXPORTS.get(name)
    if module_path is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    import importlib
    value = getattr(importlib.import_module(module_path), name)
    globals()[name] = value  # cache so subsequent access skips __getattr__
    return value
