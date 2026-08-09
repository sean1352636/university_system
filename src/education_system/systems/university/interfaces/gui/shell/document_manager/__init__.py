"""
Document Manager GUI Package

Refactored from a single 18,953-line module into a package of manager classes
using the composition/delegation pattern.

Recommended imports (direct submodule paths):
    from education_system.systems.university.interfaces.gui.shell.document_manager.main_gui import DocumentManagerGUI
    from education_system.systems.university.interfaces.gui.shell.document_manager.console import start_document_manager_gui
    from education_system.systems.university.interfaces.gui.shell.document_manager.console import display_document_management_menu

Backward-compatible imports (re-exported here):
    from education_system.systems.university.interfaces.gui.shell.document_manager import DocumentManagerGUI
    from education_system.systems.university.interfaces.gui.shell.document_manager import start_document_manager_gui
    from education_system.systems.university.interfaces.gui.shell.document_manager import display_document_management_menu
"""

from education_system.systems.university.interfaces.gui.shell.document_manager.main_gui import (
    DocumentManagerGUI,
)
from education_system.systems.university.interfaces.gui.shell.document_manager.console import (
    DocumentManager,
    main,
    display_document_management_menu,
    start_document_manager_gui,
    launch_gui_only,
    launch_console_only,
)

__all__ = [
    'DocumentManagerGUI',
    'DocumentManager',
    'main',
    'display_document_management_menu',
    'start_document_manager_gui',
    'launch_gui_only',
    'launch_console_only',
]
