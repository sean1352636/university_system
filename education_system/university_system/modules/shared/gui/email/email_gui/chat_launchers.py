"""Reusable launchers for opening a chat room from anywhere in the GUI.

Each helper takes a Tk parent, an authenticated dashboard, and the entity-
specific identifiers; it ensures the linked chat_room exists, then opens
ChatRoomWindow on top of the parent. Designed to be dropped into domain GUIs
(events, clubs, housing, career, ...) so they can offer an "Open chat" action
without each module reimplementing the wiring.

Usage:

    from education_system.university_system.modules.shared.gui.email.email_gui.chat_launchers import (
        open_chat_for_event,
    )
    open_chat_for_event(parent, dashboard, event_id=42, event_title="Welcome week")
"""

from __future__ import annotations

import logging
from tkinter import messagebox

from education_system.university_system.modules.shared.gui.email.email_gui.chat_dialogs import (
    ChatRoomWindow,
)

logger = logging.getLogger(__name__)


def _open_room(parent, dashboard, room_id, room_name):
    if not room_id:
        messagebox.showerror("Error", "Could not open chat room.", parent=parent)
        return None
    return ChatRoomWindow(parent, dashboard, room_id, room_name)


def open_chat_for_event(parent, dashboard, event_id, event_title):
    """Open (or create) the chat room linked to a calendar event."""
    try:
        rid = dashboard.get_or_create_event_room(event_id, event_title)
    except Exception as e:
        logger.exception("open_chat_for_event failed")
        messagebox.showerror("Error", str(e), parent=parent)
        return None
    return _open_room(parent, dashboard, rid, f"Event: {event_title}")


def open_chat_for_club(parent, dashboard, club_id, club_name, member_user_ids=None):
    """Open (or create) the chat room linked to a student club/society."""
    try:
        rid = dashboard.get_or_create_club_room(
            club_id, club_name, member_user_ids=member_user_ids,
        )
    except Exception as e:
        logger.exception("open_chat_for_club failed")
        messagebox.showerror("Error", str(e), parent=parent)
        return None
    return _open_room(parent, dashboard, rid, f"Club: {club_name}")


def open_chat_for_residence(parent, dashboard, residence_id, residence_name,
                            resident_user_ids=None):
    """Open (or create) the chat room linked to a residence/floor/hall."""
    try:
        rid = dashboard.get_or_create_residence_room(
            residence_id, residence_name, resident_user_ids=resident_user_ids,
        )
    except Exception as e:
        logger.exception("open_chat_for_residence failed")
        messagebox.showerror("Error", str(e), parent=parent)
        return None
    return _open_room(parent, dashboard, rid, f"Residence: {residence_name}")


def open_chat_for_advisor_oh(parent, dashboard, advisor_user_id, student_user_id,
                             starts_at=None, ends_at=None):
    """Open (or create) a 1:1 advisor office-hours room."""
    try:
        rid = dashboard.get_or_create_advisor_oh_room(
            advisor_user_id, student_user_id,
            starts_at=starts_at, ends_at=ends_at,
        )
    except Exception as e:
        logger.exception("open_chat_for_advisor_oh failed")
        messagebox.showerror("Error", str(e), parent=parent)
        return None
    return _open_room(parent, dashboard, rid, "Career advisor — office hours")
