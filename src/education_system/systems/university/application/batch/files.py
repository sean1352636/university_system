"""Reading batch files and mapping their columns.

* :func:`read_table` reads CSV, Excel (.xlsx, needs openpyxl; any sheet,
  see :func:`sheet_names`) or JSON (a list of objects) into header names
  and row dicts.
* Each import kind has canonical columns (:data:`COLUMNS`); a file's
  headers are matched to them by :func:`auto_mapping` (case, spaces and
  common aliases ignored) or by a saved mapping (per user, optionally
  shared).
* :func:`write_template` writes a header row and one example row.

Functions taking a connection do not commit; the caller does.
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path

from education_system.systems.university.infrastructure.database.schemas import (
    batch_jobs_schema as schema,
)

#: kind -> (canonical column, required?, example value)
COLUMNS = {
    "students": (
        ("student_id", False, ""), ("first_name", True, "Ana"), ("middle_name", False, ""),
        ("last_name", True, "López"), ("dob", True, "2005-04-12"), ("gender", False, "female"),
        ("title", False, "Ms"), ("course", True, "CS"), ("entry_route", False, "a_levels"),
        ("entry_qualifications", False, "A*AB"), ("ucas_tariff", False, "144"),
        ("phone", False, "07700 900123"), ("personal_email", False, "ana@example.com"),
        ("address", False, "1 High Street"), ("nationality", False, "Spanish"),
        ("mode_of_study", False, "full-time"), ("fee_status", False, "home"),
        ("pronouns", False, ""), ("emergency_contact", False, ""),
    ),
    "marks": (
        ("student_id", True, "1234567"), ("assessment_id", False, "12"),
        ("module_code", False, "CS101"), ("assessment", False, "Final exam"),
        ("score", False, "64"), ("percentage", False, ""), ("comments", False, ""),
    ),
    "staff": (
        ("username", True, "jsmith"), ("first_name", True, "Jo"), ("last_name", True, "Smith"),
        ("email", True, "j.smith@uni.ac.uk"), ("role", False, "staff"),
        ("teaches", False, "yes"), ("department", False, "Computing"),
    ),
    "actions": (("student_id", True, "1234567"),),
    "enrolments": (
        ("student_id", True, "1234567"), ("module_code", True, "CS101"),
        ("action", False, "enrol"),
    ),
}
ALIASES = {
    "student_id": ("id", "student", "student_number", "studentno", "student_no"),
    "first_name": ("forename", "firstname", "given_name"),
    "last_name": ("surname", "lastname", "family_name"),
    "middle_name": ("middlename", "middle_names"),
    "dob": ("date_of_birth", "birth_date", "birthdate", "dateofbirth"),
    "course": ("programme", "program", "course_code", "programme_code"),
    "personal_email": ("email", "email_address", "personal_email_address"),
    "phone": ("telephone", "mobile", "phone_number"),
    "address": ("home_address",),
    "mode_of_study": ("mode", "study_mode"),
    "fee_status": ("fees", "fee"),
    "ucas_tariff": ("tariff", "ucas_points"),
    "entry_qualifications": ("qualifications",),
    "assessment": ("assessment_name", "assessment_title"),
    "score": ("mark", "points", "raw_mark"),
    "percentage": ("percent", "pct"),
    "username": ("user", "login"),
    "module_code": ("module", "module_id", "unit_code"),
    "action": ("operation", "enrol_or_withdraw"),
}
MAX_ROWS = 5000


def _norm(text) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(text or "").strip().lower()).strip("_")


def sheet_names(path) -> list[str]:
    """The sheets of an Excel workbook (empty for other files)."""
    if Path(path).suffix.lower() not in (".xlsx", ".xlsm"):
        return []
    try:
        from openpyxl import load_workbook
    except ImportError:
        raise ValueError("Reading .xlsx needs openpyxl; save the sheet as CSV instead") from None
    book = load_workbook(path, read_only=True)
    try:
        return list(book.sheetnames)
    finally:
        book.close()


def read_table(path, sheet=None) -> tuple[list[str], list[dict]]:
    """``(headers, rows)``; every value is a stripped string. ``sheet``
    picks an Excel sheet by name (default: the active one)."""
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, list) or not all(isinstance(r, dict) for r in data):
            raise ValueError("A JSON import must be a list of objects")
        headers = list(dict.fromkeys(k for r in data for k in r))
        rows = data
    elif suffix in (".xlsx", ".xlsm"):
        rows, headers = _read_xlsx(path, sheet)
    elif suffix in (".csv", ".txt"):
        with path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            headers = list(reader.fieldnames or [])
            rows = list(reader)
    else:
        raise ValueError("Use a .csv, .xlsx or .json file")
    if len(rows) > MAX_ROWS:
        raise ValueError(f"At most {MAX_ROWS} rows per file")
    clean = [{h: ("" if r.get(h) is None else str(r.get(h)).strip()) for h in headers}
             for r in rows]
    return headers, [r for r in clean if any(r.values())]


def _read_xlsx(path, sheet_name=None):
    try:
        from openpyxl import load_workbook
    except ImportError:
        raise ValueError("Reading .xlsx needs openpyxl; save the sheet as CSV instead") from None
    book = load_workbook(path, read_only=True, data_only=True)
    if sheet_name:
        if sheet_name not in book.sheetnames:
            raise ValueError(f"No sheet called {sheet_name!r} in {Path(path).name}")
        sheet = book[sheet_name]
    else:
        sheet = book.active
    values = list(sheet.iter_rows(values_only=True))
    if not values:
        return [], []
    headers = [str(h or "").strip() for h in values[0]]
    rows = [dict(zip(headers, r)) for r in values[1:]]
    for r in rows:
        for k, v in r.items():
            if hasattr(v, "date") and callable(v.date):
                r[k] = v.date().isoformat()      # Excel dates
    return rows, headers


def auto_mapping(kind, headers) -> dict:
    """``{canonical column: file header}`` for every column it can match."""
    by_norm = {_norm(h): h for h in headers}
    mapping = {}
    for column, _required, _example in COLUMNS[kind]:
        for candidate in (column,) + ALIASES.get(column, ()):
            if candidate in by_norm and by_norm[candidate] not in mapping.values():
                mapping[column] = by_norm[candidate]
                break
    return mapping


def missing_required(kind, mapping, mode=None) -> list[str]:
    """Required columns the mapping lacks. Updating students needs only
    ``student_id`` (the file supplies whichever fields change)."""
    if kind == "students" and mode == "update":
        return [] if "student_id" in mapping else ["student_id"]
    return [c for c, required, _e in COLUMNS[kind] if required and c not in mapping]


def apply_mapping(rows, mapping) -> list[dict]:
    """Rows keyed by canonical column (unmapped columns dropped; blank
    cells omitted so they never overwrite anything)."""
    out = []
    for row in rows:
        out.append({column: row.get(header, "").strip() for column, header in mapping.items()
                    if row.get(header, "").strip()})
    return out


def write_template(kind, path) -> str:
    columns = COLUMNS[kind]
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow([c for c, _r, _e in columns])
        writer.writerow([e for _c, _r, e in columns])
    return str(path)


# ── saved mappings ──────────────────────────────────────────────────────


def save_mapping(conn, owner, kind, name, mapping, shared=False) -> int:
    if kind not in ("students", "marks", "staff"):
        raise ValueError("Mappings can be saved for students, marks and staff files")
    schema.apply_to_connection(conn)
    if not (name or "").strip():
        raise ValueError("Give the mapping a name")
    unknown = set(mapping) - {c for c, _r, _e in COLUMNS[kind]}
    if unknown:
        raise ValueError(f"Unknown columns: {', '.join(sorted(unknown))}")
    conn.execute("INSERT INTO batch_import_mappings (owner, kind, name, mapping_json, shared) "
                 "VALUES (?, ?, ?, ?, ?) ON CONFLICT (owner, kind, name) DO UPDATE SET "
                 "mapping_json = excluded.mapping_json, shared = excluded.shared, "
                 "updated_at = datetime('now')",
                 (owner, kind, name.strip(), json.dumps(mapping), int(bool(shared))))
    return conn.execute("SELECT id FROM batch_import_mappings WHERE owner = ? AND kind = ? AND "
                        "name = ?", (owner, kind, name.strip())).fetchone()[0]


def mappings(conn, owner, kind) -> list[dict]:
    schema.apply_to_connection(conn)
    rows = conn.execute("SELECT id, owner, name, mapping_json, shared FROM batch_import_mappings "
                        "WHERE kind = ? AND (owner = ? OR shared = 1) ORDER BY name",
                        (kind, owner)).fetchall()
    return [{"id": r[0], "owner": r[1], "name": r[2], "mapping": json.loads(r[3]),
             "shared": bool(r[4])} for r in rows]


def mapping(conn, mapping_id) -> dict:
    schema.apply_to_connection(conn)
    row = conn.execute("SELECT mapping_json FROM batch_import_mappings WHERE id = ?",
                       (mapping_id,)).fetchone()
    if not row:
        raise ValueError("No such saved mapping")
    return json.loads(row[0])


def delete_mapping(conn, owner, mapping_id, admin=False):
    schema.apply_to_connection(conn)
    row = conn.execute("SELECT owner FROM batch_import_mappings WHERE id = ?",
                       (mapping_id,)).fetchone()
    if not row:
        raise ValueError("No such saved mapping")
    if row[0] != owner and not admin:
        raise ValueError("Only its owner can delete this mapping")
    conn.execute("DELETE FROM batch_import_mappings WHERE id = ?", (mapping_id,))
