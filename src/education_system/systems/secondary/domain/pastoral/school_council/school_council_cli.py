"""Moved to ``education_system.systems.secondary.interfaces.cli.pastoral.school_council.school_council_cli``.

Delivery code (screens and terminal menus) lives under ``interfaces/``.
This alias keeps the old import path working: the old name *is* the new
module object, so ``mock.patch`` and ``monkeypatch`` targets still act on
the real module. Delete it once nothing imports the old path.
"""
# layout-shim: education_system.systems.secondary.interfaces.cli.pastoral.school_council.school_council_cli
import importlib as _importlib
import sys as _sys

_sys.modules[__name__] = _importlib.import_module("education_system.systems.secondary.interfaces.cli.pastoral.school_council.school_council_cli")
