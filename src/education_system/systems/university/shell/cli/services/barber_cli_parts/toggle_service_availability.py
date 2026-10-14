"""Moved to ``education_system.systems.university.plugins.campus_commerce.interfaces.cli.services.barber_cli_parts.toggle_service_availability`` (campus commerce plugin).

The old name *is* the new module object, so ``mock.patch`` and
``monkeypatch`` targets still act on the real code. Delete once nothing
imports the old path.
"""
# layout-shim: education_system.systems.university.plugins.campus_commerce.interfaces.cli.services.barber_cli_parts.toggle_service_availability
import importlib as _importlib
import sys as _sys

_sys.modules[__name__] = _importlib.import_module("education_system.systems.university.plugins.campus_commerce.interfaces.cli.services.barber_cli_parts.toggle_service_availability")
