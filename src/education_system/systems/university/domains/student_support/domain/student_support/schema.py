"""The one definition of the support ticket tables.

``support_tickets`` is shared by Student Support and the Helpdesk; this module
owns its DDL and that of its child tables (``ticket_responses``,
``ticket_attachments``, ``ticket_links``, ``ticket_time_tracking``,
``support_ticket_followers``), of ``support_escalation_fires``, of the
referral and erasure-request tables (``support_ticket_referrals``,
``support_erasure_requests``), of major incidents (``support_incidents``)
and of the inbound e-mail log (``support_inbound_mail``). Every other place
that used to carry its own ``CREATE TABLE support_tickets`` (Helpdesk
``database.py``, the admin support schema, the CLI database manager, the
Helpdesk GUI fallbacks) calls :func:`apply` instead, and the wave-1 support
migration runs it too.

The ticket model
----------------
* ``requester_username`` — who raised the ticket (identity is the username;
  ``user_id`` is kept for the screens that still read it and holds a student
  number for Student Support tickets and a ``users.id`` for Helpdesk ones).
* ``student_id`` — the requester's student number (NULL for staff).
* ``source`` — ``'support'`` or ``'helpdesk'``: which service owns it. The
  channel it arrived by (web, e-mail, grade appeal ...) is ``channel``.
* ``status`` — one lower-case vocabulary for both front-ends,
  :data:`STATUSES`. Display labels are :data:`STATUS_LABELS`.
* ``team``, ``confidentiality``, ``crisis_flag``, ``sla_due_at``,
  ``first_response_at``, ``resolved_at``, ``share_consent(_at)``,
  ``data_purged_at`` — carried for the routing, tiering and SLA work.
* ``sla_paused_at`` / ``sla_paused_hours`` — the resolution clock stops while
  the ticket waits on the student (``sla``).
* ``incident_id`` — the major incident the ticket is part of (``incidents``).

Two triggers keep rows written by code that predates the model canonical: on
insert they fill ``requester_username`` / ``student_id`` / ``source`` /
``channel`` from ``user_id`` and map a legacy status ('Open', 'In Progress',
'waiting for customer' ...) to the vocabulary; on a status update they map a
legacy value the same way.
"""

from __future__ import annotations

import logging
import re
from typing import Callable, Iterable

logger = logging.getLogger(__name__)

# ── status vocabulary ────────────────────────────────────────────────────

STATUSES = ('open', 'in_progress', 'waiting_on_student', 'escalated', 'resolved', 'closed')
ACTIVE_STATUSES = ('open', 'in_progress', 'waiting_on_student', 'escalated')
DONE_STATUSES = ('resolved', 'closed')
STATUS_LABELS = {
    'open': 'Open',
    'in_progress': 'In Progress',
    'waiting_on_student': 'Waiting on Student',
    'escalated': 'Escalated',
    'resolved': 'Resolved',
    'closed': 'Closed',
}

# Every spelling either front-end (or an import) has written, keyed by the
# folded form (lower case, '_' / '-' as spaces, single spaces).
LEGACY_STATUS = {
    'open': 'open', 'new': 'open', 'reopened': 'open', 'submitted': 'open',
    'in progress': 'in_progress', 'inprogress': 'in_progress', 'assigned': 'in_progress',
    'active': 'in_progress', 'working': 'in_progress',
    'waiting on student': 'waiting_on_student', 'waiting for customer': 'waiting_on_student',
    'waiting for student': 'waiting_on_student', 'waiting': 'waiting_on_student',
    'pending': 'waiting_on_student', 'on hold': 'waiting_on_student',
    'awaiting response': 'waiting_on_student', 'awaiting student': 'waiting_on_student',
    'escalated': 'escalated',
    'resolved': 'resolved', 'completed': 'resolved', 'done': 'resolved', 'fixed': 'resolved',
    'closed': 'closed', 'cancelled': 'closed', 'canceled': 'closed', 'merged': 'closed',
}

SOURCES = ('support', 'helpdesk')
CONFIDENTIALITY = ('standard', 'restricted', 'safeguarding')


def _fold(value) -> str:
    return re.sub(r'\s+', ' ', str(value).strip().lower().replace('_', ' ').replace('-', ' '))


def normalize_status(value, default=None) -> str:
    """The canonical status for ``value`` ('In Progress' -> 'in_progress').

    Raises ValueError for a value with no mapping unless ``default`` is given.
    """
    if value is None or str(value).strip() == '':
        if default is not None:
            return default
        raise ValueError("A status is required")
    mapped = LEGACY_STATUS.get(_fold(value))
    if mapped:
        return mapped
    if default is not None:
        return default
    raise ValueError(
        f"Unknown status '{value}'. Choose from: {', '.join(STATUS_LABELS.values())}")


def status_label(value) -> str:
    """Display label for a stored status (unknown values are shown as stored)."""
    try:
        return STATUS_LABELS[normalize_status(value)]
    except ValueError:
        return str(value or '')


def status_case_sql(expr: str) -> str:
    """A SQL ``CASE`` mapping ``expr`` (a status) to the vocabulary.

    Built from :data:`LEGACY_STATUS` only (no caller input). Values with no
    mapping come back unchanged.
    """
    folded = (f"lower(trim(replace(replace({expr}, '_', ' '), '-', ' ')))")
    whens = " ".join(f"WHEN '{k}' THEN '{v}'" for k, v in LEGACY_STATUS.items())
    return f"(CASE {folded} {whens} ELSE {expr} END)"


def _in_list(values: Iterable[str]) -> str:
    return ", ".join(f"'{v}'" for v in values)


# ── DDL ──────────────────────────────────────────────────────────────────

SUPPORT_TICKETS_SQL = f'''
CREATE TABLE IF NOT EXISTS support_tickets (
    ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT,
    requester_username TEXT,
    student_id TEXT,
    assigned_to TEXT,
    subject TEXT NOT NULL,
    description TEXT NOT NULL,
    category TEXT NOT NULL,
    subcategory TEXT,
    status TEXT DEFAULT 'open',
    priority TEXT DEFAULT 'medium',
    impact TEXT DEFAULT 'low',
    urgency TEXT DEFAULT 'low',
    source TEXT DEFAULT 'support',
    channel TEXT,
    team TEXT,
    confidentiality TEXT DEFAULT 'standard'
        CHECK (confidentiality IN ({_in_list(CONFIDENTIALITY)})),
    crisis_flag INTEGER DEFAULT 0,
    resolution TEXT,
    satisfaction_rating INTEGER,
    satisfaction_feedback TEXT,
    estimated_hours REAL,
    actual_hours REAL,
    due_date TEXT,
    sla_due_at TEXT,
    resolved_at TEXT,
    first_response_at TEXT,
    last_activity_at TEXT,
    escalation_level INTEGER DEFAULT 0,
    tags TEXT,
    department TEXT,
    organization_id INTEGER,
    parent_ticket_id INTEGER,
    knowledge_base_articles TEXT,
    created_at TEXT,
    updated_at TEXT,
    escalated_at TEXT,
    closed_at TEXT,
    estimated_resolution TEXT,
    sentiment TEXT DEFAULT 'neutral',
    share_consent TEXT CHECK (share_consent IS NULL OR share_consent IN ('granted', 'declined')),
    share_consent_at TEXT,
    data_purged_at TEXT,
    sla_paused_at TEXT,
    sla_paused_hours REAL DEFAULT 0,
    incident_id INTEGER,
    FOREIGN KEY (parent_ticket_id) REFERENCES support_tickets (ticket_id)
)
'''

TICKET_RESPONSES_SQL = '''
CREATE TABLE IF NOT EXISTS ticket_responses (
    response_id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id INTEGER NOT NULL,
    responder_id TEXT NOT NULL,
    responder_username TEXT,
    responder_role TEXT NOT NULL,
    response_text TEXT NOT NULL,
    response_datetime TEXT NOT NULL,
    is_internal BOOLEAN DEFAULT 0,
    is_auto_generated BOOLEAN DEFAULT 0,
    template_used TEXT,
    FOREIGN KEY (ticket_id) REFERENCES support_tickets (ticket_id)
)
'''

TICKET_ATTACHMENTS_SQL = '''
CREATE TABLE IF NOT EXISTS ticket_attachments (
    attachment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id INTEGER NOT NULL,
    reply_id INTEGER,
    filename TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_size INTEGER,
    file_type TEXT,
    mime_type TEXT,
    file_hash TEXT,
    uploaded_by TEXT,
    is_public BOOLEAN DEFAULT 0,
    created_at TEXT,
    FOREIGN KEY (ticket_id) REFERENCES support_tickets (ticket_id)
)
'''

# One row per (ticket, escalation rule) once the rule has acted on the
# ticket, so a 'notify' rule tells people once instead of every pass.
ESCALATION_FIRES_SQL = '''
CREATE TABLE IF NOT EXISTS support_escalation_fires (
    fire_id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id INTEGER NOT NULL,
    rule_id INTEGER NOT NULL,
    action_type TEXT NOT NULL,
    fired_at TEXT NOT NULL,
    UNIQUE (ticket_id, rule_id),
    FOREIGN KEY (ticket_id) REFERENCES support_tickets (ticket_id) ON DELETE CASCADE
)
'''

# Where a ticket was referred (Early Warning, mitigating circumstances,
# hardship, accessibility) or reported (a safeguarding concern), and the
# record it created there. A row is written as 'pending' before the other
# service is called and completed with its reference after, so a referral
# is never made without a trace on the ticket.
REFERRALS_SQL = '''
CREATE TABLE IF NOT EXISTS support_ticket_referrals (
    referral_id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id INTEGER NOT NULL,
    kind TEXT NOT NULL,
    target_ref TEXT,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'created', 'failed')),
    consent_basis TEXT,
    error TEXT,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    completed_at TEXT,
    FOREIGN KEY (ticket_id) REFERENCES support_tickets (ticket_id) ON DELETE CASCADE
)
'''

# Erasing one person's support records under dual control: requested by one
# administrator, decided by another who has just re-entered their password,
# then carried out (``gdpr``).
ERASURE_REQUESTS_SQL = '''
CREATE TABLE IF NOT EXISTS support_erasure_requests (
    request_id INTEGER PRIMARY KEY AUTOINCREMENT,
    requester_username TEXT,
    student_id TEXT,
    case_reference TEXT NOT NULL,
    reason TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'requested'
        CHECK (status IN ('requested', 'approved', 'rejected', 'completed')),
    tickets_json TEXT,
    requested_by TEXT NOT NULL,
    requested_at TEXT NOT NULL,
    decided_by TEXT,
    decided_at TEXT,
    decision_note TEXT,
    completed_by TEXT,
    completed_at TEXT,
    result_json TEXT
)
'''

# Links between tickets (related, duplicate, blocks, parent/child). The
# Helpdesk created this table first; the shape is unchanged. A link is stored
# both ways (``collaboration.LINK_TYPES`` names the reverse of each type).
TICKET_LINKS_SQL = '''
CREATE TABLE IF NOT EXISTS ticket_links (
    link_id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id INTEGER,
    linked_ticket_id INTEGER,
    link_type TEXT,
    created_by INTEGER,
    created_at TEXT,
    FOREIGN KEY (ticket_id) REFERENCES support_tickets (ticket_id),
    FOREIGN KEY (linked_ticket_id) REFERENCES support_tickets (ticket_id),
    FOREIGN KEY (created_by) REFERENCES users (id)
)
'''

# Time spent on a ticket (the Helpdesk's table; ``username`` added so staff
# without a local ``users`` row are still recorded).
TICKET_TIME_SQL = '''
CREATE TABLE IF NOT EXISTS ticket_time_tracking (
    time_id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id INTEGER,
    user_id INTEGER,
    start_time TEXT,
    end_time TEXT,
    duration_minutes INTEGER,
    description TEXT,
    billable BOOLEAN DEFAULT 0,
    created_at TEXT,
    username TEXT,
    FOREIGN KEY (ticket_id) REFERENCES support_tickets (ticket_id),
    FOREIGN KEY (user_id) REFERENCES users (id)
)
'''

# Staff following a ticket: told about its replies and changes. Following
# never widens access — a follower must be able to see the ticket.
FOLLOWERS_SQL = '''
CREATE TABLE IF NOT EXISTS support_ticket_followers (
    ticket_id INTEGER NOT NULL,
    username TEXT NOT NULL,
    added_by TEXT NOT NULL,
    added_at TEXT NOT NULL,
    PRIMARY KEY (ticket_id, username),
    FOREIGN KEY (ticket_id) REFERENCES support_tickets (ticket_id) ON DELETE CASCADE
)
'''

# A major incident (an outage, a known problem): one record that many
# tickets hang off (``support_tickets.incident_id``), updated and resolved
# together (``incidents``). ``public_message`` is what affected people see.
INCIDENTS_SQL = '''
CREATE TABLE IF NOT EXISTS support_incidents (
    incident_id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT,
    public_message TEXT,
    team TEXT,
    severity TEXT NOT NULL DEFAULT 'major'
        CHECK (severity IN ('minor', 'major', 'critical')),
    status TEXT NOT NULL DEFAULT 'open'
        CHECK (status IN ('open', 'monitoring', 'resolved')),
    resolution TEXT,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    resolved_by TEXT,
    resolved_at TEXT
)
'''

# Every e-mail the support mailbox received (``email_in``): what became of
# it, so a message is never processed twice and staff can review the ones
# that could not be matched to a person (``status`` 'quarantined').
INBOUND_MAIL_SQL = '''
CREATE TABLE IF NOT EXISTS support_inbound_mail (
    mail_id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_key TEXT NOT NULL UNIQUE,
    from_address TEXT,
    subject TEXT,
    received_at TEXT NOT NULL,
    status TEXT NOT NULL
        CHECK (status IN ('processed', 'quarantined', 'ignored', 'failed', 'accepted', 'discarded')),
    reason TEXT,
    ticket_id INTEGER,
    response_id INTEGER,
    username TEXT,
    raw_path TEXT,
    reviewed_by TEXT,
    reviewed_at TEXT
)
'''

COLLABORATION_INDEXES_SQL = (
    "CREATE INDEX IF NOT EXISTS idx_ticket_links_ticket ON ticket_links (ticket_id)",
    "CREATE INDEX IF NOT EXISTS idx_ticket_time_ticket ON ticket_time_tracking (ticket_id)",
    "CREATE INDEX IF NOT EXISTS idx_support_followers_user ON support_ticket_followers (username)",
    "CREATE INDEX IF NOT EXISTS idx_support_tickets_incident ON support_tickets (incident_id)",
    "CREATE INDEX IF NOT EXISTS idx_support_inbound_status ON support_inbound_mail (status)",
)

CARE_INDEXES_SQL = (
    "CREATE INDEX IF NOT EXISTS idx_support_referrals_ticket ON support_ticket_referrals (ticket_id)",
)

# Columns an existing table may lack (added in this order, all nullable).
ADDED_COLUMNS = {
    'support_tickets': (
        ('user_id', 'TEXT'),
        ('assigned_to', 'TEXT'),
        ('status', "TEXT DEFAULT 'open'"),
        ('priority', "TEXT DEFAULT 'medium'"),
        ('subject', 'TEXT'),
        ('description', "TEXT NOT NULL DEFAULT ''"),
        ('requester_username', 'TEXT'),
        ('student_id', 'TEXT'),
        ('source', "TEXT DEFAULT 'support'"),
        ('channel', 'TEXT'),
        ('team', 'TEXT'),
        ('confidentiality', "TEXT DEFAULT 'standard' CHECK (confidentiality IN "
                            f"({_in_list(CONFIDENTIALITY)}))"),
        ('crisis_flag', 'INTEGER DEFAULT 0'),
        ('sla_due_at', 'TEXT'),
        ('first_response_at', 'TEXT'),
        ('resolved_at', 'TEXT'),
        ('share_consent', "TEXT CHECK (share_consent IS NULL OR share_consent IN "
                          "('granted', 'declined'))"),
        ('share_consent_at', 'TEXT'),
        ('data_purged_at', 'TEXT'),
        ('created_at', 'TEXT'),
        ('updated_at', 'TEXT'),
        ('escalated_at', 'TEXT'),
        ('closed_at', 'TEXT'),
        ('estimated_resolution', 'TEXT'),
        ('sentiment', "TEXT DEFAULT 'neutral'"),
        ('satisfaction_rating', 'INTEGER'),
        ('satisfaction_feedback', 'TEXT'),
        ('tags', 'TEXT'),
        ('parent_ticket_id', 'INTEGER'),
        ('last_activity_at', 'TEXT'),
        ('sla_paused_at', 'TEXT'),
        ('sla_paused_hours', 'REAL DEFAULT 0'),
        ('incident_id', 'INTEGER'),
    ),
    'ticket_responses': (
        ('responder_username', 'TEXT'),
        ('is_internal', 'BOOLEAN DEFAULT 0'),
        ('is_auto_generated', 'BOOLEAN DEFAULT 0'),
        ('template_used', 'TEXT'),
    ),
    'ticket_attachments': (
        ('reply_id', 'INTEGER'),
        ('is_public', 'BOOLEAN DEFAULT 0'),
        ('uploaded_by', 'TEXT'),
        ('created_at', 'TEXT'),
    ),
    'ticket_time_tracking': (
        ('username', 'TEXT'),
    ),
}

INDEXES_SQL = (
    "CREATE INDEX IF NOT EXISTS idx_support_tickets_requester ON support_tickets (requester_username)",
    "CREATE INDEX IF NOT EXISTS idx_support_tickets_student ON support_tickets (student_id)",
    "CREATE INDEX IF NOT EXISTS idx_support_tickets_status ON support_tickets (status)",
    "CREATE INDEX IF NOT EXISTS idx_support_tickets_source ON support_tickets (source)",
    "CREATE INDEX IF NOT EXISTS idx_ticket_responses_ticket ON ticket_responses (ticket_id)",
    "CREATE INDEX IF NOT EXISTS idx_ticket_attachments_ticket ON ticket_attachments (ticket_id)",
)

INSERT_TRIGGER = 'trg_support_tickets_canonical_insert'
STATUS_TRIGGER = 'trg_support_tickets_status_vocabulary'


def _requester_sql(with_students: bool) -> tuple[str, str]:
    """``(username_expr, student_expr)`` resolving NEW.user_id like the backfill:
    a username, then a student number, then a ``users.id``."""
    by_name = "(SELECT username FROM users WHERE username = NEW.user_id)"
    by_sid = "(SELECT username FROM users WHERE student_id = NEW.user_id ORDER BY id LIMIT 1)"
    by_id = "(SELECT username FROM users WHERE CAST(id AS TEXT) = CAST(NEW.user_id AS TEXT))"
    username = f"COALESCE(NEW.requester_username, {by_name}, {by_sid}, {by_id})"
    student = ("COALESCE(NEW.student_id, "
               "(SELECT student_id FROM users WHERE username = NEW.requester_username), "
               "(SELECT student_id FROM users WHERE username = NEW.user_id), "
               "(SELECT student_id FROM users WHERE student_id = NEW.user_id ORDER BY id LIMIT 1), "
               "(SELECT student_id FROM users WHERE CAST(id AS TEXT) = CAST(NEW.user_id AS TEXT))")
    if with_students:
        student += ", (SELECT student_id FROM students WHERE student_id = NEW.user_id)"
    return username, student + ")"


def _trigger_sql(with_students: bool) -> tuple[str, str]:
    canonical = _in_list(STATUSES)
    sources = _in_list(SOURCES)
    username, student = _requester_sql(with_students)
    insert = f'''
CREATE TRIGGER IF NOT EXISTS {INSERT_TRIGGER}
AFTER INSERT ON support_tickets
WHEN NEW.requester_username IS NULL OR NEW.source IS NULL OR NEW.source NOT IN ({sources})
  OR (NEW.status IS NOT NULL AND NEW.status NOT IN ({canonical}))
BEGIN
  UPDATE support_tickets SET
    requester_username = {username},
    student_id = {student},
    channel = CASE WHEN NEW.source IN ({sources}) THEN channel
                   ELSE COALESCE(channel, NEW.source) END,
    source = CASE WHEN NEW.source IN ({sources}) THEN NEW.source
                  WHEN NEW.status GLOB '[A-Z]*' THEN 'support'
                  ELSE 'helpdesk' END,
    status = {status_case_sql('NEW.status')}
  WHERE ticket_id = NEW.ticket_id;
END
'''
    update = f'''
CREATE TRIGGER IF NOT EXISTS {STATUS_TRIGGER}
AFTER UPDATE OF status ON support_tickets
WHEN NEW.status IS NOT NULL AND NEW.status NOT IN ({canonical})
BEGIN
  UPDATE support_tickets SET status = {status_case_sql('NEW.status')}
  WHERE ticket_id = NEW.ticket_id;
END
'''
    return insert, update


# ── apply ────────────────────────────────────────────────────────────────

Execute = Callable[..., object]


def _has_table(execute: Execute, name: str) -> bool:
    return execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
                   (name,)).fetchone() is not None


def _columns(execute: Execute, table: str) -> set:
    return {row[1] for row in execute(f'PRAGMA table_info("{table}")').fetchall()}


def add_missing_columns(execute: Execute, table: str) -> list:
    """Add the :data:`ADDED_COLUMNS` ``table`` lacks; returns their names."""
    have = _columns(execute, table)
    added = []
    for name, ddl in ADDED_COLUMNS.get(table, ()):
        if name in have:
            continue
        # Names and types come from ADDED_COLUMNS above, never from input.
        execute(f'ALTER TABLE "{table}" ADD COLUMN "{name}" {ddl}')  # nosec B608
        added.append(name)
    return added


def apply(execute: Execute) -> bool:
    """Create the ticket tables in their current shape, add missing columns,
    indexes and the canonical-row triggers. Idempotent.

    ``execute`` is ``conn.execute`` / ``cursor.execute`` (sqlite3) or
    alembic's ``bind.exec_driver_sql`` — anything that runs one statement and
    returns a cursor. The caller commits.
    """
    for ddl in (SUPPORT_TICKETS_SQL, TICKET_RESPONSES_SQL, TICKET_ATTACHMENTS_SQL,
                TICKET_LINKS_SQL, TICKET_TIME_SQL, FOLLOWERS_SQL, INCIDENTS_SQL,
                INBOUND_MAIL_SQL):
        execute(ddl)
    for table in ADDED_COLUMNS:
        for name in add_missing_columns(execute, table):
            logger.info("Added %s.%s", table, name)
    execute(ESCALATION_FIRES_SQL)
    apply_care(execute)
    for ddl in INDEXES_SQL + COLLABORATION_INDEXES_SQL:
        execute(ddl)
    # The triggers read users (and students when present): a database
    # without users (a bare test fixture) gets the tables but no triggers.
    if _has_table(execute, 'users') and {'username', 'student_id'} <= _columns(execute, 'users'):
        insert, update = _trigger_sql(_has_table(execute, 'students'))
        execute(insert)
        execute(update)
    return True


def apply_care(execute: Execute) -> None:
    """The referral and erasure-request tables (part of :func:`apply`; the
    modules that use them call it too, so a database migrated before they
    existed gets them on first use). Idempotent."""
    execute(REFERRALS_SQL)
    execute(ERASURE_REQUESTS_SQL)
    for ddl in CARE_INDEXES_SQL:
        execute(ddl)


def ensure_support_tables(conn) -> bool:
    """Run :func:`apply` on ``conn`` (the caller commits)."""
    return apply(conn.execute)


def ensure_care_tables(conn) -> None:
    """Run :func:`apply_care` on ``conn`` (the caller commits)."""
    apply_care(conn.execute)


__all__ = [
    'STATUSES', 'ACTIVE_STATUSES', 'DONE_STATUSES', 'STATUS_LABELS', 'LEGACY_STATUS',
    'SOURCES', 'CONFIDENTIALITY', 'normalize_status', 'status_label', 'status_case_sql',
    'SUPPORT_TICKETS_SQL', 'TICKET_RESPONSES_SQL', 'TICKET_ATTACHMENTS_SQL',
    'ESCALATION_FIRES_SQL', 'REFERRALS_SQL', 'ERASURE_REQUESTS_SQL', 'ADDED_COLUMNS',
    'TICKET_LINKS_SQL', 'TICKET_TIME_SQL', 'FOLLOWERS_SQL', 'INCIDENTS_SQL', 'INBOUND_MAIL_SQL',
    'add_missing_columns', 'apply', 'apply_care', 'ensure_support_tables', 'ensure_care_tables',
]
