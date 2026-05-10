"""Chat room mixin for CommunicationDashboard.

Composed from per-responsibility mixins. Public surface preserved:
    from ...email.admin.chat import _ChatMixin
"""
from __future__ import annotations

from .rooms import RoomsMixin
from .invitations import InvitationsMixin
from .messages import MessagesMixin
from .reactions_pins import ReactionsPinsMixin
from .presence import PresenceMixin
from .moderation import ModerationMixin
from .safeguarding import SafeguardingMixin
from .polls import PollsMixin
from .notes import NotesMixin
from .blocking import BlockingMixin
from .sync import SyncMixin
from .audit_gdpr import AuditGdprMixin
from .overview import OverviewMixin
from .users_internal import UsersInternalMixin

# Re-export module-level helpers for any external import that
# previously reached into chat.py for them.
from ._helpers import (
    _scan_filter_words,
    _ensure_room_key,
    _encrypt_with_key,
    _decrypt_with_key,
    _maybe_decrypt,
    _format_message_row,
)

class _ChatMixin(
    RoomsMixin,
    InvitationsMixin,
    MessagesMixin,
    ReactionsPinsMixin,
    PresenceMixin,
    ModerationMixin,
    SafeguardingMixin,
    PollsMixin,
    NotesMixin,
    BlockingMixin,
    SyncMixin,
    AuditGdprMixin,
    OverviewMixin,
    UsersInternalMixin,
):
    """Mixin providing chat room lifecycle, membership, and messaging."""
    pass


__all__ = [
    "_ChatMixin",
    "_scan_filter_words",
    "_ensure_room_key",
    "_encrypt_with_key",
    "_decrypt_with_key",
    "_maybe_decrypt",
    "_format_message_row",
]
