"""The health section of a subject access request (SAR) disclosure.

Everything the health service holds about the student, with sealed fields
unsealed so the student can read them. Left out, and listed in
``withheld`` so the officer can review them before release:

* **internal notes** - clinicians' and counsellors' working notes
  (appointment / session notes, dental notes). Under the DPA 2018 health
  data exemption these go out only after an appropriate health
  professional has confirmed disclosure won't cause serious harm;
* **third-party data** - emergency contacts' details, and first-aid
  incident descriptions (which may name other people);
* internal columns (``encrypted_data``, conflict flags, anonymous codes).
"""

from __future__ import annotations

from education_system.systems.university.domains.health.application.health import (
    consent,
    erasure,
    sealed_fields,
)

#: table -> (key column, columns withheld as internal notes)
STUDENT_TABLES: dict[str, tuple[str, tuple[str, ...]]] = {
    "health_records": ("student_id", ()),
    "vaccination_records": ("student_id", ()),
    "health_appointments": ("student_id", ("notes",)),
    "medical_conditions": ("student_id", ("notes",)),
    "allergies": ("student_id", ()),
    "prescriptions": ("student_id", ("notes",)),
    "lab_results": ("student_id", ()),
    "vital_signs": ("student_id", ("notes",)),
    "counseling_appointments": ("student_id", ("notes",)),
    "counselling_sessions": ("student_id", ("notes", "outcome")),
    "mental_health_appointments": ("student_id", ("notes",)),
    "wellness_checkins": ("student_id", ()),        # the student's own words
    "mental_health_checkins": ("student_id", ()),
    "medical_accommodations": ("student_id", ("internal_notes", "notes")),
}
#: Never disclosed: implementation detail, not information about the student.
INTERNAL_COLUMNS = {"encrypted_data", "has_conflict", "anonymous_code"}
#: Withheld as third-party data.
THIRD_PARTY_TABLES = ("emergency_contacts",)


def _has(conn, table) -> bool:
    return bool(conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
                             (table,)).fetchone())


def _rows(conn, sql, args) -> list[dict]:
    cur = conn.execute(sql, args)
    names = [d[0] for d in cur.description]
    return [dict(zip(names, tuple(r))) for r in cur.fetchall()]


def _clean(rows, drop, table, withheld) -> list[dict]:
    out = []
    for row in rows:
        data = sealed_fields.unseal_row(row)
        for col in list(data):
            if col in INTERNAL_COLUMNS:
                data.pop(col)
            elif col in drop:
                if data.pop(col) not in (None, ""):
                    withheld[f"{table}.{col}"] = withheld.get(f"{table}.{col}", 0) + 1
        out.append(data)
    return out


def _student_rows(conn, student_id, records, withheld) -> None:
    for table, (key, drop) in STUDENT_TABLES.items():
        if not _has(conn, table):
            continue
        if key not in {r[1] for r in conn.execute(f'PRAGMA table_info("{table}")')}:
            continue
        rows = _rows(conn, f'SELECT * FROM "{table}" WHERE "{key}" = ?',  # nosec B608
                     (str(student_id),))
        if rows:
            records[table] = _clean(rows, set(drop), table, withheld)


def _third_party(conn, student_id, withheld) -> None:
    for table in THIRD_PARTY_TABLES:
        if _has(conn, table):
            n = conn.execute(f'SELECT COUNT(*) FROM "{table}" WHERE student_id = ?',  # nosec B608
                             (str(student_id),)).fetchone()[0]
            if n:
                withheld[f"{table} (third-party contact details)"] = n


def _dental(conn, who, records, withheld) -> None:
    """Dental clinic rows, keyed on the student's login."""
    patients = erasure.patients(conn, who)
    if not patients:
        return
    marks = ",".join("?" * len(patients))
    args = tuple(str(p) for p in patients)
    records["dentist_patients"] = _clean(_rows(
        conn, f"SELECT * FROM dentist_patients WHERE CAST(patient_id AS TEXT) IN ({marks})",  # nosec B608
        args), {"notes"}, "dentist_patients", withheld)
    for table, drop in (("dentist_appointments", {"notes"}),
                        ("dentist_treatments", {"notes", "procedure_notes"}),
                        ("dentist_prescriptions", set()),
                        ("dentist_records", set())):
        if _has(conn, table):
            rows = _rows(conn, f"SELECT * FROM {table} WHERE "  # nosec B608
                         f"CAST(patient_id AS TEXT) IN ({marks})", args)
            if rows:
                records[table] = _clean(rows, drop, table, withheld)


def _first_aid(conn, who, records, withheld) -> None:
    """First-aid incidents the student reported (descriptions may name others)."""
    if not _has(conn, "first_aid_incidents"):
        return
    where, args = erasure.incidents_where(conn, who)
    if not where:
        return
    rows = _rows(conn, f"SELECT * FROM first_aid_incidents WHERE {where}", args)  # nosec B608
    if rows:
        records["first_aid_incidents"] = _clean(
            rows, {"description"}, "first_aid_incidents (third-party)", withheld)


def health_section(conn, student_id) -> dict:
    """``{"records": {table: [rows]}, "withheld": {what: count}, "consent": [...]}``"""
    records: dict[str, list] = {}
    withheld: dict[str, int] = {}
    _student_rows(conn, student_id, records, withheld)
    _third_party(conn, student_id, withheld)
    who = erasure.identities(conn, student_id)
    _dental(conn, who, records, withheld)
    _first_aid(conn, who, records, withheld)
    try:
        consents = consent.consent_history(student_id, conn=conn)
    except Exception:
        consents = []
    return {"student_id": str(student_id), "records": records, "withheld": withheld,
            "consent": consents}


__all__ = ["STUDENT_TABLES", "health_section"]
