"""Schema for the university AI content detector (``infrastructure/ai/
ai_detector``): what used to be created at runtime by the detector mixins,
now declared once.

The reading tables themselves (``ai_detector_submissions`` /
``ai_detector_results``) and the review/comment tables belong to
``academic_integrity_schema``; this module adds the detector's own tables:
alerts, the persisted audit chain, model versions and federated updates,
and anything else the detector needs.

Shared by migration ``f3b5d7f9a1c4`` and :func:`apply_to_connection`.
Idempotent.
"""

from __future__ import annotations

# ── detector core (alerts, assignment profiles, activity, …) ────────────
CORE_TABLES: tuple = (
    """CREATE TABLE IF NOT EXISTS ai_detector_metadata (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        submission_id INTEGER NOT NULL,
        time_taken INTEGER,
        browser_info TEXT,
        device_fingerprint TEXT,
        ip_address TEXT,
        location_data TEXT,
        keystroke_data TEXT,
        FOREIGN KEY (submission_id) REFERENCES ai_detector_submissions (id)
    )""",
    """CREATE TABLE IF NOT EXISTS institutions (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        type TEXT,
        country TEXT,
        created_at TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS student_demographics (
        student_id TEXT PRIMARY KEY,
        age_group TEXT,
        gender TEXT,
        ethnicity TEXT,
        native_language TEXT,
        academic_level TEXT,
        accommodations TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS processing_queue (
        id TEXT PRIMARY KEY,
        submission_data TEXT NOT NULL,
        priority INTEGER DEFAULT 1,
        status TEXT DEFAULT 'queued',
        created_at TEXT NOT NULL,
        processed_at TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS advanced_detection_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        submission_id INTEGER NOT NULL,
        temporal_analysis TEXT,
        citation_analysis TEXT,
        behavioral_analysis TEXT,
        multimodal_analysis TEXT,
        adversarial_analysis TEXT,
        ensemble_prediction TEXT,
        risk_prediction TEXT,
        bias_adjusted_score REAL,
        blockchain_hash TEXT,
        FOREIGN KEY (submission_id) REFERENCES ai_detector_submissions (id)
    )""",
    """CREATE TABLE IF NOT EXISTS style_fingerprints (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL,
        fingerprint_data TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS ai_detector_alert_config (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        config_key TEXT UNIQUE NOT NULL,
        config_value TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        updated_by TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS ai_detector_email_alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT NOT NULL,
        risk_levels TEXT NOT NULL,
        include_details INTEGER NOT NULL DEFAULT 1,
        is_active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL,
        created_by TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS ai_detector_alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        submission_id TEXT NOT NULL,
        student_id TEXT NOT NULL,
        submission_title TEXT,
        risk_level TEXT NOT NULL,
        ai_score REAL NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        created_at TEXT NOT NULL,
        reviewed_at TEXT,
        reviewed_by TEXT,
        dismissal_reason TEXT,
        notes TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS ai_detector_escalations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        escalation_id TEXT UNIQUE NOT NULL,
        submission_id TEXT NOT NULL,
        student_id TEXT NOT NULL,
        violation_type TEXT NOT NULL,
        summary TEXT NOT NULL,
        recommended_action TEXT,
        status TEXT NOT NULL DEFAULT 'pending',
        escalated_by TEXT,
        escalated_at TEXT NOT NULL,
        reviewed_by TEXT,
        reviewed_at TEXT,
        resolution TEXT,
        notes TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS ai_detector_academic_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        record_id TEXT UNIQUE NOT NULL,
        student_id TEXT NOT NULL,
        submission_id TEXT NOT NULL,
        violation_type TEXT NOT NULL,
        sanction TEXT NOT NULL,
        sanction_details TEXT,
        notes TEXT,
        reviewer_id TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'active',
        created_at TEXT NOT NULL,
        synced_to_external INTEGER DEFAULT 0,
        synced_at TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS ai_detector_activity_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        action TEXT NOT NULL,
        action_type TEXT,
        target_id TEXT,
        details TEXT,
        ip_address TEXT,
        timestamp TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS ai_detector_assignment_profiles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        profile_id TEXT UNIQUE NOT NULL,
        course_code TEXT NOT NULL,
        assignment_name TEXT NOT NULL,
        assignment_type TEXT NOT NULL,
        word_count_min INTEGER,
        word_count_max INTEGER,
        references_required INTEGER DEFAULT 0,
        technical_terms TEXT,
        allow_collaboration INTEGER DEFAULT 0,
        created_at TEXT NOT NULL,
        created_by TEXT,
        baseline_set INTEGER DEFAULT 0
    )""",
    """CREATE TABLE IF NOT EXISTS ai_detector_baselines (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        profile_id TEXT UNIQUE NOT NULL,
        avg_sentence_length REAL,
        vocabulary_complexity REAL,
        avg_word_count REAL,
        samples_analyzed INTEGER,
        created_at TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS ai_detector_batch_jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id TEXT UNIQUE NOT NULL,
        job_type TEXT NOT NULL,
        target_path TEXT NOT NULL,
        scheduled_time TEXT NOT NULL,
        notify_email TEXT,
        status TEXT NOT NULL DEFAULT 'queued',
        progress INTEGER DEFAULT 0,
        created_at TEXT NOT NULL,
        started_at TEXT,
        completed_at TEXT,
        result TEXT,
        error TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS student_review_flags (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL,
        submission_id INTEGER,
        reason TEXT NOT NULL,
        severity TEXT NOT NULL,
        flagged_by TEXT,
        flagged_at TEXT NOT NULL,
        status TEXT DEFAULT 'active',
        resolved_at TEXT,
        resolved_by TEXT,
        resolution_notes TEXT
    )""",
)
# Alerts, escalations and academic records now lead to the integrity
# workflow: the reading they came from and the case they opened.
CORE_COLUMNS: tuple = (
    ("ai_detector_alerts", "ai_result_id", "INTEGER"),
    ("ai_detector_alerts", "module_code", "TEXT"),
    ("ai_detector_alerts", "assignment_id", "TEXT"),
    ("ai_detector_alerts", "case_id", "INTEGER"),
    ("ai_detector_escalations", "ai_result_id", "INTEGER"),
    ("ai_detector_escalations", "case_id", "INTEGER"),
    ("ai_detector_academic_records", "ai_result_id", "INTEGER"),
    ("ai_detector_academic_records", "case_id", "INTEGER"),
    # Batch jobs run as the person who scheduled them, on one module.
    ("ai_detector_batch_jobs", "course_code", "TEXT"),
    ("ai_detector_batch_jobs", "assignment_id", "TEXT"),
    ("ai_detector_batch_jobs", "created_by", "TEXT"),
    ("ai_detector_batch_jobs", "retries", "INTEGER DEFAULT 0"),
)

# ── models, federated updates, audit chain, analytics ───────────────────
ML_TABLES: tuple = (
    # Indicator models: trained on human review outcomes, imported, or
    # aggregated from federated updates (ml/indicator_model.py).
    """CREATE TABLE IF NOT EXISTS ai_detector_model_versions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        version TEXT UNIQUE NOT NULL,
        model_path TEXT NOT NULL,
        accuracy REAL,
        precision_score REAL,
        recall_score REAL,
        f1_score REAL,
        training_samples INTEGER,
        is_active INTEGER DEFAULT 0,
        created_at TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS ai_detector_model_rollbacks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        from_version TEXT,
        to_version TEXT NOT NULL,
        reason TEXT,
        rolled_back_by TEXT,
        rolled_back_at TEXT NOT NULL
    )""",
    # Detector settings that are not integrity settings (institution id
    # for federated updates).
    """CREATE TABLE IF NOT EXISTS ai_detector_settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        updated_by TEXT,
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    # Federated learning: model updates exported to, or imported from,
    # other institutions as files (features/federated_learning.py).
    """CREATE TABLE IF NOT EXISTS ai_federated_updates (
        update_id INTEGER PRIMARY KEY AUTOINCREMENT,
        direction TEXT NOT NULL CHECK (direction IN ('exported', 'imported')),
        institution_id TEXT NOT NULL,
        model_version TEXT,
        features TEXT NOT NULL,
        coef TEXT NOT NULL,
        intercept REAL NOT NULL,
        n_samples INTEGER NOT NULL,
        epsilon REAL,
        sha256 TEXT NOT NULL,
        path TEXT,
        created_by TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        used_in_version TEXT
    )""",
    # The persisted, hash-chained audit trail (features/blockchain_audit.py).
    """CREATE TABLE IF NOT EXISTS ai_audit_chain (
        idx INTEGER PRIMARY KEY,
        event TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        actor TEXT NOT NULL,
        at TEXT NOT NULL,
        prev_hash TEXT NOT NULL,
        hash TEXT NOT NULL UNIQUE
    )""",
    # Work waiting for the real-time processor (features/realtime_processor.py).
    """CREATE TABLE IF NOT EXISTS processing_queue (
        id TEXT PRIMARY KEY,
        submission_data TEXT NOT NULL,
        priority INTEGER DEFAULT 1,
        status TEXT DEFAULT 'queued',
        created_at TEXT NOT NULL,
        processed_at TEXT
    )""",
    # Privacy: consent records, retention runs, access log, self-check use.
    """CREATE TABLE IF NOT EXISTS privacy_consent (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL,
        consent_type TEXT NOT NULL,
        granted INTEGER NOT NULL,
        granted_at TEXT NOT NULL,
        expires_at TEXT,
        version TEXT NOT NULL,
        UNIQUE(student_id, consent_type)
    )""",
    """CREATE TABLE IF NOT EXISTS data_retention (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        data_type TEXT NOT NULL,
        retention_period INTEGER NOT NULL,
        deletion_date TEXT,
        status TEXT DEFAULT 'active'
    )""",
    """CREATE TABLE IF NOT EXISTS privacy_audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        action TEXT NOT NULL,
        student_id TEXT,
        user_id INTEGER,
        data_accessed TEXT,
        timestamp TEXT NOT NULL,
        ip_address TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS self_check_usage (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_hash TEXT NOT NULL,
        score_range TEXT NOT NULL,
        timestamp TEXT NOT NULL
    )""",
)
ML_COLUMNS: tuple = (
    ("ai_detector_model_versions", "source", "TEXT DEFAULT 'trained'"),
    ("ai_detector_model_versions", "trained_by", "TEXT"),
    ("ai_detector_model_versions", "sha256", "TEXT"),
    ("ai_detector_model_versions", "features", "TEXT"),
    ("ai_detector_model_versions", "metrics", "TEXT"),
    ("ai_detector_model_versions", "activated_at", "TEXT"),
    ("ai_detector_model_versions", "note", "TEXT"),
    ("processing_queue", "kind", "TEXT DEFAULT 'text'"),
    ("processing_queue", "queued_by", "TEXT"),
    ("processing_queue", "attempts", "INTEGER DEFAULT 0"),
    ("processing_queue", "started_at", "TEXT"),
    ("processing_queue", "error", "TEXT"),
    ("processing_queue", "ai_result_id", "INTEGER"),
    ("data_retention", "cutoff", "TEXT"),
    ("data_retention", "removed", "INTEGER"),
    ("data_retention", "run_by", "TEXT"),
    ("data_retention", "run_at", "TEXT"),
)

INDEXES: tuple = (
    # models / queue / privacy (ML section)
    "CREATE INDEX IF NOT EXISTS ix_processing_queue_status ON processing_queue (status, priority)",
    "CREATE INDEX IF NOT EXISTS ix_self_check_usage ON self_check_usage (student_hash, timestamp)",
    "CREATE INDEX IF NOT EXISTS ix_ai_audit_chain_event ON ai_audit_chain (event)",
)


def _columns(execute, table):
    return {r[1] for r in execute(f'PRAGMA table_info("{table}")').fetchall()}


def apply(execute) -> None:
    for ddl in CORE_TABLES + ML_TABLES:
        execute(ddl)
    for table, column, decl in CORE_COLUMNS + ML_COLUMNS:
        existing = _columns(execute, table)
        if existing and column not in existing:
            execute(f'ALTER TABLE "{table}" ADD COLUMN "{column}" {decl}')
    for ddl in INDEXES:
        execute(ddl)


_APPLIED: set[str] = set()


def apply_to_connection(conn) -> None:
    """:func:`apply` once per database file (the integrity schema first, as
    the detector's tables refer to its reading tables)."""
    from education_system.systems.university.infrastructure.database.schemas import (
        academic_integrity_schema,
    )
    academic_integrity_schema.apply_to_connection(conn)
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
