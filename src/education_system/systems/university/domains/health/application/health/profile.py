"""A student's health profile: one ``medical_info`` row per student.

Where each health fact lives (``infrastructure/health/health_schema``):

* **profile** — blood type, GP / doctor, insurance, a free-text summary of
  regular medications, conditions and allergies: ``medical_info`` (this
  module; also written by the sixth-form medical import);
* **allergies** (one row each, with severity — what the prescribing screen
  reads): ``allergies``; **conditions**: ``medical_conditions``;
  **prescriptions**: ``prescriptions``;
* **visits / clinical notes**: ``health_records``. Its ``blood_type`` /
  ``allergies`` / ``medications`` / ``conditions`` / ``insurance_*`` /
  ``last_updated`` columns are a retired second copy of the profile: nothing
  writes them, and migration ``a0d2f4b6c8e1`` moved any values into
  ``medical_info``;
* **emergency contacts**: ``emergency_contacts`` (``domain/health/services/contacts``).

Keyed on the student number (``students.student_id``), never ``users.id``.
Functions take an open connection; :func:`save` does not commit.
"""

from __future__ import annotations

from datetime import datetime

from education_system.systems.university.domains.health.application.health import access

FIELDS = ("blood_type", "allergies", "medications", "conditions", "doctor_name",
          "doctor_phone", "insurance_provider", "insurance_policy")


def get(conn, student_id) -> dict | None:
    """The student's profile (``FIELDS`` + ``last_updated``), or None."""
    row = conn.execute(
        f"SELECT {', '.join(FIELDS)}, last_updated FROM medical_info "  # nosec B608 - constants
        "WHERE student_id = ? ORDER BY id DESC LIMIT 1", (str(student_id),)).fetchone()
    if row is None:
        return None
    return dict(zip(FIELDS + ("last_updated",), tuple(row)))


def ensure_schema(conn) -> None:
    """The health tables (``infrastructure/health/health_schema``), once per
    database file — for callers outside the health portal."""
    from education_system.systems.university.domains.health.infrastructure.health import (
        health_schema,
    )
    health_schema.apply_to_connection(conn)


def upsert(conn, student_id, values: dict) -> None:
    """Write profile fields for a caller that has made its own permission
    check (the parent portal's update form, the sixth-form import): only the
    fields given; ``None``/blank clears one. One row per student — updated
    when there is one, else inserted. Does not commit."""
    unknown = set(values) - set(FIELDS)
    if unknown:
        raise ValueError(f"Not a health profile field: {', '.join(sorted(unknown))}")
    if not str(student_id or "").strip():
        raise ValueError("A student number is required")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    clean = {k: (str(v).strip() or None) if v is not None else None for k, v in values.items()}
    if conn.execute("SELECT 1 FROM medical_info WHERE student_id = ?",
                    (str(student_id),)).fetchone():
        if clean:
            sets = ", ".join(f"{k} = ?" for k in clean)
            conn.execute(f"UPDATE medical_info SET {sets}, last_updated = ? "  # nosec B608
                         "WHERE student_id = ?", (*clean.values(), now, str(student_id)))
    else:
        cols = ["student_id", *clean, "last_updated"]
        conn.execute(f"INSERT INTO medical_info ({', '.join(cols)}) "  # nosec B608 - FIELDS
                     f"VALUES ({', '.join('?' * len(cols))})",
                     (str(student_id), *clean.values(), now))


def save(conn, who, student_id, **values) -> None:
    """:func:`upsert` for the health team. Raises ``PermissionError`` /
    ``ValueError``. Does not commit."""
    access.require_clinician(who, "change a health profile")
    upsert(conn, student_id, values)


def blood_type_counts(conn) -> list[tuple[str, int]]:
    """``[(blood type, students)]`` across all profiles, most common first."""
    return [(r[0], r[1]) for r in conn.execute(
        "SELECT blood_type, COUNT(DISTINCT student_id) FROM medical_info "
        "WHERE blood_type IS NOT NULL AND blood_type <> '' GROUP BY blood_type "
        "ORDER BY 2 DESC, 1").fetchall()]
