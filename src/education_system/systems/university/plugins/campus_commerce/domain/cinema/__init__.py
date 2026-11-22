"""
Cinema Module

Provides campus cinema management including screenings,
bookings, concessions, and event scheduling.
"""

from education_system.systems.university.plugins.campus_commerce.domain.cinema.services import CinemaService

__all__ = ['CinemaService', 'CinemaCLI', 'CinemaApp']

# The GUI and CLI classes live in the interfaces layer, which imports back
# into this domain package, so an eager re-export here is a circular import
# (importing the CLI package first failed). PEP 562 lazy lookup keeps these
# names on the package's public surface without the cycle: the interfaces
# module is only imported on first attribute access.
_LAZY_GUI_EXPORTS = {
    "CinemaApp": "education_system.systems.university.plugins.campus_commerce.interfaces.gui.cinema",
    "CinemaCLI": "education_system.systems.university.plugins.campus_commerce.interfaces.cli.cinema",
}


def __getattr__(name: str):
    module_path = _LAZY_GUI_EXPORTS.get(name)
    if module_path is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    import importlib
    value = getattr(importlib.import_module(module_path), name)
    globals()[name] = value  # cache so subsequent access skips __getattr__
    return value
