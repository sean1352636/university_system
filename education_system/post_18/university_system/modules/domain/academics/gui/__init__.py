"""
Academics GUI Module

GUI interfaces for academic management.

Launchers are exposed via PEP 562 lazy ``__getattr__`` so that importing
this package (e.g. via ``_event_bus`` from the cross-domain bus modules
during launcher startup) does not pull in the entire AI-detector view
tree, ``docx``, ``textract`` etc. before any user has opened a GUI.
Eager imports here added ~3.8s to ``run.py --gui`` startup.
"""

from __future__ import annotations

import importlib

__all__ = [
    'launch_blockchain_credentials_gui',
    'GradeTrackingManagementGUI',
    'CalendarGUI',
    'ai_detector_gui',
]

_LAZY = {
    'launch_blockchain_credentials_gui': (
        'education_system.post_18.university_system.modules.domain.academics.gui.blockchain_credentials_gui',
        'launch_blockchain_credentials_gui',
    ),
    'GradeTrackingManagementGUI': (
        'education_system.post_18.university_system.modules.domain.academics.gui.grade_tracking_management_gui',
        'GradeTrackingManagementGUI',
    ),
    'CalendarGUI': (
        'education_system.post_18.university_system.modules.domain.academics.gui.academic_calendar.main_gui',
        'CalendarGUI',
    ),
    'ai_detector_gui': (
        'education_system.post_18.university_system.modules.domain.academics.gui.ai_detector_gui',
        None,
    ),
}


def __getattr__(name):
    spec = _LAZY.get(name)
    if spec is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_path, attr = spec
    try:
        mod = importlib.import_module(module_path)
    except ImportError:
        globals()[name] = None
        return None
    value = mod if attr is None else getattr(mod, attr, None)
    globals()[name] = value
    return value
