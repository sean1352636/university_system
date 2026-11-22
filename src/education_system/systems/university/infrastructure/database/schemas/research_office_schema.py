"""Research office: who holds research roles, the audit trail, the ethics
review workflow, project teams, grant costing / approvals / spend / reports,
output authors / open access / internal review, REF staff, IP deadlines and
inventor payments, declarations of interest and data management plans.

The portal's main records stay on the university's existing tables
(``research_projects``, ``ethics_reviews``, ``grant_applications``,
``grant_budgets``, ``research_publications``, ``ip_disclosures``,
``ip_inventors``, ``ip_licenses``, ``ip_revenue_shares``,
``research_profiles``, ``ref_impact_cases``); this module adds the columns
the workflows need and the tables they did not have.

People are addressed by username (staff) or student id (students).

Shared by migration ``c4e6f8a0b2d5`` and :func:`apply_to_connection`
(``university/application/research/``). Idempotent.
"""

from __future__ import annotations

COLUMNS = (
    # ethics workflow
    ("ethics_reviews", "kind", "TEXT DEFAULT 'application'"),
    ("ethics_reviews", "parent_review_id", "INTEGER"),
    ("ethics_reviews", "applicant_id", "TEXT"),
    ("ethics_reviews", "supervisor_id", "TEXT"),
    ("ethics_reviews", "supervisor_endorsed_by", "TEXT"),
    ("ethics_reviews", "supervisor_endorsed_at", "TEXT"),
    ("ethics_reviews", "route", "TEXT"),
    ("ethics_reviews", "summary", "TEXT"),
    ("ethics_reviews", "participants", "TEXT"),
    ("ethics_reviews", "data_handling", "TEXT"),
    ("ethics_reviews", "start_date", "TEXT"),
    ("ethics_reviews", "end_date", "TEXT"),
    ("ethics_reviews", "decided_by", "TEXT"),
    ("ethics_reviews", "created_by", "TEXT"),
    ("ethics_reviews", "updated_at", "TEXT"),
    # projects
    ("research_projects", "reference", "TEXT"),
    ("research_projects", "created_by", "TEXT"),
    ("research_projects", "closed_at", "TEXT"),
    ("research_projects", "needs_ethics", "INTEGER DEFAULT 0"),
    # grants
    ("grant_applications", "status", "TEXT DEFAULT 'draft'"),
    ("grant_applications", "department", "TEXT"),
    ("grant_applications", "scheme", "TEXT"),
    ("grant_applications", "funder_rate", "REAL DEFAULT 80"),
    ("grant_applications", "ethics_required", "INTEGER DEFAULT 0"),
    ("grant_applications", "dmp_required", "INTEGER DEFAULT 1"),
    ("grant_applications", "hod_approved_by", "TEXT"),
    ("grant_applications", "hod_approved_at", "TEXT"),
    ("grant_applications", "office_approved_by", "TEXT"),
    ("grant_applications", "office_approved_at", "TEXT"),
    ("grant_applications", "award_reference", "TEXT"),
    ("grant_applications", "accepted_by", "TEXT"),
    ("grant_applications", "accepted_at", "TEXT"),
    ("grant_applications", "closed_at", "TEXT"),
    ("grant_applications", "created_by", "TEXT"),
    ("grant_applications", "decision_note", "TEXT"),
    # outputs
    ("research_publications", "acceptance_date", "TEXT"),
    ("research_publications", "deposit_date", "TEXT"),
    ("research_publications", "repository_url", "TEXT"),
    ("research_publications", "oa_route", "TEXT"),
    ("research_publications", "oa_exception", "TEXT"),
    ("research_publications", "issn", "TEXT"),
    ("research_publications", "created_by", "TEXT"),
    ("research_publications", "updated_at", "TEXT"),
    # IP
    ("ip_disclosures", "project_id", "INTEGER"),
    ("ip_disclosures", "filing_date", "TEXT"),
    ("ip_disclosures", "application_number", "TEXT"),
    # REF narratives
    ("ref_impact_cases", "lead_username", "TEXT"),
    ("ref_environment_statements", "drafted_by_username", "TEXT"),
)

TABLES = (
    """CREATE TABLE IF NOT EXISTS research_office_roles (
        username TEXT NOT NULL,
        role TEXT NOT NULL CHECK (role IN ('research_office', 'ethics_chair',
            'ethics_reviewer', 'head_of_department', 'ref_lead', 'tto')),
        scope TEXT NOT NULL DEFAULT '',
        granted_by TEXT,
        granted_at TEXT NOT NULL DEFAULT (datetime('now')),
        PRIMARY KEY (username, role, scope)
    )""",
    """CREATE TABLE IF NOT EXISTS research_audit (
        audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
        entity TEXT NOT NULL,
        entity_id TEXT NOT NULL,
        action TEXT NOT NULL,
        actor TEXT,
        detail TEXT,
        at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    "CREATE INDEX IF NOT EXISTS ix_research_audit_entity ON research_audit (entity, entity_id)",
    # ── ethics ──
    """CREATE TABLE IF NOT EXISTS ethics_reviewer_allocations (
        allocation_id INTEGER PRIMARY KEY AUTOINCREMENT,
        review_id INTEGER NOT NULL REFERENCES ethics_reviews(review_id) ON DELETE CASCADE,
        reviewer TEXT NOT NULL,
        allocated_by TEXT,
        allocated_at TEXT NOT NULL DEFAULT (datetime('now')),
        status TEXT NOT NULL DEFAULT 'allocated'
            CHECK (status IN ('allocated', 'conflicted', 'completed', 'withdrawn')),
        conflict_detail TEXT,
        recommendation TEXT CHECK (recommendation IS NULL OR recommendation IN
            ('approve', 'approve_with_conditions', 'revise', 'reject')),
        comments TEXT,
        completed_at TEXT
    )""",
    "CREATE INDEX IF NOT EXISTS ix_ethics_alloc_review ON ethics_reviewer_allocations "
    "(review_id, status)",
    """CREATE TABLE IF NOT EXISTS ethics_conditions (
        condition_id INTEGER PRIMARY KEY AUTOINCREMENT,
        review_id INTEGER NOT NULL REFERENCES ethics_reviews(review_id) ON DELETE CASCADE,
        condition_text TEXT NOT NULL,
        met_at TEXT,
        met_by TEXT,
        evidence TEXT
    )""",
    # ── grants ──
    """CREATE TABLE IF NOT EXISTS grant_cost_lines (
        line_id INTEGER PRIMARY KEY AUTOINCREMENT,
        application_id INTEGER NOT NULL REFERENCES grant_applications(application_id)
            ON DELETE CASCADE,
        category TEXT NOT NULL CHECK (category IN ('directly_incurred', 'directly_allocated',
            'indirect', 'exception')),
        item TEXT NOT NULL,
        amount REAL NOT NULL CHECK (amount >= 0)
    )""",
    """CREATE TABLE IF NOT EXISTS grant_spend (
        spend_id INTEGER PRIMARY KEY AUTOINCREMENT,
        budget_id INTEGER NOT NULL REFERENCES grant_budgets(budget_id),
        amount REAL NOT NULL,
        spent_on TEXT NOT NULL,
        description TEXT NOT NULL,
        recorded_by TEXT,
        recorded_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    """CREATE TABLE IF NOT EXISTS grant_reports (
        report_id INTEGER PRIMARY KEY AUTOINCREMENT,
        application_id INTEGER NOT NULL REFERENCES grant_applications(application_id)
            ON DELETE CASCADE,
        kind TEXT NOT NULL CHECK (kind IN ('interim', 'final', 'financial', 'other')),
        due_date TEXT NOT NULL,
        submitted_at TEXT,
        submitted_by TEXT,
        note TEXT
    )""",
    # ── project teams ──
    "CREATE UNIQUE INDEX IF NOT EXISTS ux_research_team_active ON research_team_members "
    "(project_id, staff_id) WHERE is_active = 1",
    # ── outputs ──
    """CREATE TABLE IF NOT EXISTS research_output_authors (
        publication_id INTEGER NOT NULL REFERENCES research_publications(publication_id)
            ON DELETE CASCADE,
        position INTEGER NOT NULL,
        name TEXT NOT NULL,
        username TEXT,
        PRIMARY KEY (publication_id, position)
    )""",
    "CREATE INDEX IF NOT EXISTS ix_output_authors_user ON research_output_authors (username)",
    """CREATE TABLE IF NOT EXISTS research_output_reviews (
        review_id INTEGER PRIMARY KEY AUTOINCREMENT,
        publication_id INTEGER NOT NULL REFERENCES research_publications(publication_id)
            ON DELETE CASCADE,
        reviewer TEXT NOT NULL,
        score INTEGER NOT NULL CHECK (score BETWEEN 0 AND 4),
        comment TEXT,
        reviewed_at TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE (publication_id, reviewer)
    )""",
    """CREATE TABLE IF NOT EXISTS ref_staff_uoa (
        username TEXT NOT NULL PRIMARY KEY,
        uoa TEXT NOT NULL,
        fte REAL NOT NULL DEFAULT 1 CHECK (fte > 0 AND fte <= 1),
        updated_by TEXT,
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    # ── IP ──
    """CREATE TABLE IF NOT EXISTS ip_deadlines (
        deadline_id INTEGER PRIMARY KEY AUTOINCREMENT,
        disclosure_id INTEGER NOT NULL REFERENCES ip_disclosures(disclosure_id)
            ON DELETE CASCADE,
        kind TEXT NOT NULL,
        due_date TEXT NOT NULL,
        done_at TEXT,
        done_by TEXT,
        note TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS ip_inventor_payments (
        payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
        revenue_id INTEGER NOT NULL REFERENCES ip_revenue_shares(revenue_id) ON DELETE CASCADE,
        username TEXT NOT NULL,
        amount REAL NOT NULL
    )""",
    # ── integrity ──
    """CREATE TABLE IF NOT EXISTS research_interest_declarations (
        declaration_id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL,
        kind TEXT NOT NULL CHECK (kind IN ('none', 'financial', 'shareholding', 'consultancy',
            'directorship', 'gift', 'personal', 'other')),
        counterpart TEXT,
        description TEXT,
        value REAL,
        project_id INTEGER REFERENCES research_projects(project_id),
        declared_at TEXT NOT NULL DEFAULT (datetime('now')),
        status TEXT NOT NULL DEFAULT 'declared'
            CHECK (status IN ('declared', 'no_action', 'managed', 'closed')),
        management_plan TEXT,
        reviewed_by TEXT,
        reviewed_at TEXT
    )""",
    "CREATE INDEX IF NOT EXISTS ix_interest_decl_user ON research_interest_declarations "
    "(username, declared_at)",
    """CREATE TABLE IF NOT EXISTS research_data_plans (
        plan_id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id INTEGER NOT NULL REFERENCES research_projects(project_id),
        version INTEGER NOT NULL DEFAULT 1,
        status TEXT NOT NULL DEFAULT 'draft'
            CHECK (status IN ('draft', 'submitted', 'approved', 'changes_requested',
                              'superseded')),
        data_types TEXT,
        storage TEXT,
        sharing TEXT,
        repository TEXT,
        retention_years INTEGER,
        personal_data INTEGER NOT NULL DEFAULT 0,
        dpia_reference TEXT,
        author TEXT,
        submitted_at TEXT,
        reviewed_by TEXT,
        reviewed_at TEXT,
        review_note TEXT,
        UNIQUE (project_id, version)
    )""",
)

#: One spelling for units of assessment: "UoA 11" (the QA screens wrote "UOA11").
NORMALISE_UOA = tuple(
    f"UPDATE OR IGNORE {table} SET uoa = 'UoA ' || CAST(SUBSTR(REPLACE(uoa, ' ', ''), 4) AS "
    f"INTEGER) WHERE UPPER(REPLACE(uoa, ' ', '')) GLOB 'UOA[0-9]*' AND uoa NOT GLOB 'UoA [0-9]*'"
    for table in ("ref_impact_cases", "ref_environment_statements", "research_publications"))


def _columns(execute, table):
    return {r[1] for r in execute(f'PRAGMA table_info("{table}")').fetchall()}


def apply(execute) -> None:
    for table, column, decl in COLUMNS:
        existing = _columns(execute, table)
        if existing and column not in existing:
            execute(f'ALTER TABLE "{table}" ADD COLUMN "{column}" {decl}')
    for ddl in TABLES:
        if "research_team_members" in ddl and not _columns(execute, "research_team_members"):
            continue
        execute(ddl)
    for table, sql in zip(("ref_impact_cases", "ref_environment_statements",
                           "research_publications"), NORMALISE_UOA):
        if _columns(execute, table):
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
