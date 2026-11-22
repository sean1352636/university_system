"""university schema clean-up (2026-10-18 audit): redundant indexes,
duplicate tables merged into their canonical table, duplicate columns,
and the notification_actions FK to the removed notifications table

* Indexes that duplicate another index on exactly the same columns
  (including a UNIQUE constraint's autoindex) are dropped, each only while
  its twin exists; the code that recreated them was removed.
  ``ix_ed_people_deleted`` indexed ``ref_code`` (already UNIQUE) — replaced
  by ``ix_ed_people_deleted_at`` on the column the E&D reports filter on.
* Duplicate tables: ``assignment_groups`` / ``assignment_group_members`` →
  ``groups`` / ``group_members`` (member ids mapped from ``users.id`` to the
  student number; a value that is already a student number is kept);
  ``musicshop_wishlist`` → ``musicshop_wishlists``; ``student_trips`` →
  ``trips``. Each duplicate is dropped only after its rows were copied and
  counted. Empty, unreferenced leftovers of the old AI detector GUI and an
  unused ``submissions`` table are dropped only while empty.
* Duplicate columns: ``ai_detector_submissions`` keeps ``submission_text`` /
  ``title`` (``text_content`` / ``submission_title`` are copied across where
  the canonical column is empty and dropped only when nothing would be lost;
  the unused ``ai_score``, ``retry_count``, ``status`` are dropped only while
  entirely empty); ``permissions`` drops ``permission`` / ``role`` only while
  empty. Tables with both ``created_at`` and ``created_date`` (or
  ``updated_at`` and ``last_updated``) get ``created_at`` / ``updated_at``
  filled from the other where empty; the old column stays (some modules
  still write it).
* ``notification_actions`` is rebuilt without its FK while ``notifications``
  (removed by design) does not exist.

Runs after ``5e7a9c1d3f6b`` (column types): if that step rebuilt
``assignment_group_members`` with a text student number, the merge keeps it
as is; if it still holds ``users.id``, the merge maps it through ``users``.

Revision ID: 6f8b0d2e4a7c
Revises: 5e7a9c1d3f6b
Create Date: 2026-10-18 12:00:00.000000

Idempotent: every step checks what exists first, and every drop is guarded.
"""
from typing import Sequence, Union

from alembic import op


revision: str = '6f8b0d2e4a7c'
down_revision: Union[str, Sequence[str], None] = '5e7a9c1d3f6b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (table, redundant index) — dropped only while another index on exactly the
# same columns exists, so a lookup never loses its index.
_REDUNDANT_INDEXES = (
    ("academic_calendar_events", "idx_events_type"),
    ("academic_calendar_events", "idx_events_date"),
    ("assets", "idx_assets_tag"),
    ("betting_accounts", "idx_betting_accounts_user"),
    ("book_loans", "idx_book_loans_due_date"),
    ("book_loans", "idx_book_loans_status"),
    ("document_repository", "idx_doc_module"),
    ("ed_people", "ix_ed_people_deleted"),
    ("interest_matches", "idx_interest_matches_users"),
    ("mfa_trusted_devices", "idx_mfa_trusted_devices_token"),
    ("mfa_user_settings", "idx_mfa_user_settings_user"),
    ("public_profiles", "idx_public_profiles_url"),
    ("sabbatical_eligibility", "idx_sabbatical_eligibility_user"),
    ("security_incidents", "idx_inc_incident"),
    ("staff_profiles", "idx_staff_profiles_user"),
    ("student_finance_accounts", "idx_student_finance_accounts_student"),
    ("student_modules", "idx_modules_student"),
    ("student_modules", "idx_student_modules_student_module"),
    ("transactions", "idx_transactions_created"),
    ("transactions", "idx_transactions_student"),
    ("transactions", "idx_transactions_source"),
    ("ucas_offer_terms", "idx_ucas_terms_choice"),
)

# Empty, unreferenced tables to drop (only while empty).
_EMPTY_LEFTOVERS = (
    "ai_activity_log", "ai_alert_queue", "ai_assignment_profiles", "ai_model_versions",
    "ai_dean_escalations", "ai_violation_records", "ai_writing_fingerprints",
    "ai_student_flags", "ai_analysis_history", "ai_batch_jobs", "submissions",
)

_TIMESTAMP_PAIRS = (
    ("email_templates", "created_at", "created_date"),
    ("api_keys", "created_at", "created_date"),
    ("parent_notifications", "created_at", "created_date"),
    ("alumni_chapters", "created_at", "created_date"),
    ("search_profiles", "created_at", "created_date"),
    ("legal_cases", "created_at", "created_date"),
    ("legal_consultations", "created_at", "created_date"),
    ("carrental_vehicles", "created_at", "created_date"),
    ("carrental_rentals", "created_at", "created_date"),
    ("equipment_rentals", "created_at", "created_date"),
    ("products", "created_at", "created_date"),
    ("late_policies", "created_at", "created_date"),
    ("saved_searches", "created_at", "created_date"),
    ("financial_alerts", "created_at", "created_date"),
    ("security_policies", "updated_at", "last_updated"),
    ("data_privacy_settings", "updated_at", "last_updated"),
)


def _x():
    return op.get_bind().exec_driver_sql


def _table(name) -> bool:
    return _x()("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
                (name,)).fetchone() is not None


def _cols(table) -> list:
    return [r[1] for r in _x()(f'PRAGMA table_info("{table}")').fetchall()]


def _count(table) -> int:
    return _x()(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]  # nosec B608


def _index_cols(name) -> tuple:
    return tuple(r[2] for r in _x()(f'PRAGMA index_info("{name}")').fetchall())


# ── indexes ─────────────────────────────────────────────────────────────


def _drop_redundant_indexes() -> None:
    execute = _x()
    for table, name in _REDUNDANT_INDEXES:
        if not _table(table):
            continue
        indexes = [r[1] for r in execute(f'PRAGMA index_list("{table}")').fetchall()]
        if name not in indexes:
            continue
        mine = _index_cols(name)
        if mine and any(other != name and _index_cols(other) == mine for other in indexes):
            execute(f'DROP INDEX IF EXISTS "{name}"')
    if _table("ed_people") and "deleted_at" in _cols("ed_people"):
        execute("CREATE INDEX IF NOT EXISTS ix_ed_people_deleted_at ON ed_people(deleted_at)")


# ── duplicate tables ────────────────────────────────────────────────────


def _merge_groups() -> None:
    execute = _x()
    if not _table("groups") or not _table("group_members"):
        return
    if "description" not in _cols("groups"):
        execute("ALTER TABLE groups ADD COLUMN description TEXT")
    if not _table("assignment_groups"):
        if _table("assignment_group_members") and _count("assignment_group_members") == 0:
            execute("DROP TABLE assignment_group_members")
        return
    source_cols = set(_cols("assignment_groups"))
    created_by = "created_by" if "created_by" in source_cols else "NULL"
    description = "description" if "description" in source_cols else "NULL"
    has_members = _table("assignment_group_members")
    groups_copied = members_copied = members_total = 0
    groups_total = _count("assignment_groups")
    for gid, aid, name, desc, created, by in execute(
            f"SELECT id, assignment_id, group_name, {description}, created_at, {created_by} "  # nosec B608
            "FROM assignment_groups").fetchall():
        cur = execute("INSERT INTO groups (assignment_id, group_name, description, created_at, "
                      "created_by) VALUES (?, ?, ?, COALESCE(?, datetime('now')), ?)",
                      (aid, name, desc, created,
                       None if by is None or str(by).isdigit() else str(by)))
        groups_copied += 1
        if not has_members:
            continue
        new_id = cur.lastrowid
        for student, role, joined in execute(
                "SELECT COALESCE(u.student_id, CAST(m.student_id AS TEXT)), m.role, m.joined_at "
                "FROM assignment_group_members m LEFT JOIN users u ON u.id = m.student_id "
                "AND COALESCE(u.student_id, '') <> '' WHERE m.group_id = ?", (gid,)).fetchall():
            execute("INSERT INTO group_members (group_id, student_id, role, joined_at) "
                    "VALUES (?, ?, COALESCE(?, 'member'), COALESCE(?, datetime('now')))",
                    (new_id, student, role, joined))
            members_copied += 1
    if has_members:
        members_total = _count("assignment_group_members")
    # Drop only when every group and every member row was carried over.
    if groups_copied == groups_total and members_copied == members_total:
        if has_members:
            execute("DROP TABLE assignment_group_members")
        execute("DROP TABLE assignment_groups")


def _merge_wishlist() -> None:
    execute = _x()
    if not _table("musicshop_wishlist") or not _table("musicshop_wishlists"):
        return
    execute("INSERT OR IGNORE INTO musicshop_wishlists (customer_id, product_id, added_at) "
            "SELECT customer_name, product_id, added_date FROM musicshop_wishlist")
    missing = execute(
        "SELECT COUNT(*) FROM musicshop_wishlist w WHERE NOT EXISTS (SELECT 1 FROM "
        "musicshop_wishlists t WHERE t.customer_id = w.customer_name AND "
        "t.product_id = w.product_id)").fetchone()[0]
    if missing == 0:
        execute("DROP TABLE musicshop_wishlist")


def _merge_trips() -> None:
    execute = _x()
    if not _table("student_trips") or not _table("trips"):
        return
    from datetime import datetime

    trip_cols = set(_cols("trips"))
    source = execute("SELECT trip_name, destination, trip_date, cost, max_participants, "
                     "description, organizing_club FROM student_trips").fetchall()
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    copied = 0
    for name, dest, day, cost, cap, desc, club in source:
        text = ((f"Organised by {club}. " if club else "") + (desc or "")).strip()
        # end_date / created_at / updated_at are NOT NULL on trips; a
        # student trip is a single day. 'planning' is what the trips CHECK
        # allowed ('planned' would have failed the insert).
        columns = ["trip_name", "destination", "start_date", "cost", "max_participants",
                   "description"]
        values = [name, dest, day, cost, cap, text]
        for column, value in (("end_date", day), ("created_at", stamp), ("updated_at", stamp),
                              ("status", "planning")):
            if column in trip_cols:
                columns.append(column)
                values.append(value)
        execute(f"INSERT INTO trips ({', '.join(columns)}) "  # nosec B608
                f"VALUES ({', '.join('?' * len(values))})", tuple(values))
        copied += 1
    if copied == len(source):
        execute("DROP TABLE student_trips")


def _drop_empty_leftovers() -> None:
    execute = _x()
    for table in _EMPTY_LEFTOVERS:
        if _table(table) and _count(table) == 0:
            execute(f'DROP TABLE "{table}"')


# ── duplicate columns ───────────────────────────────────────────────────


def _drop_column(table, column) -> None:
    if column in _cols(table):
        try:
            _x()(f'ALTER TABLE "{table}" DROP COLUMN "{column}"')
        except Exception:
            # An index, trigger or view still uses it: leave it in place.
            pass


def _all_empty(table, column) -> bool:
    return _x()(f'SELECT 1 FROM "{table}" WHERE "{column}" IS NOT NULL '  # nosec B608
                f'AND CAST("{column}" AS TEXT) <> \'\' LIMIT 1').fetchone() is None


def _duplicate_columns() -> None:
    execute = _x()
    if _table("ai_detector_submissions"):
        cols = _cols("ai_detector_submissions")
        for old, keep in (("text_content", "submission_text"), ("submission_title", "title")):
            if old not in cols or keep not in cols:
                continue
            execute(f'UPDATE ai_detector_submissions SET "{keep}" = "{old}" WHERE '  # nosec B608
                    f'COALESCE("{keep}", \'\') = \'\' AND COALESCE("{old}", \'\') <> \'\'')
            lost = execute(f'SELECT 1 FROM ai_detector_submissions WHERE '  # nosec B608
                           f'COALESCE("{old}", \'\') <> \'\' AND "{old}" IS NOT "{keep}" '
                           'LIMIT 1').fetchone()
            if lost is None:
                _drop_column("ai_detector_submissions", old)
        for unused in ("ai_score", "retry_count", "status"):
            if unused in _cols("ai_detector_submissions") and \
                    _all_empty("ai_detector_submissions", unused):
                _drop_column("ai_detector_submissions", unused)
    if _table("permissions") and "permission_name" in _cols("permissions"):
        for column in ("permission", "role"):
            if column in _cols("permissions") and _all_empty("permissions", column):
                _drop_column("permissions", column)
    for table, keep, other in _TIMESTAMP_PAIRS:
        if _table(table) and {keep, other} <= set(_cols(table)):
            execute(f'UPDATE "{table}" SET "{keep}" = "{other}" WHERE "{keep}" IS NULL '  # nosec B608
                    f'AND "{other}" IS NOT NULL')


# ── notification_actions ────────────────────────────────────────────────


def _notification_actions() -> None:
    execute = _x()
    if not _table("notification_actions") or _table("notifications"):
        return
    if not any(r[2] == "notifications" for r in
               execute("PRAGMA foreign_key_list(notification_actions)").fetchall()):
        return
    before = _count("notification_actions")
    execute("DROP TABLE IF EXISTS notification_actions_rebuilt")
    execute("""CREATE TABLE notification_actions_rebuilt (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        notification_id INTEGER NOT NULL,
        action_text TEXT NOT NULL,
        action_url TEXT NOT NULL,
        action_type TEXT DEFAULT 'link',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    execute("INSERT INTO notification_actions_rebuilt (id, notification_id, action_text, "
            "action_url, action_type, created_at) SELECT id, notification_id, action_text, "
            "action_url, action_type, created_at FROM notification_actions")
    if _count("notification_actions_rebuilt") != before:
        execute("DROP TABLE notification_actions_rebuilt")
        return
    execute("DROP TABLE notification_actions")
    execute("ALTER TABLE notification_actions_rebuilt RENAME TO notification_actions")


def upgrade() -> None:
    _drop_redundant_indexes()
    _merge_groups()
    _merge_wishlist()
    _merge_trips()
    _drop_empty_leftovers()
    _duplicate_columns()
    _notification_actions()


def downgrade() -> None:
    # Nothing to restore. Merged rows live on in their canonical tables
    # (groups / group_members, musicshop_wishlists, trips); every dropped
    # table was empty or fully copied first; dropped columns held no data
    # that is not in the kept column; the dropped indexes each had a twin on
    # the same columns. Recreating the duplicates would reintroduce the
    # split the audit found.
    pass
