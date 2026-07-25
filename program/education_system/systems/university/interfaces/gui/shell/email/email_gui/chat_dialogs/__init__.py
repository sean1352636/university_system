"""Chat dialogs package — split from the former chat_dialogs.py module.

Public API is preserved: every class that used to be importable from
``...email_gui.chat_dialogs`` is re-exported here, so existing call sites
continue to work unchanged.
"""

from .announcements import (
    AnnouncementDetailsDialog,
    CreateAnnouncementDialog,
    EditAnnouncementDialog,
)
from .messages import ComposeMessageDialog, ReplyMessageDialog
from .rooms_create import (
    CreateChatRoomDialog,
    ChatInvitationsDialog,
    RoomSwitcherDialog,
)
from .chat_room_window import ChatRoomWindow
from .room_admin import EditRoomDialog, ManageMembersDialog
from .room_tools import (
    PollComposerDialog,
    QueueDialog,
    ReportsDialog,
    AuditLogDialog,
    BlocksDialog,
)
from .room_notes import RoomNotesDialog, NotesDiffDialog
from .misc_dialogs import GDPRChatDialog, UserProfileDialog

__all__ = [
    "AnnouncementDetailsDialog",
    "CreateAnnouncementDialog",
    "EditAnnouncementDialog",
    "ComposeMessageDialog",
    "ReplyMessageDialog",
    "CreateChatRoomDialog",
    "ChatInvitationsDialog",
    "RoomSwitcherDialog",
    "ChatRoomWindow",
    "EditRoomDialog",
    "ManageMembersDialog",
    "PollComposerDialog",
    "QueueDialog",
    "ReportsDialog",
    "AuditLogDialog",
    "BlocksDialog",
    "RoomNotesDialog",
    "NotesDiffDialog",
    "GDPRChatDialog",
    "UserProfileDialog",
]
