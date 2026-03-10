"""
DEPRECATED: Email GUI components have been moved to modules/shared/gui/email/

This module provides backward compatibility for existing imports.
New code should import from education_system.university_system.modules.shared.gui.email instead.
"""

import warnings

warnings.warn(
    "Importing from education_system.university_system.infrastructure.email.gui is deprecated. "
    "Please import from education_system.university_system.modules.shared.gui.email instead.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export from new location for backward compatibility
from education_system.university_system.modules.shared.gui.email.email_gui import EmailManagerGUI
from education_system.university_system.modules.shared.gui.email.email_manager_management_gui import EmailManagerManagementGUI
from education_system.university_system.modules.shared.gui.email.email_queue_scheduler_gui import EmailQueueSchedulerGUI

# Create EmailGUI alias for backwards compatibility
EmailGUI = EmailManagerGUI

__all__ = [
    'EmailManagerGUI',
    'EmailGUI',
    'EmailManagerManagementGUI',
    'EmailQueueSchedulerGUI',
]
