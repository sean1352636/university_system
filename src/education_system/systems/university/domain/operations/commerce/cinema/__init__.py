"""
Cinema Module

Provides campus cinema management including screenings,
bookings, concessions, and event scheduling.
"""

from education_system.systems.university.domain.operations.commerce.cinema.services import CinemaService
from education_system.systems.university.interfaces.cli.operations.commerce.cinema import CinemaCLI

__all__ = ['CinemaService', 'CinemaCLI', 'CinemaApp']

# The GUI classes live in the interfaces layer, which imports back into this
# domain package, so an eager re-export here is a circular import. PEP 562
# lazy lookup keeps these names on the package's public surface without the
# cycle: the interfaces module is only imported on first attribute access.
_LAZY_GUI_EXPORTS = {
    "CinemaApp": "education_system.systems.university.interfaces.gui.operations.commerce.cinema",
}


def __getattr__(name: str):
    module_path = _LAZY_GUI_EXPORTS.get(name)
    if module_path is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    import importlib
    value = getattr(importlib.import_module(module_path), name)
    globals()[name] = value  # cache so subsequent access skips __getattr__
    return value
