"""Inter-system messaging service for teacher-to-teacher communication.

Messages are stored in the shared auth database and are associated with
specific students to facilitate handover conversations during transfers.

A message can also belong to a *transition* — one learner's move between
two institutions. That is the handover conversation proper: the sending
school's SENCo asking the receiving college whether the access
arrangements arrived, or the college telling the school a start date has
moved. Such a thread is addressed either to a named member of staff or to
the other institution as a whole (``recipient_scope='institution'``),
because at the start of a transfer the sender usually does not know who at
the other end will pick it up.
"""

import sqlite3
from datetime import datetime

from education_system.platform.identity.auth.db import AUTH_DB_FILE, connect as auth_connect

SCOPE_USER = "user"
SCOPE_INSTITUTION = "institution"

# Columns added after the table shipped; CREATE TABLE IF NOT EXISTS will not
# add them to an existing database.
_ADDED_COLUMNS = (
    ("transition_id", "TEXT"),
    ("recipient_scope", "TEXT NOT NULL DEFAULT 'user'"),
)
_POST_MIGRATION_SQL = """
CREATE INDEX IF NOT EXISTS idx_csm_transition
    ON cross_system_messages(transition_id, created_at)
    WHERE transition_id IS NOT NULL;
"""


class TransitionMessageError(ValueError):
    """A transition message that cannot be sent as addressed."""

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS cross_system_messages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    sender_id       INTEGER NOT NULL,
    sender_system   TEXT    NOT NULL,
    sender_name     TEXT,
    recipient_id    INTEGER NOT NULL,
    recipient_system TEXT   NOT NULL,
    recipient_name  TEXT,
    student_name    TEXT,
    student_id      TEXT,
    subject         TEXT    NOT NULL,
    body            TEXT,
    is_read         INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);
"""


class InterSystemMessagingService:
    """Send and receive messages between staff across education systems."""

    def __init__(self, db_path=None, transitions_db_path=None):
        self._db_path = db_path or str(AUTH_DB_FILE)
        # Transitions live in the auth DB. When this service is pointed at
        # its own file (tests, or a split deployment) the caller says where
        # transitions are; by default they are wherever the messages are.
        self._transitions_db_path = transitions_db_path or db_path
        self._ensure_table()

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _conn(self):
        return auth_connect(self._db_path)

    def _ensure_table(self):
        """Create the cross_system_messages table if it does not exist."""
        conn = self._conn()
        try:
            conn.executescript(_CREATE_TABLE_SQL)
            held = {r["name"] for r in conn.execute(
                "PRAGMA table_info(cross_system_messages)").fetchall()}
            for name, decl in _ADDED_COLUMNS:
                if name not in held:
                    conn.execute(
                        f"ALTER TABLE cross_system_messages ADD COLUMN {name} {decl}")  # nosec B608
            conn.executescript(_POST_MIGRATION_SQL)
            conn.commit()
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------

    def send_message(self, sender_id, sender_system, sender_name,
                     recipient_id, recipient_system, recipient_name,
                     student_name, student_id, subject, body,
                     transition_id=None, recipient_scope=SCOPE_USER):
        """Send a message from one staff member to another.

        ``transition_id`` files the message under a learner's transfer (see
        :meth:`send_transition_message`, which also checks the addressing).

        Returns the newly created message dict.
        """
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO cross_system_messages
                   (sender_id, sender_system, sender_name,
                    recipient_id, recipient_system, recipient_name,
                    student_name, student_id, subject, body,
                    transition_id, recipient_scope)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (sender_id, sender_system, sender_name or "",
                 recipient_id, recipient_system, recipient_name or "",
                 student_name or "", student_id or "",
                 subject, body or "", transition_id,
                 recipient_scope or SCOPE_USER),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM cross_system_messages WHERE id = last_insert_rowid()"
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_inbox(self, user_id, system=None):
        """Get messages received by *user_id*, newest first.

        If *system* is given, filters to messages sent TO that system.
        """
        conn = self._conn()
        try:
            if system:
                rows = conn.execute(
                    "SELECT * FROM cross_system_messages "
                    "WHERE recipient_id = ? AND recipient_system = ? "
                    "ORDER BY created_at DESC",
                    (user_id, system),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM cross_system_messages "
                    "WHERE recipient_id = ? ORDER BY created_at DESC",
                    (user_id,),
                ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_sent(self, user_id, system=None):
        """Get messages sent by *user_id*, newest first."""
        conn = self._conn()
        try:
            if system:
                rows = conn.execute(
                    "SELECT * FROM cross_system_messages "
                    "WHERE sender_id = ? AND sender_system = ? "
                    "ORDER BY created_at DESC",
                    (user_id, system),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM cross_system_messages "
                    "WHERE sender_id = ? ORDER BY created_at DESC",
                    (user_id,),
                ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_message(self, msg_id):
        """Get a single message by ID."""
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM cross_system_messages WHERE id = ?", (msg_id,)
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def mark_read(self, msg_id):
        """Mark a message as read."""
        conn = self._conn()
        try:
            conn.execute(
                "UPDATE cross_system_messages SET is_read = 1 WHERE id = ?",
                (msg_id,),
            )
            conn.commit()
        finally:
            conn.close()

    def get_staff_list(self, system):
        """Get staff/admin/teacher users in a given system.

        Returns a list of dicts with keys: id, display_name, username, role.
        """
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT u.id, u.display_name, u.username, us.role "
                "FROM users u "
                "JOIN user_systems us ON u.id = us.user_id "
                "WHERE us.system_key = ? AND us.role IN ('admin', 'staff', 'teacher', 'instructor') "
                "AND u.is_active = 1 "
                "ORDER BY u.display_name",
                (system,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def search_messages(self, user_id, system, query):
        """Search messages (inbox and sent) by subject, body, or student name.

        Returns messages where the user is sender or recipient matching query.
        """
        conn = self._conn()
        try:
            like = f"%{query.strip()}%"
            rows = conn.execute(
                "SELECT * FROM cross_system_messages "
                "WHERE (recipient_id = ? OR sender_id = ?) "
                "AND (subject LIKE ? OR body LIKE ? OR student_name LIKE ?) "
                "ORDER BY created_at DESC",
                (user_id, user_id, like, like, like),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # transition (handover) threads
    # ------------------------------------------------------------------

    def _transition(self, transition_id):
        from education_system.platform.cross_system import transitions
        row = transitions.get_transition(
            transition_id, db_path=self._transitions_db_path)
        if row is None:
            raise TransitionMessageError(f"No transition {transition_id}")
        return row

    def send_transition_message(self, transition_id, *, sender_id,
                                sender_system, subject, body,
                                sender_name=None, recipient_id=None,
                                recipient_name=None, recipient_system=None,
                                allow_other_systems=False):
        """Post to a transition's thread. Returns the message dict.

        The sender must be at one end of the transition — the source or the
        destination — unless ``allow_other_systems`` (a superadmin acting
        for either side). The recipient system defaults to the *other* end.
        With no ``recipient_id`` the message goes to that institution as a
        whole and appears in :meth:`get_institution_inbox`.

        The learner is identified by journey id only. The thread is a
        conversation between institutions; it is not the place to copy the
        learner's name or handover details into free text.
        """
        transition = self._transition(transition_id)
        ends = {transition.get("source_system"), transition["destination_system"]}
        ends.discard(None)
        if sender_system not in ends and not allow_other_systems:
            raise TransitionMessageError(
                f"{sender_system!r} is not a party to transition "
                f"{transition_id} ({' -> '.join(sorted(ends))})")
        if recipient_system is None:
            others = ends - {sender_system}
            if not others:
                raise TransitionMessageError(
                    "Name the recipient system: this transition has only one "
                    "platform system at its ends")
            recipient_system = sorted(others)[0]
        elif recipient_system not in ends and not allow_other_systems:
            raise TransitionMessageError(
                f"{recipient_system!r} is not a party to transition {transition_id}")
        scope = SCOPE_USER if recipient_id else SCOPE_INSTITUTION
        return self.send_message(
            sender_id, sender_system, sender_name,
            int(recipient_id) if recipient_id else 0, recipient_system,
            recipient_name or ("" if recipient_id else recipient_system),
            "", transition["journey_id"], subject, body,
            transition_id=transition_id, recipient_scope=scope)

    def list_by_transition(self, transition_id):
        """Every message in one transition's thread, oldest first."""
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT * FROM cross_system_messages WHERE transition_id = ? "
                "ORDER BY created_at, id", (transition_id,)).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_institution_inbox(self, system, *, unread_only=False):
        """Transition messages addressed to *system* as an institution."""
        conn = self._conn()
        try:
            sql = ("SELECT * FROM cross_system_messages WHERE recipient_scope = ? "
                   "AND recipient_system = ?")
            if unread_only:
                sql += " AND is_read = 0"
            rows = conn.execute(sql + " ORDER BY created_at DESC",
                                (SCOPE_INSTITUTION, system)).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def transition_threads(self, system=None):
        """One summary row per transition with messages, newest activity first."""
        conn = self._conn()
        try:
            sql = ("SELECT transition_id, COUNT(*) AS messages, "
                   "SUM(CASE WHEN is_read = 0 THEN 1 ELSE 0 END) AS unread, "
                   "MAX(created_at) AS last_message_at "
                   "FROM cross_system_messages WHERE transition_id IS NOT NULL")
            params = []
            if system:
                sql += " AND (sender_system = ? OR recipient_system = ?)"
                params = [system, system]
            rows = conn.execute(
                sql + " GROUP BY transition_id ORDER BY last_message_at DESC",
                params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_unread_count(self, user_id, system=None):
        """Get the count of unread messages for a user."""
        conn = self._conn()
        try:
            if system:
                row = conn.execute(
                    "SELECT COUNT(*) as cnt FROM cross_system_messages "
                    "WHERE recipient_id = ? AND recipient_system = ? AND is_read = 0",
                    (user_id, system),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT COUNT(*) as cnt FROM cross_system_messages "
                    "WHERE recipient_id = ? AND is_read = 0",
                    (user_id,),
                ).fetchone()
            return row["cnt"]
        finally:
            conn.close()
