"""
Accessibility Services Portal Module

This module provides comprehensive accessibility services for students with disabilities,
ensuring FERPA compliance and privacy throughout all operations.

Features:
- Accommodation request workflow
- Real-time status tracking
- Document management for medical documentation
- Direct messaging with disability services staff
- Faculty notification system
- Accommodation renewal tracking

Submodules:
- services: Business logic and database operations
- cli: Command-line interface
- gui: Graphical user interface
"""

from education_system.systems.university.domain.operations.campus.accessibility.services.accessibility_service import AccessibilityService
from education_system.systems.university.interfaces.cli.operations.campus.accessibility.accessibility_cli import AccessibilityCLI

__all__ = ['AccessibilityService', 'AccessibilityCLI', 'AccessibilityGUI']

# The GUI classes live in the interfaces layer, which imports back into this
# domain package, so an eager re-export here is a circular import. PEP 562
# lazy lookup keeps these names on the package's public surface without the
# cycle: the interfaces module is only imported on first attribute access.
_LAZY_GUI_EXPORTS = {
    "AccessibilityGUI": "education_system.systems.university.interfaces.gui.operations.campus.accessibility.accessibility_gui",
}


def __getattr__(name: str):
    module_path = _LAZY_GUI_EXPORTS.get(name)
    if module_path is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    import importlib
    value = getattr(importlib.import_module(module_path), name)
    globals()[name] = value  # cache so subsequent access skips __getattr__
    return value
