"""Compatibility shim — the shell lives in ``interfaces/gui/gui_main.py``.

The launcher imports ``<system>.gui_main.run`` for every system, so this
keeps that contract while the implementation sits with the rest of the
GUI.
"""
from education_system.systems.apprenticeships.interfaces.gui.gui_main import *  # noqa: F401,F403
from education_system.systems.apprenticeships.interfaces.gui.gui_main import run  # noqa: F401
