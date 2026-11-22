"""Which health columns are sealed at rest, and the helpers that seal and
unseal them (``infrastructure/health/field_crypto``, one managed key).

Sealed: the free-text notes of counselling and mental-health contacts —
the most sensitive text the portal holds, never searched or aggregated —
the dental clinic's medical history, allergies and treatment notes, and the
description of a health record marked ``confidential``, a trip
participant's medical information, dietary requirements and accessibility
needs (Trip Management: ``trip_management/medical`` unseals and audits them),
and the text of a Student Support ticket in the restricted or safeguarding
confidentiality tier — its description and resolution and every reply on it
(:data:`TIERED`; ``student_support/confidentiality`` seals them, and reveals
them only after its access check).

Writers call :func:`seal_values` (or :func:`seal_value`) before INSERT /
UPDATE; readers call :func:`unseal_row` / :func:`unseal_rows` (or
:func:`reveal`) after SELECT. Values written before sealing are plain text
and pass through unchanged, so nothing old stops reading.

GUI code that writes these columns with its own SQL must use the same
helpers::

    from education_system.systems.university.domains.health.application.health import (
        sealed_fields,
    )
    description = sealed_fields.seal_value("health_records", "description", text,
                                           confidential=is_confidential)
    ...
    shown = sealed_fields.reveal(row["description"])
"""

from __future__ import annotations

from education_system.systems.university.domains.health.infrastructure.health import (
    field_crypto,
)

#: Always sealed.
SEALED: dict[str, tuple[str, ...]] = {
    "counseling_appointments": ("notes",),
    "counselling_sessions": ("notes", "outcome"),
    "wellness_checkins": ("notes",),
    "mental_health_checkins": ("notes",),
    "mental_health_appointments": ("notes",),
    "dentist_patients": ("medical_history", "allergies", "notes"),
    "dentist_treatments": ("notes", "procedure_notes"),
    # Special-category data a trip participant gives at registration (or
    # imports from their health profile with consent).
    "trip_participants": ("medical_info", "dietary_requirements", "accessibility_needs"),
    # What a student says about a disability (Disability & Accessibility).
    "student_disabilities": ("details",),
}
#: Sealed when the row's flag column is set.
CONDITIONAL: dict[str, tuple[str, str]] = {
    "health_records": ("description", "confidential"),
}

#: Sealed when the record they belong to is confidential — for a support
#: ticket, when its confidentiality tier is restricted or safeguarding. The
#: row carries no flag of its own (a reply's tier is its ticket's), so the
#: caller says: ``seal_value(table, column, text, confidential=True)``.
TIERED: dict[str, tuple[str, ...]] = {
    "support_tickets": ("description", "resolution"),
    "ticket_responses": ("response_text",),
    "ticket_replies": ("message",),
}

UNREADABLE = "[sealed — cannot be read with this key]"


def _truthy(value) -> bool:
    return str(value).strip().lower() in ("1", "true", "yes", "y", "t")


def is_sealed_column(table: str, column: str) -> bool:
    return (column in SEALED.get(table, ()) or CONDITIONAL.get(table, (None,))[0] == column
            or column in TIERED.get(table, ()))


def seal_value(table: str, column: str, value, *, confidential=None):
    """``value`` as it should be stored in ``table.column``."""
    if column in SEALED.get(table, ()):
        return field_crypto.seal(value)
    flagged = CONDITIONAL.get(table)
    if flagged and flagged[0] == column and _truthy(confidential):
        return field_crypto.seal(value)
    if column in TIERED.get(table, ()) and _truthy(confidential):
        return field_crypto.seal(value)
    return value


def seal_values(table: str, values: dict) -> dict:
    """A copy of ``values`` (column -> value) with the sealed columns sealed.
    For a conditional column the flag is read from ``values``."""
    out = dict(values)
    for column in SEALED.get(table, ()):
        if column in out:
            out[column] = field_crypto.seal(out[column])
    flagged = CONDITIONAL.get(table)
    if flagged and flagged[0] in out and _truthy(out.get(flagged[1])):
        out[flagged[0]] = field_crypto.seal(out[flagged[0]])
    return out


def reveal(value):
    """The readable text of a stored value (plain text passes through; a
    value this key can't open is shown as :data:`UNREADABLE`, never as
    ciphertext)."""
    try:
        return field_crypto.unseal(value)
    except ValueError:
        return UNREADABLE


def unseal_row(row, columns=None):
    """A dict copy of ``row`` with every sealed value revealed. ``row`` may
    be a dict, a ``sqlite3.Row`` or a tuple (then pass ``columns``)."""
    if row is None:
        return None
    if isinstance(row, dict):
        data = dict(row)
    elif hasattr(row, "keys"):
        data = {k: row[k] for k in row.keys()}
    else:
        data = dict(zip(columns or (), row))
    for key, value in data.items():
        if field_crypto.is_sealed(value):
            data[key] = reveal(value)
    return data


def unseal_rows(rows, columns=None) -> list[dict]:
    return [unseal_row(r, columns) for r in rows]


def seal_existing(execute) -> dict:
    """Seal every plain value of the sealed columns (used by the migration;
    idempotent — sealed values are skipped). Returns counts per column."""
    counts: dict[str, int] = {}

    def columns_of(table):
        return {r[1] for r in execute(f'PRAGMA table_info("{table}")').fetchall()}

    for table, sealed in SEALED.items():
        cols = columns_of(table)
        for column in sealed:
            if column not in cols:
                continue
            n = 0
            for rid, value in execute(
                    f'SELECT rowid, "{column}" FROM "{table}" WHERE "{column}" IS NOT NULL '  # nosec B608
                    f'AND "{column}" <> \'\' AND "{column}" NOT LIKE \'enc1:%\'').fetchall():
                execute(f'UPDATE "{table}" SET "{column}" = ? WHERE rowid = ?',  # nosec B608
                        (field_crypto.seal(value), rid))
                n += 1
            counts[f"{table}.{column}"] = n
    for table, (column, flag) in CONDITIONAL.items():
        cols = columns_of(table)
        if not {column, flag} <= cols:
            continue
        n = 0
        for rid, value, conf in execute(
                f'SELECT rowid, "{column}", "{flag}" FROM "{table}" WHERE "{column}" IS NOT NULL '  # nosec B608
                f'AND "{column}" <> \'\' AND "{column}" NOT LIKE \'enc1:%\'').fetchall():
            if _truthy(conf):
                execute(f'UPDATE "{table}" SET "{column}" = ? WHERE rowid = ?',  # nosec B608
                        (field_crypto.seal(value), rid))
                n += 1
        counts[f"{table}.{column}"] = n
    return counts
