"""Moved to ``education_system.systems.primary.interfaces.gui.assessment.phonics_screening.phonics_screening_views``.

Delivery code (screens and terminal menus) lives under ``interfaces/``.
This alias keeps the old import path working: the old name *is* the new
module object, so ``mock.patch`` and ``monkeypatch`` targets still act on
the real module. Delete it once nothing imports the old path.
"""
# layout-shim: education_system.systems.primary.interfaces.gui.assessment.phonics_screening.phonics_screening_views
import importlib as _importlib
import sys as _sys

_sys.modules[__name__] = _importlib.import_module("education_system.systems.primary.interfaces.gui.assessment.phonics_screening.phonics_screening_views")
