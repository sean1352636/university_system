"""Centralised DB extensions for the Disciplinary Portal + Academic
Misconduct Panel.

Single source of truth for the columns and triggers that bridge
``disciplinary_records`` and ``academic_misconduct_cases``. Both surfaces
import :func:`ensure_disciplinary_schema` and call it once on startup,
instead of each one running its own scattered ``ALTER TABLE … ADD
COLUMN`` statements.

The triggers replace the application-side mirror code that used to live
in both panels: an UPDATE on ``status`` in either store now propagates
to the other automatically (regardless of who/what wrote the row), with
a vocabulary-translation map and a guard against fire-back.
"""
from __future__ import annotations

import logging
import sqlite3

from education_system.university_system.modules.shared.constants.paths import (
    DEFAULT_DB_PATH,
)

logger = logging.getLogger(__name__)


# Idempotent column additions. Each tuple is (table, "col_name col_def").
# Run via ALTER TABLE … ADD COLUMN; duplicate-column errors are swallowed.
_EXTRA_COLUMNS = (
    # Portal exposes Location on the incident form; the shared schema
    # doesn't include it.
    ("disciplinary_records",      "location TEXT"),
    # Portal's add-student form exposed Year of Study; central schema
    # doesn't have an equivalent column.
    ("students",                  "year_of_study INTEGER"),
    # Back-link from a misconduct case to the disciplinary record it
    # was escalated from, so the two stores can cross-reference.
    ("academic_misconduct_cases", "source_record_id INTEGER"),
)


# Severity migration: normalise legacy values (lowercase + the old
# 4-level scale) to the unified 3-level vocabulary used everywhere now.
_SEVERITY_NORMALISATION = (
    ("minor",    "Minor"),
    ("moderate", "Minor"),
    ("Moderate", "Minor"),
    ("serious",  "Major"),
    ("Serious",  "Major"),
    ("severe",   "Critical"),
    ("Severe",   "Critical"),
    ("major",    "Major"),
    ("critical", "Critical"),
)


# Status translation maps. Single source of truth for the vocabulary
# bridge between the two stores; the trigger SQL is built from these
# at install time so a vocabulary change is a one-line edit here.
#
# Round-trip stability is required: for every key K, mapping the value
# back through the inverse map MUST yield K. Otherwise the cross-table
# trigger chain (disc → misc → disc) overwrites the user's original
# write, because SQLite's `recursive_triggers` pragma does NOT suppress
# cross-table cascades — only direct self-recursion. Triggers below
# additionally guard with ``status IN (map_keys)`` so unmapped values
# (portal-only Open/Closed/Escalated, etc.) don't propagate at all.
_PORTAL_TO_MISC = {
    'Under Review': 'Under Review',
    'Resolved':     'Resolved',
    'Appealed':     'Pending Hearing',
}
_MISC_TO_PORTAL = {
    'Under Review':    'Under Review',
    'Resolved':        'Resolved',
    'Pending Hearing': 'Appealed',
}


def _case_expr(mapping, source="NEW.status"):
    """Build a SQL CASE expression from a Python dict.

    Renders ``CASE <source> WHEN 'k1' THEN 'v1' … ELSE <source> END``.
    Used twice per trigger (once in SET, once in the WHERE guard); this
    helper makes that duplication mechanical rather than hand-edited.
    Values are SQL string literals — quotes inside keys/values would
    break the output, but the maps above don't contain any.
    """
    parts = ["CASE", source]
    for k, v in mapping.items():
        parts.append(f"WHEN '{k}' THEN '{v}'")
    parts.append(f"ELSE {source} END")
    return " ".join(parts)


def _in_list(mapping):
    """SQL ``('k1', 'k2', …)`` from a dict's keys."""
    return "(" + ", ".join(f"'{k}'" for k in mapping.keys()) + ")"


def ensure_disciplinary_schema(db_path=None) -> None:
    """Idempotent: add the bridge columns + status-sync triggers and
    normalise severities. Safe to call from any process at any time.

    Three steps, each isolated so a failure on one doesn't block the
    others (a fresh DB might have one of the parent tables missing
    on first run, etc.).
    """
    path = str(db_path or DEFAULT_DB_PATH)
    try:
        conn = sqlite3.connect(path)
    except sqlite3.Error:
        logger.exception("could not open %s for schema bootstrap", path)
        return
    try:
        _add_extra_columns(conn)
        _normalise_severity(conn)
        _install_status_sync_triggers(conn)
    finally:
        conn.close()


def _add_extra_columns(conn) -> None:
    for table, col_def in _EXTRA_COLUMNS:
        try:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col_def}")
            conn.commit()
        except sqlite3.OperationalError:
            # Column already exists, or parent table not yet created.
            pass


def _normalise_severity(conn) -> None:
    """One-shot UPDATE: collapse legacy severity values into the
    unified 3-level scale. Only touches rows that actually need it."""
    try:
        for old, new in _SEVERITY_NORMALISATION:
            if old == new:
                continue
            conn.execute(
                "UPDATE disciplinary_records SET severity = ? "
                "WHERE severity = ?", (new, old))
        conn.commit()
    except sqlite3.OperationalError:
        # Table missing on a fresh DB; harmless.
        pass


def _install_status_sync_triggers(conn) -> None:
    """Bidirectional status sync: a status UPDATE on either store fires
    a trigger that mirrors the new value (translated through the
    vocabulary map) onto the linked row in the other store.

    Guards against fire-back via ``WHERE status != <translated>`` —
    if the target already has the right value the UPDATE is a no-op
    and the second-level trigger doesn't fire.
    """
    portal_to_misc = _case_expr(_PORTAL_TO_MISC)
    misc_to_portal = _case_expr(_MISC_TO_PORTAL)
    portal_keys = _in_list(_PORTAL_TO_MISC)
    misc_keys = _in_list(_MISC_TO_PORTAL)
    # The IN-list filter on the WHEN clause keeps unmapped statuses
    # (portal-only Open/Closed/Escalated, etc.) from propagating into
    # the other store at all. Combined with round-trip-stable maps,
    # this means the cross-table chain always halts at depth 1.
    sync_to_misc = (
        f"CREATE TRIGGER IF NOT EXISTS sync_disc_status_to_misc "
        f"AFTER UPDATE OF status ON disciplinary_records "
        f"WHEN NEW.status IS NOT OLD.status "
        f"     AND NEW.status IN {portal_keys} "
        f"BEGIN "
        f"  UPDATE academic_misconduct_cases "
        f"     SET status = {portal_to_misc}, "
        f"         updated_at = CURRENT_TIMESTAMP "
        f"   WHERE source_record_id = NEW.record_id "
        f"     AND status != {portal_to_misc}; "
        f"END;"
    )
    sync_to_disc = (
        f"CREATE TRIGGER IF NOT EXISTS sync_misc_status_to_disc "
        f"AFTER UPDATE OF status ON academic_misconduct_cases "
        f"WHEN NEW.status IS NOT OLD.status "
        f"     AND NEW.source_record_id IS NOT NULL "
        f"     AND NEW.status IN {misc_keys} "
        f"BEGIN "
        f"  UPDATE disciplinary_records "
        f"     SET status = {misc_to_portal}, "
        f"         updated_at = CURRENT_TIMESTAMP "
        f"   WHERE record_id = NEW.source_record_id "
        f"     AND status != {misc_to_portal}; "
        f"END;"
    )
    # Drop any stale triggers from a previous install so the new
    # CASE bodies actually take effect (CREATE TRIGGER IF NOT EXISTS
    # would otherwise leave the old body in place).
    for stmt in ("DROP TRIGGER IF EXISTS sync_disc_status_to_misc",
                 "DROP TRIGGER IF EXISTS sync_misc_status_to_disc",
                 sync_to_misc, sync_to_disc):
        try:
            conn.execute(stmt)
            conn.commit()
        except sqlite3.OperationalError:
            # Either table missing — leave the trigger uninstalled.
            # Will install on the next call once both exist.
            pass
