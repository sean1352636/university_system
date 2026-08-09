"""
Lost & Found Module

Comprehensive lost and found item management with:
- Lost item reporting with detailed descriptions
- Found item reporting with photo upload
- Automatic matching between lost and found items
- Claim submission and verification process
- Search and filtering capabilities
- Campus security integration
- CLI and GUI interfaces
"""

from education_system.systems.university.domain.operations.campus.lost_found.services.lost_found_service import LostFoundService
from education_system.systems.university.interfaces.cli.operations.campus.lost_found.lost_found_cli import LostFoundCLI, display_lost_found_menu

__all__ = [
    'LostFoundService',
    'LostFoundCLI',
    'display_lost_found_menu',
    'LostFoundGUI',
    'launch_lost_found_gui'
]

# The GUI classes live in the interfaces layer, which imports back into this
# domain package, so an eager re-export here is a circular import. PEP 562
# lazy lookup keeps these names on the package's public surface without the
# cycle: the interfaces module is only imported on first attribute access.
_LAZY_GUI_EXPORTS = {
    "LostFoundGUI": "education_system.systems.university.interfaces.gui.operations.campus.lost_found.lost_found_gui",
    "launch_lost_found_gui": "education_system.systems.university.interfaces.gui.operations.campus.lost_found.lost_found_gui",
}


def __getattr__(name: str):
    module_path = _LAZY_GUI_EXPORTS.get(name)
    if module_path is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    import importlib
    value = getattr(importlib.import_module(module_path), name)
    globals()[name] = value  # cache so subsequent access skips __getattr__
    return value
