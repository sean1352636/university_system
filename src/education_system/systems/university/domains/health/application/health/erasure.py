"""The health part of erasing a student (``application/students/erasure``).

The generic erasure pass removes every row with a ``student_id`` column
(health records, counselling, check-ins, ``privacy_consent`` …, sealed
fields with them). This covers the health rows keyed on something else:

* ``dentist_patients`` - keyed on the student's university login
  (``user_id`` / ``user_email``); the patient and its appointments,
  treatments, prescriptions and records are deleted;
* ``first_aid_incidents`` - the incident stays (a health & safety record)
  but the reporter's identity (login, name, id, phone, e-mail) is cleared;
* ``first_aid_training_registrations`` - deleted;
* ``ed_consent`` - consent flags held under the student's id or login.

:func:`identities` must be read before the student's logins are removed.
Functions take an open connection and do not commit.
"""

from __future__ import annotations


def _has(conn, table) -> bool:
    return bool(conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
                             (table,)).fetchone())


def _cols(conn, table) -> set:
    return {r[1] for r in conn.execute(f'PRAGMA table_info("{table}")').fetchall()}


def identities(conn, student_id) -> dict:
    """The student's ids, logins and e-mail addresses, as health tables hold
    them."""
    ids = {str(student_id)}
    user_ids: set[str] = set()
    usernames = {str(student_id)}
    emails: set[str] = set()
    if _has(conn, "students"):
        cols = _cols(conn, "students")
        for col in ("email_address", "personal_email", "email"):
            if col in cols:
                row = conn.execute(f'SELECT "{col}" FROM students WHERE student_id = ?',
                                   (student_id,)).fetchone()
                if row and row[0]:
                    emails.add(str(row[0]).lower())
    if _has(conn, "users"):
        cols = _cols(conn, "users")
        email = "email" if "email" in cols else "NULL"
        for uid, username, mail in conn.execute(
                f"SELECT id, username, {email} FROM users WHERE student_id = ? OR username = ?",  # nosec B608
                (student_id, student_id)).fetchall():
            ids.add(str(uid))
            user_ids.add(str(uid))
            usernames.add(str(username))
            if mail:
                emails.add(str(mail).lower())
    return {"student_id": str(student_id), "ids": sorted(ids), "user_ids": sorted(user_ids),
            "usernames": sorted(usernames),
            "emails": sorted(emails)}


def _in(values) -> tuple[str, tuple]:
    values = tuple(values) or ("",)
    return ",".join("?" * len(values)), values


def _patients(conn, who) -> list:
    if not _has(conn, "dentist_patients"):
        return []
    cols = _cols(conn, "dentist_patients")
    clauses, args = [], []
    if "user_id" in cols:
        marks, vals = _in(who["user_ids"])
        clauses.append(f"CAST(user_id AS TEXT) IN ({marks})")
        args += vals
    if "user_email" in cols and who["emails"]:
        marks, vals = _in(who["emails"])
        clauses.append(f"LOWER(user_email) IN ({marks})")
        args += vals
    if not clauses:
        return []
    return [r[0] for r in conn.execute(
        f"SELECT patient_id FROM dentist_patients WHERE {' OR '.join(clauses)}",  # nosec B608
        args).fetchall()]


def _incidents_where(conn, who):
    cols = _cols(conn, "first_aid_incidents")
    clauses, args = [], []
    for col, values in (("reporter_user", who["usernames"]), ("reporter_id", who["ids"])):
        if col in cols:
            marks, vals = _in(values)
            clauses.append(f'CAST("{col}" AS TEXT) IN ({marks})')
            args += vals
    if "email" in cols and who["emails"]:
        marks, vals = _in(who["emails"])
        clauses.append(f"LOWER(email) IN ({marks})")
        args += vals
    return " OR ".join(clauses), args


def impact(conn, who) -> dict[str, dict]:
    out = {}
    patients = _patients(conn, who)
    if patients:
        out["dentist_patients.user_id"] = {"rows": len(patients), "fate": "removed"}
    if _has(conn, "first_aid_incidents"):
        where, args = _incidents_where(conn, who)
        if where:
            n = conn.execute(f"SELECT COUNT(*) FROM first_aid_incidents WHERE {where}",  # nosec B608
                             args).fetchone()[0]
            if n:
                out["first_aid_incidents.reporter"] = {"rows": n,
                                                       "fate": "reporter identity cleared"}
    if _has(conn, "first_aid_training_registrations"):
        marks, vals = _in(who["user_ids"] + who["usernames"])
        n = conn.execute("SELECT COUNT(*) FROM first_aid_training_registrations WHERE "  # nosec B608
                         f"CAST(user_id AS TEXT) IN ({marks})", vals).fetchone()[0]
        if n:
            out["first_aid_training_registrations.user_id"] = {"rows": n, "fate": "removed"}
    if _has(conn, "ed_consent"):
        marks, vals = _in(who["ids"] + who["usernames"])
        n = conn.execute(f"SELECT COUNT(*) FROM ed_consent WHERE CAST(person_id AS TEXT) "  # nosec B608
                         f"IN ({marks})", vals).fetchone()[0]
        if n:
            out["ed_consent.person_id"] = {"rows": n, "fate": "removed"}
    return out


def erase(conn, who, delete_rows) -> dict:
    """Erase the health rows above. ``delete_rows(conn, table, where, args)``
    is the erasure's dependent-first delete."""
    done: dict[str, int] = {}
    patients = _patients(conn, who)
    if patients:
        marks, vals = _in(str(p) for p in patients)
        if _has(conn, "dentist_appointments"):
            delete_rows(conn, "dentist_appointments",
                        f"CAST(patient_id AS TEXT) IN ({marks})", vals)
        delete_rows(conn, "dentist_patients", f"CAST(patient_id AS TEXT) IN ({marks})", vals)
        done["dentist_patients"] = len(patients)
    if _has(conn, "first_aid_incidents"):
        where, args = _incidents_where(conn, who)
        if where:
            cols = _cols(conn, "first_aid_incidents")
            sets = [f'"{c}" = NULL' for c in ("reporter_user", "reporter_id", "phone", "email")
                    if c in cols]
            if "reporter_name" in cols:
                sets.append("reporter_name = 'Erased'")
            if sets:
                cur = conn.execute(f"UPDATE first_aid_incidents SET {', '.join(sets)} "  # nosec B608
                                   f"WHERE {where}", args)
                done["first_aid_incidents"] = cur.rowcount
    marks, vals = _in(who["user_ids"] + who["usernames"])
    if _has(conn, "first_aid_training_registrations"):
        cur = conn.execute("DELETE FROM first_aid_training_registrations WHERE "  # nosec B608
                           f"CAST(user_id AS TEXT) IN ({marks})", vals)
        done["first_aid_training_registrations"] = cur.rowcount
    if _has(conn, "ed_consent"):
        marks, vals = _in(who["ids"] + who["usernames"])
        cur = conn.execute(f"DELETE FROM ed_consent WHERE CAST(person_id AS TEXT) "  # nosec B608
                           f"IN ({marks})", vals)
        done["ed_consent"] = cur.rowcount
    return done


#: Shared with the subject access export (same matching rules).
patients = _patients
incidents_where = _incidents_where

__all__ = ["identities", "impact", "erase", "patients", "incidents_where"]
