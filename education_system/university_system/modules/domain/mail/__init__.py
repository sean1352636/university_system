"""
Mail/Post System Module

Provides comprehensive mail and package handling services including
receiving, storing, tracking, PO boxes, and forwarding with
email and finance integration.
"""

from education_system.university_system.modules.domain.mail.gui.mail_post_gui import (
    MailPostGUI,
    launch_mail_post_gui
)
from education_system.university_system.modules.domain.mail.services.mail_post_core import (
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
