"""Mail/Post System Core Services Module"""

from education_system.university_system.modules.domain.mail.services.mail_post_core import (
    PackageManager,
    POBoxManager,
    ForwardingManager,
    TransactionManager,
    ReportManager,
    init_mail_db,
    generate_tracking_number,
    PACKAGE_TYPES,
    PACKAGE_STATUSES,
    STORAGE_FEES,
    FORWARDING_FEES
)

__all__ = [
    'PackageManager',
    'POBoxManager',
    'ForwardingManager',
    'TransactionManager',
    'ReportManager',
    'init_mail_db',
    'generate_tracking_number',
    'PACKAGE_TYPES',
    'PACKAGE_STATUSES',
    'STORAGE_FEES',
    'FORWARDING_FEES'
]
