"""Schema for the health portal's clinic workflows (wave 2B).

* Diary: ``provider_time_off`` (blocks booking), ``provider_schedule_templates``
  (weekly patterns that write ``provider_schedules``), ``appointment_waitlist``
  (join when no slot; offered on a cancellation), ``appointment_reminders_sent``
  (one reminder per appointment and kind), ``appointment_feedback``
  (post-appointment satisfaction, replacing mock figures).
* Prescribing safety: ``drug_classes`` (drug → class), ``drug_class_cross_reactivity``,
  ``drug_interactions`` (a maintained table, seeded), and
  ``prescription_safety_overrides`` (a clinician overriding a hard stop, with
  the reason).
* ``outbreak_investigations`` (surveillance investigations were not saved).
* ``health_records`` soft delete: ``archived`` / ``archived_at`` /
  ``archived_by`` / ``archive_reason``.

Shared by migration ``c2f4a6b8d0e3`` and :func:`apply_to_connection`.
Idempotent; never drops anything.
"""

from __future__ import annotations

TABLES = (
    """CREATE TABLE IF NOT EXISTS provider_time_off (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        provider_name TEXT NOT NULL,
        start_date TEXT NOT NULL,
        end_date TEXT NOT NULL,
        start_time TEXT,
        end_time TEXT,
        reason TEXT,
        created_by TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    "CREATE INDEX IF NOT EXISTS ix_provider_time_off ON provider_time_off (provider_name, start_date)",
    """CREATE TABLE IF NOT EXISTS provider_schedule_templates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        pattern_json TEXT NOT NULL,
        max_appointments INTEGER NOT NULL DEFAULT 8,
        specialty TEXT,
        location TEXT,
        active INTEGER NOT NULL DEFAULT 1,
        created_by TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    """CREATE TABLE IF NOT EXISTS appointment_waitlist (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL,
        appointment_type TEXT NOT NULL,
        provider_name TEXT,
        preferred_from TEXT,
        preferred_to TEXT,
        notes TEXT,
        status TEXT NOT NULL DEFAULT 'waiting'
            CHECK (status IN ('waiting', 'offered', 'booked', 'expired', 'withdrawn')),
        offered_date TEXT,
        offered_time TEXT,
        offered_provider TEXT,
        offered_at TEXT,
        offer_expires_at TEXT,
        booked_appointment_id INTEGER,
        created_by TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    "CREATE INDEX IF NOT EXISTS ix_appointment_waitlist ON appointment_waitlist (status, appointment_type)",
    """CREATE TABLE IF NOT EXISTS appointment_reminders_sent (
        source_table TEXT NOT NULL,
        appointment_id INTEGER NOT NULL,
        kind TEXT NOT NULL,
        sent_at TEXT NOT NULL DEFAULT (datetime('now')),
        PRIMARY KEY (source_table, appointment_id, kind)
    )""",
    """CREATE TABLE IF NOT EXISTS appointment_feedback (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_table TEXT NOT NULL,
        appointment_id INTEGER NOT NULL,
        student_id TEXT NOT NULL,
        provider_name TEXT,
        rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
        comments TEXT,
        submitted_at TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE (source_table, appointment_id)
    )""",
    """CREATE TABLE IF NOT EXISTS drug_classes (
        drug_name TEXT PRIMARY KEY COLLATE NOCASE,
        drug_class TEXT NOT NULL COLLATE NOCASE
    )""",
    """CREATE TABLE IF NOT EXISTS drug_class_cross_reactivity (
        class_a TEXT NOT NULL COLLATE NOCASE,
        class_b TEXT NOT NULL COLLATE NOCASE,
        note TEXT,
        PRIMARY KEY (class_a, class_b)
    )""",
    """CREATE TABLE IF NOT EXISTS drug_interactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        drug_a TEXT NOT NULL COLLATE NOCASE,
        drug_b TEXT NOT NULL COLLATE NOCASE,
        severity TEXT NOT NULL CHECK (severity IN ('severe', 'moderate', 'minor')),
        description TEXT NOT NULL,
        UNIQUE (drug_a, drug_b)
    )""",
    """CREATE TABLE IF NOT EXISTS prescription_safety_overrides (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL,
        medication_name TEXT NOT NULL,
        issue TEXT NOT NULL,
        reason TEXT NOT NULL,
        overridden_by TEXT NOT NULL,
        at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    """CREATE TABLE IF NOT EXISTS outbreak_investigations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        disease_name TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'monitoring', 'closed')),
        case_count INTEGER NOT NULL DEFAULT 0,
        case_ids TEXT,
        locations TEXT,
        findings TEXT,
        actions TEXT,
        opened_by TEXT,
        opened_at TEXT NOT NULL DEFAULT (datetime('now')),
        closed_at TEXT,
        closed_by TEXT
    )""",
)

COLUMNS = (
    ("health_records", "archived", "INTEGER DEFAULT 0"),
    ("health_records", "archived_at", "TEXT"),
    ("health_records", "archived_by", "TEXT"),
    ("health_records", "archive_reason", "TEXT"),
    ("health_appointments", "duration_minutes", "INTEGER DEFAULT 30"),
)

# Drug → class. Names are matched case-insensitively against a medication
# name's words; the class is used for allergy cross-matching and duplicates.
DRUG_CLASSES = (
    ("penicillin", "penicillin"), ("amoxicillin", "penicillin"), ("ampicillin", "penicillin"),
    ("flucloxacillin", "penicillin"), ("phenoxymethylpenicillin", "penicillin"),
    ("benzylpenicillin", "penicillin"), ("co-amoxiclav", "penicillin"),
    ("piperacillin", "penicillin"), ("cefalexin", "cephalosporin"),
    ("cephalexin", "cephalosporin"), ("cefuroxime", "cephalosporin"),
    ("ceftriaxone", "cephalosporin"), ("cefaclor", "cephalosporin"),
    ("cefixime", "cephalosporin"), ("ibuprofen", "nsaid"), ("naproxen", "nsaid"),
    ("diclofenac", "nsaid"), ("aspirin", "nsaid"), ("mefenamic", "nsaid"),
    ("celecoxib", "nsaid"), ("ketoprofen", "nsaid"), ("trimethoprim", "trimethoprim"),
    ("sulfamethoxazole", "sulfonamide"), ("co-trimoxazole", "sulfonamide"),
    ("sulfasalazine", "sulfonamide"), ("sulfadiazine", "sulfonamide"),
    ("erythromycin", "macrolide"), ("clarithromycin", "macrolide"),
    ("azithromycin", "macrolide"), ("doxycycline", "tetracycline"),
    ("lymecycline", "tetracycline"), ("oxytetracycline", "tetracycline"),
    ("ciprofloxacin", "fluoroquinolone"), ("levofloxacin", "fluoroquinolone"),
    ("codeine", "opioid"), ("tramadol", "opioid"), ("morphine", "opioid"),
    ("dihydrocodeine", "opioid"), ("paracetamol", "paracetamol"),
    ("sertraline", "ssri"), ("fluoxetine", "ssri"), ("citalopram", "ssri"),
    ("escitalopram", "ssri"), ("paroxetine", "ssri"), ("warfarin", "anticoagulant"),
    ("apixaban", "anticoagulant"), ("rivaroxaban", "anticoagulant"),
    ("lidocaine", "amide local anaesthetic"), ("articaine", "amide local anaesthetic"),
    ("prilocaine", "amide local anaesthetic"), ("metronidazole", "nitroimidazole"),
    ("salbutamol", "beta2 agonist"), ("prednisolone", "corticosteroid"),
)
# A documented allergy to the first class makes the second a warning.
CROSS_REACTIVITY = (
    ("penicillin", "cephalosporin", "About 1-2% of people allergic to penicillin react to "
                                    "cephalosporins; avoid after anaphylaxis."),
    ("cephalosporin", "penicillin", "Cross-reactivity with penicillins is possible."),
    ("sulfonamide", "trimethoprim", "Co-trimoxazole contains a sulfonamide; check the product."),
    ("nsaid", "nsaid", "NSAID hypersensitivity usually covers the whole class (incl. aspirin)."),
)
INTERACTIONS = (
    ("warfarin", "aspirin", "severe", "Greatly increased bleeding risk."),
    ("warfarin", "ibuprofen", "severe", "Increased bleeding risk; NSAIDs also cause GI bleeds."),
    ("warfarin", "naproxen", "severe", "Increased bleeding risk."),
    ("warfarin", "metronidazole", "severe", "Raises INR markedly; monitor or avoid."),
    ("warfarin", "clarithromycin", "severe", "Raises INR; monitor closely."),
    ("sertraline", "tramadol", "severe", "Risk of serotonin syndrome and seizures."),
    ("fluoxetine", "tramadol", "severe", "Risk of serotonin syndrome and seizures."),
    ("citalopram", "tramadol", "severe", "Risk of serotonin syndrome and seizures."),
    ("sertraline", "ibuprofen", "moderate", "SSRIs with NSAIDs raise GI bleeding risk."),
    ("citalopram", "aspirin", "moderate", "SSRIs with aspirin raise bleeding risk."),
    ("ciprofloxacin", "prednisolone", "moderate", "Higher risk of tendon rupture."),
    ("clarithromycin", "simvastatin", "severe", "Raised statin levels; risk of rhabdomyolysis."),
    ("trimethoprim", "methotrexate", "severe", "Bone marrow suppression."),
    ("doxycycline", "antacid", "minor", "Antacids reduce absorption; separate doses."),
    ("ibuprofen", "aspirin", "moderate", "Ibuprofen can reduce aspirin's antiplatelet effect."),
    ("codeine", "tramadol", "moderate", "Additive opioid effects and sedation."),
)

# The four patterns the CLI used to list as text, now real templates.
# Days: 1 = Monday … 6 = Saturday, 0 = Sunday (the provider_schedules convention).
DEFAULT_TEMPLATES = (
    ("Standard Full-Time (Mon-Fri 8AM-5PM)",
     '[{"day": 1, "start": "08:00", "end": "17:00"}, {"day": 2, "start": "08:00", "end": "17:00"}, '
     '{"day": 3, "start": "08:00", "end": "17:00"}, {"day": 4, "start": "08:00", "end": "17:00"}, '
     '{"day": 5, "start": "08:00", "end": "17:00"}]', 16),
    ("Part-Time Morning (Mon-Wed-Fri 8AM-12PM)",
     '[{"day": 1, "start": "08:00", "end": "12:00"}, {"day": 3, "start": "08:00", "end": "12:00"}, '
     '{"day": 5, "start": "08:00", "end": "12:00"}]', 8),
    ("Extended Hours (Tue-Thu 7AM-7PM)",
     '[{"day": 2, "start": "07:00", "end": "19:00"}, {"day": 3, "start": "07:00", "end": "19:00"}, '
     '{"day": 4, "start": "07:00", "end": "19:00"}]', 24),
    ("Weekend Coverage (Sat-Sun 9AM-3PM)",
     '[{"day": 6, "start": "09:00", "end": "15:00"}, {"day": 0, "start": "09:00", "end": "15:00"}]',
     12),
)


def _columns(execute, table) -> set:
    return {r[1] for r in execute(f'PRAGMA table_info("{table}")').fetchall()}


def apply(execute) -> None:
    for ddl in TABLES:
        execute(ddl)
    for table, column, decl in COLUMNS:
        existing = _columns(execute, table)
        if existing and column not in existing:
            execute(f'ALTER TABLE "{table}" ADD COLUMN "{column}" {decl}')
    for name, cls in DRUG_CLASSES:
        execute("INSERT OR IGNORE INTO drug_classes (drug_name, drug_class) VALUES (?, ?)",
                (name, cls))
    for a, b, note in CROSS_REACTIVITY:
        execute("INSERT OR IGNORE INTO drug_class_cross_reactivity (class_a, class_b, note) "
                "VALUES (?, ?, ?)", (a, b, note))
    for a, b, severity, text in INTERACTIONS:
        execute("INSERT OR IGNORE INTO drug_interactions (drug_a, drug_b, severity, description) "
                "VALUES (?, ?, ?, ?)", (a, b, severity, text))
    for name, pattern, max_appts in DEFAULT_TEMPLATES:
        execute("INSERT OR IGNORE INTO provider_schedule_templates (name, pattern_json, "
                "max_appointments, created_by) VALUES (?, ?, ?, 'system')",
                (name, pattern, max_appts))


_APPLIED: set[str] = set()


def apply_to_connection(conn) -> None:
    """:func:`apply` once per database file; inside an open transaction it
    applies without committing."""
    try:
        key = conn.execute("PRAGMA database_list").fetchone()[2]
    except Exception:
        key = None
    if key and key in _APPLIED:
        return
    busy = conn.in_transaction
    apply(conn.execute)
    if not busy:
        conn.commit()
        if key:
            _APPLIED.add(key)
