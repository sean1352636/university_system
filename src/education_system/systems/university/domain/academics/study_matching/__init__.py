"""
Peer Study Matching Module

Intelligent peer matching system that connects students for collaborative learning.

Features:
- Study profile with learning preferences
- AI-powered compatibility matching
- Study group formation and management
- Virtual study rooms with Pomodoro timer
- Anonymous Q&A board
- Comprehensive analytics

Components:
- Service Layer: StudyMatchingService
- CLI Interface: StudyMatchingCLI
- GUI Interface: StudyMatchingGUI
"""

from education_system.systems.university.domain.academics.study_matching.services.study_matching_service import StudyMatchingService
from education_system.systems.university.interfaces.cli.academics.study_matching.study_matching_cli import StudyMatchingCLI

__all__ = [
    'StudyMatchingService',
    'StudyMatchingCLI',
    'StudyMatchingGUI'
]

__version__ = '1.0.0'

# The GUI classes live in the interfaces layer, which imports back into this
# domain package, so an eager re-export here is a circular import. PEP 562
# lazy lookup keeps these names on the package's public surface without the
# cycle: the interfaces module is only imported on first attribute access.
_LAZY_GUI_EXPORTS = {
    "StudyMatchingGUI": "education_system.systems.university.interfaces.gui.academics.study_matching.study_matching_gui",
}


def __getattr__(name: str):
    module_path = _LAZY_GUI_EXPORTS.get(name)
    if module_path is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    import importlib
    value = getattr(importlib.import_module(module_path), name)
    globals()[name] = value  # cache so subsequent access skips __getattr__
    return value
