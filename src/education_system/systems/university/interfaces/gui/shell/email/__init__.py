"""
Email GUI components.

This module contains GUI components for email management that were moved from
infrastructure/email/gui/ to maintain proper architectural layering.
"""

# Import from the new modular email_gui package
from education_system.systems.university.interfaces.gui.shell.email.email_gui import EmailManagerGUI

# Create EmailGUI alias for backwards compatibility
EmailGUI = EmailManagerGUI

# Import other email GUI components
from education_system.systems.university.interfaces.gui.shell.email.email_manager_management_gui import EmailManagerManagementGUI
from education_system.systems.university.interfaces.gui.shell.email.email_queue_scheduler_gui import EmailQueueSchedulerGUI, main as email_scheduler_main

__all__ = [
    'EmailManagerGUI',
    'EmailGUI',
    'EmailManagerManagementGUI',
    'EmailQueueSchedulerGUI',
    'email_scheduler_main',
]
