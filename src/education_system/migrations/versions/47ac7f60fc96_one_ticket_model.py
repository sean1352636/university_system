"""support tickets: one ticket model for Student Support and the Helpdesk

1. **Schema.** ``student_support/schema.apply`` — the one support ticket
   DDL — adds the canonical columns to ``support_tickets``
   (requester_username, student_id, source, channel, team, confidentiality,
   crisis_flag, sla_due_at, first_response_at, resolved_at, share_consent,
   share_consent_at, data_purged_at), ``responder_username`` to
   ``ticket_responses``, creates ``support_escalation_fires`` and the
   indexes, and the two triggers that keep rows written by older code
   canonical (requester / source / status filled on insert, legacy status
   spellings mapped on update).
2. **Backfill.** For every ticket:
   * ``requester_username`` / ``student_id`` from ``user_id``, which holds a
     student number (Student Support) or a ``users.id`` (Helpdesk): matched
     as a username, then a student number, then a ``users.id``. A ticket
     whose user_id matches nobody keeps NULLs and is listed in the log;
   * ``source``: 'support' for a Student Support row (title-case status, or
     a web ticket whose user_id is a username / student number), else
     'helpdesk'; the old value ('web', 'grade_appeal', ...) moves to
     ``channel``;
   * ``status`` mapped to open / in_progress / waiting_on_student /
     escalated / resolved / closed ('On Hold' and 'Pending' become
     waiting_on_student, 'cancelled' closed). A value with no mapping is
     left as it is and logged;
   * ``first_response_at`` from the first staff reply when missing;
     ``resolved_at`` for resolved / closed tickets when missing.
   ``ticket_responses.responder_username`` is filled where ``responder_id``
   is a ``users.id`` whose role matches ``responder_role``.
3. **notifications.** Student Support recreated the ``notifications`` table
   that migration 6f8b0d2e4a7c removed by design. It is dropped again when
   it is that table (it has ``related_ticket_id``), empty and referenced by
   no foreign key; otherwise it is left and logged.

Idempotent: every step checks what exists first; a second run changes
nothing.

Revision ID: 47ac7f60fc96
Revises: c4146c91ede9
Create Date: 2026-10-19 12:00:00.000000
"""
import logging
import re
from typing import Sequence, Union

from alembic import op


revision: str = '47ac7f60fc96'
down_revision: Union[str, Sequence[str], None] = 'c4146c91ede9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

logger = logging.getLogger(__name__)

STAFF_ROLES = ('admin', 'staff', 'support_staff', 'support_agent', 'helpdesk_agent',
               'super_admin', 'superadmin')


def _x():
    return op.get_bind().exec_driver_sql


def _table(name) -> bool:
    return _x()("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
                (name,)).fetchone() is not None


def _cols(table) -> list:
    return [r[1] for r in _x()(f'PRAGMA table_info("{table}")').fetchall()]


def _schema():
    from education_system.systems.university.domains.student_support.domain.student_support import (
        schema,
    )
    return schema


# ── 2. backfill ─────────────────────────────────────────────────────────


def _resolve(user_id, has_students):
    """``(username, student_id, how)`` for a stored user_id."""
    execute = _x()
    text = str(user_id or '').strip()
    if not text:
        return None, None, None
    row = execute("SELECT username, student_id FROM users WHERE username = ?", (text,)).fetchone()
    if row:
        return row[0], row[1], 'username'
    row = execute("SELECT username, student_id FROM users WHERE student_id = ? ORDER BY id LIMIT 1",
                  (text,)).fetchone()
    if row:
        return row[0], row[1], 'student_number'
    if text.isdigit():
        row = execute("SELECT username, student_id FROM users WHERE id = ?", (int(text),)).fetchone()
        if row:
            return row[0], row[1], 'users_id'
    if has_students and execute("SELECT 1 FROM students WHERE student_id = ?", (text,)).fetchone():
        return None, text, 'student_number'
    return None, None, None


def _backfill_tickets():
    schema = _schema()
    execute = _x()
    if not _table('support_tickets'):
        return
    has_students = _table('students')
    has_users = _table('users')
    canonical = set(schema.STATUSES)
    unresolved, unmapped, changed = [], [], 0
    rows = execute("SELECT ticket_id, user_id, requester_username, student_id, source, channel, "
                   "status FROM support_tickets ORDER BY ticket_id").fetchall()
    for ticket_id, user_id, requester, student_id, source, channel, status in rows:
        updates = {}
        how = None
        if has_users and (requester is None or student_id is None):
            username, sid, how = _resolve(user_id, has_students)
            if requester is None and username:
                updates['requester_username'] = username
            if student_id is None and sid:
                updates['student_id'] = sid
            if requester is None and not username and not sid:
                unresolved.append(f"#{ticket_id} (user_id={user_id!r})")
        if source not in schema.SOURCES:
            title_case = bool(status) and bool(re.match(r'[A-Z]', str(status)))
            web = source in (None, '', 'web')
            updates['source'] = ('support' if title_case or (web and how in ('username', 'student_number'))
                                 else 'helpdesk')
            if source and channel is None:
                updates['channel'] = source
        if status is not None and status not in canonical:
            mapped = schema.normalize_status(status, default='')
            if mapped:
                updates['status'] = mapped
            else:
                unmapped.append(f"#{ticket_id} ({status!r})")
        if updates:
            names = ", ".join(f'"{k}" = ?' for k in updates)
            execute(f"UPDATE support_tickets SET {names} WHERE ticket_id = ?",  # nosec B608 - fixed keys
                    (*updates.values(), ticket_id))
            changed += 1

    # first_response_at: the first public staff reply in either thread.
    staff = ", ".join(f"'{r}'" for r in STAFF_ROLES)
    execute(f"""
        UPDATE support_tickets SET first_response_at = (
            SELECT MIN(r.response_datetime) FROM ticket_responses r
            WHERE r.ticket_id = support_tickets.ticket_id
              AND COALESCE(r.is_internal, 0) = 0 AND COALESCE(r.is_auto_generated, 0) = 0
              AND r.responder_role IN ({staff}))
        WHERE first_response_at IS NULL AND EXISTS (
            SELECT 1 FROM ticket_responses r
            WHERE r.ticket_id = support_tickets.ticket_id
              AND COALESCE(r.is_internal, 0) = 0 AND COALESCE(r.is_auto_generated, 0) = 0
              AND r.responder_role IN ({staff}))""")  # nosec B608 - fixed role list
    if _table('ticket_replies') and has_users:
        execute(f"""
            UPDATE support_tickets SET first_response_at = (
                SELECT MIN(tr.created_at) FROM ticket_replies tr JOIN users u ON u.id = tr.user_id
                WHERE tr.ticket_id = support_tickets.ticket_id AND COALESCE(tr.is_internal, 0) = 0
                  AND u.role IN ({staff}))
            WHERE first_response_at IS NULL AND EXISTS (
                SELECT 1 FROM ticket_replies tr JOIN users u ON u.id = tr.user_id
                WHERE tr.ticket_id = support_tickets.ticket_id AND COALESCE(tr.is_internal, 0) = 0
                  AND u.role IN ({staff}))""")  # nosec B608 - fixed role list
    execute("UPDATE support_tickets SET resolved_at = COALESCE(closed_at, updated_at, created_at) "
            "WHERE resolved_at IS NULL AND status IN ('resolved', 'closed')")

    if has_users and 'responder_username' in _cols('ticket_responses'):
        execute("""
            UPDATE ticket_responses SET responder_username = (
                SELECT u.username FROM users u
                WHERE CAST(u.id AS TEXT) = CAST(ticket_responses.responder_id AS TEXT)
                  AND u.role = ticket_responses.responder_role)
            WHERE responder_username IS NULL AND EXISTS (
                SELECT 1 FROM users u
                WHERE CAST(u.id AS TEXT) = CAST(ticket_responses.responder_id AS TEXT)
                  AND u.role = ticket_responses.responder_role)""")

    logger.info("support_tickets: %s of %s tickets brought onto the one ticket model",
                changed, len(rows))
    if unresolved:
        logger.warning("support_tickets: no requester found for %s ticket(s); left with "
                       "requester_username NULL: %s", len(unresolved), ", ".join(unresolved))
    if unmapped:
        logger.warning("support_tickets: status with no mapping left as stored: %s",
                       ", ".join(unmapped))


# ── 3. notifications ────────────────────────────────────────────────────


def _drop_recreated_notifications():
    if not _table('notifications'):
        return
    execute = _x()
    if 'related_ticket_id' not in _cols('notifications'):
        logger.info("notifications exists but is not the Student Support table; left alone")
        return
    count = execute('SELECT COUNT(*) FROM "notifications"').fetchone()[0]
    pattern = re.compile(r'REFERENCES\s+"?notifications"?\s*\(', re.IGNORECASE)
    referenced = [name for name, sql in execute(
        "SELECT name, sql FROM sqlite_master WHERE type = 'table' AND name <> 'notifications'"
    ).fetchall() if sql and pattern.search(sql)]
    if count or referenced:
        logger.warning("notifications (recreated by Student Support) kept: %s row(s), "
                       "referenced by %s", count, referenced or 'nothing')
        return
    execute('DROP TABLE "notifications"')
    logger.info("Dropped the empty notifications table Student Support had recreated")


def upgrade() -> None:
    schema = _schema()
    schema.apply(_x())
    _backfill_tickets()
    _drop_recreated_notifications()


def downgrade() -> None:
    # The triggers and the escalation-fires table go; the added columns and
    # the backfilled values stay (older code ignores them, and the status
    # values they replaced are still accepted by the screens' mapping).
    schema = _schema()
    execute = _x()
    execute(f"DROP TRIGGER IF EXISTS {schema.INSERT_TRIGGER}")
    execute(f"DROP TRIGGER IF EXISTS {schema.STATUS_TRIGGER}")
    if _table('support_escalation_fires') and not execute(
            "SELECT COUNT(*) FROM support_escalation_fires").fetchone()[0]:
        execute("DROP TABLE support_escalation_fires")
