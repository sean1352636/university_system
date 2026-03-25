# Auto‑generated init file for the email GUI package

from education_system.university_system.modules.shared.gui.email.email_gui.email_manager_main import EmailManagerGUI, main, run_gui_mode, display_communication_dashboard_gui, integrate_with_cli
from education_system.university_system.modules.shared.gui.email.email_gui.utils import ThemeManager, ConfigManager, SingletonApp, handle_gui_error

# Email dialogs
from education_system.university_system.modules.shared.gui.email.email_gui.email_dialogs import (
    ComposeEmailDialog,
    BulkEmailDialog,
    ScheduleEmailDialog,
    TemplateManagerDialog,
    TemplateEditDialog,
    TemplateEditor,
    EmailConfigDialog,
    EmailDetailsDialog,
    RecipientSelectorDialog,
)

# Chat dialogs
from education_system.university_system.modules.shared.gui.email.email_gui.chat_dialogs import (
    ComposeMessageDialog,
    ReplyMessageDialog,
    CreateAnnouncementDialog,
    AnnouncementDetailsDialog,
    EditAnnouncementDialog,
    CreateChatRoomDialog,
    ChatInvitationsDialog,
    ChatRoomWindow,
)

# Utility dialogs
from education_system.university_system.modules.shared.gui.email.email_gui.utility_dialogs import (
    SystemHealthDialog,
    DatabaseCleanupDialog,
    NotificationPreferencesDialog,
    ExportDataDialog,
    AdvancedSearchDialog,
    EmailReportsDialog,
    HelpDialog,
    AboutDialog,
    ProgressDialog,
    StatusNotification,
)

# Academic notification dialogs
from education_system.university_system.modules.shared.gui.email.email_gui.notification_dialogs_academic import (
    RegistrationConfirmationDialog,
    AssignmentNotificationDialog,
    ModuleGradeNotificationDialog,
    AssignmentGradeNotificationDialog,
    ExtensionNotificationDialog,
    UpdateConfirmationDialog,
    PasswordResetDialog,
    ScheduleChangeNotificationDialog,
)

# Library notification dialogs
from education_system.university_system.modules.shared.gui.email.email_gui.notification_dialogs_library import (
    BookCheckoutConfirmationDialog,
    BookReturnReminderDialog,
    OverdueNotificationDialog,
)

# Support notification dialogs
from education_system.university_system.modules.shared.gui.email.email_gui.notification_dialogs_support import (
    TicketNotificationDialog,
    ReplyNotificationDialog,
    SLAAlertDialog,
    SatisfactionSurveyDialog,
    BulkSatisfactionSurveysDialog,
)

# Other notification dialogs
from education_system.university_system.modules.shared.gui.email.email_gui.notification_dialogs_other import (
    AppointmentConfirmationDialog,
    HealthNotificationDialog,
    InternshipNotificationDialog,
    MentorshipNotificationDialog,
    AlumniWelcomeDialog,
    EventInvitationDialog,
    DonationReceiptDialog,
    ApplicationConfirmationDialog,
    PermitConfirmationDialog,
    PermitUpdateConfirmationDialog,
)

# Tab modules contain helper functions (create_*_tab) that are called by EmailManagerGUI
# They are not imported here as they don't define exportable classes

# misc.py contains no exportable utilities

__all__ = [
    'EmailManagerGUI',
    'main',
    'run_gui_mode',
    'display_communication_dashboard_gui',
    'integrate_with_cli',
    'ComposeEmailDialog',
    'BulkEmailDialog',
    'ScheduleEmailDialog',
    'TemplateManagerDialog',
    'TemplateEditDialog',
    'TemplateEditor',
    'EmailConfigDialog',
    'EmailDetailsDialog',
    'RecipientSelectorDialog',
    'ComposeMessageDialog',
    'ReplyMessageDialog',
    'CreateAnnouncementDialog',
    'AnnouncementDetailsDialog',
    'EditAnnouncementDialog',
    'CreateChatRoomDialog',
    'ChatInvitationsDialog',
    'ChatRoomWindow',
    'SystemHealthDialog',
    'DatabaseCleanupDialog',
    'NotificationPreferencesDialog',
    'ExportDataDialog',
    'AdvancedSearchDialog',
    'EmailReportsDialog',
    'HelpDialog',
    'AboutDialog',
    'ProgressDialog',
    'StatusNotification',
    'RegistrationConfirmationDialog',
    'AssignmentNotificationDialog',
    'ModuleGradeNotificationDialog',
    'AssignmentGradeNotificationDialog',
    'ExtensionNotificationDialog',
    'UpdateConfirmationDialog',
    'PasswordResetDialog',
    'ScheduleChangeNotificationDialog',
    'BookCheckoutConfirmationDialog',
    'BookReturnReminderDialog',
    'OverdueNotificationDialog',
    'TicketNotificationDialog',
    'ReplyNotificationDialog',
    'SLAAlertDialog',
    'SatisfactionSurveyDialog',
    'BulkSatisfactionSurveysDialog',
    'AppointmentConfirmationDialog',
    'HealthNotificationDialog',
    'InternshipNotificationDialog',
    'MentorshipNotificationDialog',
    'AlumniWelcomeDialog',
    'EventInvitationDialog',
    'DonationReceiptDialog',
    'ApplicationConfirmationDialog',
    'PermitConfirmationDialog',
    'PermitUpdateConfirmationDialog',
    'ThemeManager',
    'ConfigManager',
    'SingletonApp',
    'handle_gui_error',
]
