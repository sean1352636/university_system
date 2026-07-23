"""
Consolidated University System Services

This module provides easy access to all university system services
organized by interface type (GUI, CLI, API).

Organization:
- gui/: All graphical user interface implementations
- cli/: All command line interface implementations
- api/: All REST API implementations

Top-level re-exports (``HealthPortalGUI``, ``display_health_portal_menu``
etc.) are exposed via PEP 562 lazy ``__getattr__``. Eager re-exports
here pulled in the entire health-portal GUI tree, the betting-shop GUI
(through ``services.cli``'s eager package init), ``docx``, ``textract``,
``boto3`` and friends every time *any* code imported
``education_system.post_18.university_system.modules.services`` — including
``bus_migrations`` at launcher startup, costing ~10s on ``run.py --gui``.
"""

from __future__ import annotations

import importlib

__version__ = "8.117.72"
__author__ = "University System Team"
__description__ = "Consolidated University System Services"

_LAZY_GUI = ("HealthPortalGUI",)
_LAZY_CLI = (
    "display_health_portal_menu",
    "view_health_records",
    "schedule_appointment",
    "view_medical_history",
    "manage_emergency_contacts",
    "generate_health_reports",
    "view_vaccination_records",
)


def __getattr__(name):
    if name in _LAZY_GUI:
        try:
            mod = importlib.import_module(
                "education_system.post_18.university_system.modules.services.gui"
            )
            value = getattr(mod, name, None)
        except ImportError:
            value = None
        globals()[name] = value
        return value
    if name in _LAZY_CLI:
        try:
            mod = importlib.import_module(
                "education_system.post_18.university_system.modules.services.cli"
            )
            value = getattr(mod, name, None)
        except ImportError:
            value = None
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
