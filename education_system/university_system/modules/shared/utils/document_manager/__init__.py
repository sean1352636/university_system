"""
Document Manager Package

Split from a single large module into feature-specific mixins
for maintainability.  All public API is re-exported here so that
existing imports continue to work:

    from education_system.university_system.modules.shared.utils.document_manager import DocumentManager
    from education_system.university_system.modules.shared.utils.document_manager import display_document_management_menu
"""

from education_system.university_system.modules.shared.utils.document_manager.manager import DocumentManager, display_document_management_menu, main

__all__ = [
    "DocumentManager",
    "display_document_management_menu",
    "main",
]
