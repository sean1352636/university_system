"""
Notification system for support tickets.
"""

import logging


from education_system.systems.university.domains.student_support.domain.student_support import auth as _auth_mod
from education_system.systems.university.domains.student_support.domain.student_support import notify, store

logger = logging.getLogger(__name__)

def get_user_notifications(user_id=None, unread_only=False):
    """Get notifications for a user, from the mailbox the Hub reads.

    Was a query against the retired ``notifications`` table, which is never
    written to — so this returned nothing for everyone, and the callers that
    depend on it (notably "Mark All Read") had nothing to act on.
    """
    if not user_id:
        user_id = _auth_mod.auth.current_user['id'] if _auth_mod.auth and _auth_mod.auth.current_user else None

    if not user_id:
        raise ValueError("User ID required")

    items = _get_recent_notifications(user_id, None, limit=50)
    if unread_only:
        items = [n for n in items if not n.get('is_read')]
    return items


def mark_notification_read(notification_id, user_id=None):
    """Mark one inbox message read, through the same mailbox API as the Hub.

    The standalone ``notifications`` table this used to update is retired and
    never written to, so every call reported success against zero rows and
    "Mark All Read" always said it had marked none.
    """
    try:
        from education_system.systems.university.infrastructure.email.admin import (
            CommunicationDashboard,
        )
        dashboard = CommunicationDashboard(auth=_auth_for_notifications(user_id))
        return bool(dashboard.read_message(notification_id))
    except Exception as e:
        logger.error(f"Error marking notification as read: {e}")
        return False


def _get_recent_notifications(user_id, cursor, limit=10):
    """Recent inbox items for the dashboard widget.

    Reads the user's mailbox through ``CommunicationDashboard`` — the same
    source the Notifications Hub and the header bell use — rather than the
    standalone ``notifications`` table, which the Hub redesign retired. That
    table still exists but is never written to, so this widget reported "No
    recent notifications" to every user while their mailbox held hundreds of
    messages.

    ``cursor`` is accepted for call-compatibility and no longer used.

    Returns dicts shaped as before: ``notification_id``, ``title``,
    ``message``, ``type``, ``created``, ``is_read``.
    """
    try:
        from education_system.systems.university.infrastructure.email.admin import (
            CommunicationDashboard,
        )
    except Exception:
        logger.warning("CommunicationDashboard unavailable; "
                       "dashboard notifications will be empty", exc_info=True)
        return []

    try:
        dashboard = CommunicationDashboard(auth=_auth_for_notifications(user_id))
        inbox = dashboard.get_inbox(page=1, limit=limit)
    except Exception:
        logger.warning("Could not read the inbox for user %s", user_id,
                       exc_info=True)
        return []

    if not isinstance(inbox, dict):
        return []

    items = []
    for m in (inbox.get("messages") or [])[:limit]:
        if not isinstance(m, dict):
            continue
        items.append({
            "notification_id": m.get("id") or m.get("message_id"),
            # The widget shows the subject; fall back to the sender so a
            # subject-less message is not rendered as a blank row.
            "title": (m.get("subject") or m.get("title")
                      or m.get("sender") or "Message"),
            # get_inbox returns `content` (the messages.message column) and
            # `sent_at`; the older key names guessed here were always empty,
            # which showed as a blank timestamp beside every row.
            "message": m.get("content") or m.get("body") or m.get("message") or "",
            "type": m.get("message_type") or "message",
            "created": (m.get("sent_at") or m.get("sent_datetime")
                        or m.get("created_at") or ""),
            "is_read": bool(m.get("is_read")),
        })
    return items


def _auth_for_notifications(user_id):
    """Auth for the mailbox of ``user_id`` — not of whoever is signed in.

    This used to return the live session whenever one existed, ignoring the
    id it was given. The two coincide when you are looking at your own
    dashboard, so it looked right, but any call naming another user read the
    signed-in user's mailbox instead and showed rows belonging to someone
    else. The requested id wins; the live session is only used when it is
    that same user (so its permissions and any extra state come along) or
    when no id was given.
    """
    live = None
    try:
        candidate = getattr(_auth_mod, "auth", None)
        if candidate is not None and getattr(candidate, "current_user", None):
            live = candidate
    except Exception:
        logger.debug("no live auth session for notifications", exc_info=True)

    if user_id is None:
        return live

    if live is not None:
        live_id = (live.current_user or {}).get("id")
        if str(live_id) == str(user_id):
            return live

    class _StandInAuth:
        """Carries just the identity the mailbox query needs."""

        def __init__(self, uid):
            self.current_user = {"id": uid}

        def check_permission(self, *_a, **_k):
            return True

    return _StandInAuth(user_id)


def _create_ticket_notifications(ticket_id, student_id, assigned_to, action):
    """In-app notices (``messages`` rows) for a ticket event, on their own
    connection. ``service`` sends these inside its own transactions; this is
    kept for callers outside it."""
    try:
        with store.writing() as conn:
            row = conn.execute("SELECT subject FROM support_tickets WHERE ticket_id = ?",
                               (ticket_id,)).fetchone()
            subject = row[0] if row else ''
            notices = []
            if action == 'created' and student_id:
                notices = notify.ticket_created(ticket_id, subject, student_id, assigned_to)
            elif assigned_to:
                notices = notify.assigned(ticket_id, subject, assigned_to)
            notify.deliver_in_app(conn, notices)
        notify.after_commit(notices)
    except Exception as e:
        logger.error(f"Error creating notifications: {e}")


def _trigger_satisfaction_survey(ticket_id, student_id):
    """Invite the requester to rate a resolved ticket (an in-app message)."""
    if not student_id:
        logger.warning(f"Cannot trigger satisfaction survey for ticket #{ticket_id}: student_id is None")
        return
    try:
        with store.writing() as conn:
            row = conn.execute("SELECT subject FROM support_tickets WHERE ticket_id = ?",
                               (ticket_id,)).fetchone()
            notices = notify.satisfaction_invite(ticket_id, row[0] if row else '', student_id)
            notify.deliver_in_app(conn, notices)
        notify.after_commit(notices)
    except Exception as e:
        logger.error(f"Error triggering satisfaction survey: {e}")


def view_notifications(support):
    """View user notifications"""
    try:
        print("\n🔔 NOTIFICATIONS")
        print("="*40)

        # Get notifications from dashboard data
        dashboard_data = support.get_dashboard_data(_auth_mod.auth.current_user['role'], _auth_mod.auth.current_user['id'])
        notifications = dashboard_data.get('notifications', [])

        if not notifications:
            print("📭 No notifications.")
            return

        print(f"📬 You have {len(notifications)} notifications:")

        for i, notif in enumerate(notifications, 1):
            status_icon = "📫" if notif['is_read'] else "📬"
            print(f"\n{i}. {status_icon} {notif['title']}")
            print(f"   📝 {notif['message']}")
            print(f"   📅 {notif['created']}")
            print(f"   🏷️ Type: {notif['type']}")

        # Mark as read option
        unread = [n for n in notifications if not n.get('is_read') and n.get('notification_id')]
        if unread:
            mark_read = input("\nMark all as read? (y/n): ").lower()
            if mark_read == 'y':
                user_id = _auth_mod.auth.current_user['id']
                marked = sum(1 for n in unread
                             if mark_notification_read(n['notification_id'], user_id))
                if marked == len(unread):
                    print(f"✅ Marked {marked} notification(s) as read.")
                else:
                    print(f"⚠️ Marked {marked} of {len(unread)} notification(s) as read.")

    except Exception as e:
        print(f"❌ Error viewing notifications: {e}")

    input("\nPress Enter to continue...")

# Additional helper functions for enhanced features