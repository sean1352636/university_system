"""
Mail/Post System Module

Provides comprehensive mail and package handling services including
receiving, storing, tracking, PO boxes, and forwarding with
email and finance integration.
"""

from education_system.systems.university.domain.operations.communications.mail.services.mail_post_core import (
    PackageManager,
    POBoxManager,
    ForwardingManager,
    TransactionManager,
    ReportManager,
    init_mail_db,
    PACKAGE_TYPES,
    STORAGE_FEES
)

__all__ = [
    'MailPostGUI',
    'launch_mail_post_gui',
    'PackageManager',
    'POBoxManager',
    'ForwardingManager',
    'TransactionManager',
    'ReportManager',
    'init_mail_db',
    'PACKAGE_TYPES',
    'STORAGE_FEES'
]

# The GUI classes live in the interfaces layer, which imports back into this
# domain package, so an eager re-export here is a circular import. PEP 562
# lazy lookup keeps these names on the package's public surface without the
# cycle: the interfaces module is only imported on first attribute access.
_LAZY_GUI_EXPORTS = {
    "MailPostGUI": "education_system.systems.university.interfaces.gui.operations.communications.mail.mail_post_gui",
    "launch_mail_post_gui": "education_system.systems.university.interfaces.gui.operations.communications.mail.mail_post_gui",
}


def __getattr__(name: str):
    module_path = _LAZY_GUI_EXPORTS.get(name)
    if module_path is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    import importlib
    value = getattr(importlib.import_module(module_path), name)
    globals()[name] = value  # cache so subsequent access skips __getattr__
    return value
