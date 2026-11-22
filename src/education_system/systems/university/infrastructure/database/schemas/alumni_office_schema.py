"""Alumni office: roles and audit, contact consent and suppression, data
requests, the alumni transition, giving (Gift Aid declarations and claims,
pledges, refunds, receipts), newsletter delivery with unsubscribe tokens,
mentor vetting and mentoring concerns, and content reports.

The canonical records are the existing tables: ``alumni`` (one row per
graduate, ``alumni_id`` = student id), ``donations``,
``fundraising_campaigns``, ``regional_chapters`` + ``chapter_memberships``,
``mentorships``, ``alumni_forum`` / ``forum_replies``, ``alumni_stories``,
``photo_gallery``, ``newsletters``. Rows written to the duplicate tables
(``chapter_members``, ``alumni_donations``) are copied across once.

Shared by migration ``e6a8c0d2f4b7`` and :func:`apply_to_connection`
(``university/application/alumni/``). Idempotent.
"""

from __future__ import annotations

COLUMNS = (
    ("alumni", "marketing_consent", "INTEGER"),          # NULL = not asked
    ("alumni", "consent_updated_at", "TEXT"),
    ("alumni", "consent_source", "TEXT"),
    ("alumni", "do_not_contact", "INTEGER DEFAULT 0"),
    ("alumni", "email_bounced", "INTEGER DEFAULT 0"),
    ("alumni", "deceased_at", "TEXT"),
    ("alumni", "anonymised_at", "TEXT"),
    ("alumni", "graduate_outcomes_due", "TEXT"),
    ("alumni", "updated_at", "TEXT"),
    ("alumni", "updated_by", "TEXT"),
    ("donations", "status", "TEXT DEFAULT 'received'"),
    ("donations", "gift_aid_declaration_id", "INTEGER"),
    ("donations", "gift_aid_claim_id", "INTEGER"),
    ("donations", "gift_aid_adjusted_in", "INTEGER"),
    ("gift_aid_claims", "adjustments_total", "REAL DEFAULT 0"),
    ("donations", "pledge_id", "INTEGER"),
    ("donations", "receipt_number", "TEXT"),
    ("donations", "thanked_at", "TEXT"),
    ("donations", "refunded_at", "TEXT"),
    ("donations", "refund_reason", "TEXT"),
    ("donations", "finance_payment_id", "INTEGER"),
    ("donations", "recorded_by", "TEXT"),
    ("mentorships", "student_consent_at", "TEXT"),
    ("mentorships", "matched_by", "TEXT"),
    ("mentorships", "ended_by", "TEXT"),
    ("mentorships", "ended_reason", "TEXT"),
    ("alumni_forum", "hidden_at", "TEXT"),
    ("alumni_forum", "hidden_reason", "TEXT"),
    ("forum_replies", "hidden_at", "TEXT"),
    ("forum_replies", "hidden_reason", "TEXT"),
    ("alumni_stories", "status", "TEXT DEFAULT 'published'"),
    ("alumni_stories", "consent_at", "TEXT"),
    ("alumni_stories", "approved_by", "TEXT"),
    ("photo_gallery", "consent_confirmed", "INTEGER DEFAULT 0"),
    ("photo_gallery", "hidden_at", "TEXT"),
    ("newsletters", "sent_at", "TEXT"),
    ("newsletters", "sent_by", "TEXT"),
    ("newsletters", "sent_count", "INTEGER DEFAULT 0"),
    ("newsletters", "suppressed_count", "INTEGER DEFAULT 0"),
    ("newsletters", "audience_json", "TEXT"),
)

TABLES = (
    """CREATE TABLE IF NOT EXISTS alumni_roles (
        username TEXT NOT NULL,
        role TEXT NOT NULL CHECK (role IN ('alumni_office', 'fundraising',
                                           'mentoring_coordinator', 'moderator')),
        granted_by TEXT,
        granted_at TEXT NOT NULL DEFAULT (datetime('now')),
        PRIMARY KEY (username, role)
    )""",
    """CREATE TABLE IF NOT EXISTS alumni_audit (
        audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
        entity TEXT NOT NULL,
        entity_id TEXT NOT NULL,
        action TEXT NOT NULL,
        actor TEXT,
        detail TEXT,
        at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    "CREATE INDEX IF NOT EXISTS ix_alumni_audit_entity ON alumni_audit (entity, entity_id)",
    """CREATE TABLE IF NOT EXISTS alumni_data_requests (
        request_id INTEGER PRIMARY KEY AUTOINCREMENT,
        alumni_id TEXT NOT NULL,
        kind TEXT NOT NULL CHECK (kind IN ('export', 'erasure')),
        requested_by TEXT,
        requested_at TEXT NOT NULL DEFAULT (datetime('now')),
        status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'completed',
                                                              'refused')),
        completed_by TEXT,
        completed_at TEXT,
        note TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS alumni_unsubscribe_tokens (
        token_hash TEXT PRIMARY KEY,
        alumni_id TEXT NOT NULL,
        newsletter_id INTEGER,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        used_at TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS newsletter_deliveries (
        newsletter_id INTEGER NOT NULL,
        alumni_id TEXT NOT NULL,
        outcome TEXT NOT NULL,
        at TEXT NOT NULL DEFAULT (datetime('now')),
        PRIMARY KEY (newsletter_id, alumni_id)
    )""",
    """CREATE TABLE IF NOT EXISTS gift_aid_declarations (
        declaration_id INTEGER PRIMARY KEY AUTOINCREMENT,
        alumni_id TEXT NOT NULL,
        full_name TEXT NOT NULL,
        house TEXT NOT NULL,
        postcode TEXT NOT NULL,
        method TEXT NOT NULL CHECK (method IN ('written', 'oral', 'online')),
        made_on TEXT NOT NULL,
        covers_past_four_years INTEGER NOT NULL DEFAULT 1,
        taxpayer_confirmed INTEGER NOT NULL DEFAULT 0,
        recorded_by TEXT,
        cancelled_at TEXT,
        cancelled_by TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS gift_aid_claims (
        claim_id INTEGER PRIMARY KEY AUTOINCREMENT,
        period_from TEXT NOT NULL,
        period_to TEXT NOT NULL,
        donations_total REAL NOT NULL DEFAULT 0,
        claim_total REAL NOT NULL DEFAULT 0,
        adjustments_total REAL DEFAULT 0,
        gift_count INTEGER NOT NULL DEFAULT 0,
        status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'submitted', 'paid')),
        created_by TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        submitted_at TEXT,
        hmrc_reference TEXT,
        paid_at TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS donation_pledges (
        pledge_id INTEGER PRIMARY KEY AUTOINCREMENT,
        alumni_id TEXT NOT NULL,
        campaign_id INTEGER,
        amount REAL NOT NULL CHECK (amount > 0),
        frequency TEXT NOT NULL CHECK (frequency IN ('one_off', 'monthly', 'quarterly',
                                                     'annual')),
        instalments INTEGER NOT NULL DEFAULT 1,
        paid_instalments INTEGER NOT NULL DEFAULT 0,
        next_due TEXT,
        status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'completed',
                                                                'cancelled')),
        created_by TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        cancelled_reason TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS mentor_vetting (
        alumni_id TEXT PRIMARY KEY,
        status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved',
                                                                 'rejected')),
        training_completed INTEGER NOT NULL DEFAULT 0,
        checked_by TEXT,
        checked_at TEXT,
        expires_on TEXT,
        notes TEXT,
        offered_at TEXT NOT NULL DEFAULT (datetime('now')),
        focus_areas TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS mentoring_concerns (
        concern_id INTEGER PRIMARY KEY AUTOINCREMENT,
        mentorship_id INTEGER NOT NULL,
        raised_by TEXT NOT NULL,
        raised_at TEXT NOT NULL DEFAULT (datetime('now')),
        description TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'escalated', 'closed')),
        handled_by TEXT,
        handled_at TEXT,
        outcome TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS alumni_content_reports (
        report_id INTEGER PRIMARY KEY AUTOINCREMENT,
        kind TEXT NOT NULL CHECK (kind IN ('forum_post', 'forum_reply', 'story', 'photo')),
        item_id INTEGER NOT NULL,
        reported_by TEXT NOT NULL,
        reason TEXT NOT NULL,
        reported_at TEXT NOT NULL DEFAULT (datetime('now')),
        status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'upheld', 'dismissed')),
        handled_by TEXT,
        handled_at TEXT
    )""",
    "CREATE UNIQUE INDEX IF NOT EXISTS ux_chapter_memberships ON chapter_memberships "
    "(chapter_id, alumni_id)",
    # networking requests between alumni (the directory screen used to create this on open)
    """CREATE TABLE IF NOT EXISTS alumni_connections (
        connection_id INTEGER PRIMARY KEY AUTOINCREMENT,
        requester_id TEXT NOT NULL,
        recipient_id TEXT NOT NULL,
        status TEXT DEFAULT 'pending',
        message TEXT,
        request_date TEXT DEFAULT (datetime('now')),
        response_date TEXT
    )""",
)

COPIES = (
    # chapter members written by the old screen
    ("chapter_members", "INSERT OR IGNORE INTO chapter_memberships (chapter_id, alumni_id, "
     "join_date, role) SELECT chapter_id, member_id, join_date, COALESCE(role, 'member') FROM "
     "chapter_members WHERE COALESCE(status, 'active') = 'active' AND member_id IS NOT NULL"),
    # gifts written by the old CLI
    ("alumni_donations", "INSERT INTO donations (alumni_id, amount, donation_date, campaign_id, "
     "payment_method, is_recurring, notes, donation_type, status) SELECT CAST(d.alumni_id AS "
     "TEXT), COALESCE(d.amount, d.donation_amount), d.donation_date, d.campaign_id, "
     "d.payment_method, d.is_recurring, COALESCE(d.purpose, d.fund_designation, '') || ' (from "
     "alumni_donations #' || d.donation_id || ')', COALESCE(d.donation_type, 'general'), "
     "'received' FROM alumni_donations d WHERE NOT EXISTS (SELECT 1 FROM donations x WHERE "
     "x.notes LIKE '%(from alumni_donations #' || d.donation_id || ')%')"),
)


def _columns(execute, table):
    return {r[1] for r in execute(f'PRAGMA table_info("{table}")').fetchall()}


def apply(execute) -> None:
    for table, column, decl in COLUMNS:
        existing = _columns(execute, table)
        if existing and column not in existing:
            execute(f'ALTER TABLE "{table}" ADD COLUMN "{column}" {decl}')
    for ddl in TABLES:
        if "chapter_memberships" in ddl and not _columns(execute, "chapter_memberships"):
            continue
        execute(ddl)
    for source, sql in COPIES:
        if _columns(execute, source) and _columns(execute, "donations") and \
                _columns(execute, "chapter_memberships"):
            execute(sql)


_APPLIED: set[str] = set()


def apply_to_connection(conn) -> None:
    """:func:`apply` once per database file. Inside a caller's open
    transaction it applies without committing or caching."""
    try:
        key = conn.execute("PRAGMA database_list").fetchone()[2]
    except Exception:
        key = None
    if key and key in _APPLIED:
        return
    busy = conn.in_transaction
    apply(conn.execute)
    if busy:
        return
    conn.commit()
    if key:
        _APPLIED.add(key)
