"""
Document Manager GUI Package

Refactored from a single 18,953-line module into a package of manager classes
using the composition/delegation pattern.

Recommended imports (direct submodule paths):
    from education_system.post_18.university_system.modules.shared.gui.document_manager_gui.main_gui import DocumentManagerGUI
    from education_system.post_18.university_system.modules.shared.gui.document_manager_gui.console import start_document_manager_gui
    from education_system.post_18.university_system.modules.shared.gui.document_manager_gui.console import display_document_management_menu

Backward-compatible imports (re-exported here):
    from education_system.post_18.university_system.modules.shared.gui.document_manager_gui import DocumentManagerGUI
    from education_system.post_18.university_system.modules.shared.gui.document_manager_gui import start_document_manager_gui
    from education_system.post_18.university_system.modules.shared.gui.document_manager_gui import display_document_management_menu
"""

from education_system.post_18.university_system.modules.shared.gui.document_manager_gui.main_gui import (
    DocumentManagerGUI,
)
from education_system.post_18.university_system.modules.shared.gui.document_manager_gui.console import (
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
