"""UCAS applicant files in, decision files out.

UCAS only shows this system our own sixth form's applicants (through the
sixth form's adapter, ``domains/admissions/domain/ucas``). Everyone else who
applies through UCAS reaches us as a file the admissions team downloads
from UCAS (the applicant data export / ABL download). :func:`import_file`
reads that file:

* **CSV** with a header row, or **XML** where each applicant is an element
  whose children carry the same field names. The column names accepted
  (case and spacing ignored) are listed in :data:`FIELDS`; ``personal_id``
  (the 10-digit UCAS Personal ID, dashes allowed), ``course_code`` and
  ``entry_year`` are required. If your UCAS export names a column
  differently, rename the header before importing - nothing is guessed.
* Each row adopts the admissions application already held under that
  Personal ID for that course (``admission_applications.external_reference``,
  the convention the sixth-form handover and UCAS offers already use) or
  opens one through the admissions CRM, and is recorded in
  ``ucas_import_records``. When the applicant is one of our sixth formers
  with a UCAS choice for the same course, the choice's
  ``ucas_application_links`` row is created / attached too.

Decisions: each recorded decision on a UCAS application is already fed per
event to the ``ucas`` connector (``connector_feeds``,
``admissions.decision.recorded``). :func:`export_decisions` also writes a
batch file of every decision not yet in a batch, with the UCAS decision
codes C (conditional offer), U (unconditional offer), R (reject) and W
(withdrawn), for upload to UCAS. A decision that does not say which kind of
offer it is ("offer", "accept") is listed as needing a C or U, not sent.
"""

from __future__ import annotations

import csv
import io
import logging
import re

from education_system.systems.university.application import connectors
from education_system.systems.university.application.statutory import access as sa

logger = logging.getLogger(__name__)

CONNECTOR = "ucas"

#: our field -> header names accepted (normalised: lower case, letters/digits only).
FIELDS: dict[str, tuple[str, ...]] = {
    "personal_id": ("personalid", "ucaspersonalid", "applicantpersonalid", "ucasid"),
    "scheme": ("scheme", "schemecode", "applicationscheme"),
    "choice_number": ("choicenumber", "choiceno", "choice"),
    "course_code": ("coursecode", "course", "ucascoursecode"),
    "campus_code": ("campuscode", "campus"),
    "entry_year": ("entryyear", "yearofentry", "startyear"),
    "point_of_entry": ("pointofentry", "entrypoint"),
    "title": ("title",),
    "forenames": ("forenames", "forename", "firstname", "givennames"),
    "surname": ("surname", "lastname", "familyname"),
    "date_of_birth": ("dateofbirth", "dob", "birthdate"),
    "email": ("email", "emailaddress"),
    "ucas_status": ("status", "applicationstatus"),
    "decision": ("decision", "decisioncode"),
}
REQUIRED = ("personal_id", "course_code", "entry_year")
DECISION_CODES = {"C": "Conditional offer", "U": "Unconditional offer", "R": "Reject",
                  "W": "Withdrawn"}
_DECISION_WORDS = {
    "c": "C", "conditional": "C", "conditional offer": "C",
    "u": "U", "unconditional": "U", "unconditional offer": "U",
    "r": "R", "reject": "R", "rejected": "R", "rejection": "R", "denied": "R",
    "unsuccessful": "R", "w": "W", "withdrawn": "W", "withdraw": "W",
}
_PID = re.compile(r"^\d{10}$")


def _norm(name) -> str:
    return re.sub(r"[^a-z0-9]", "", str(name or "").lower())


_ALIASES = {alias: field for field, names in FIELDS.items() for alias in names}


def personal_id(value) -> str | None:
    digits = re.sub(r"[\s-]", "", str(value or ""))
    return digits if _PID.match(digits) else None


def decision_code(decision) -> str | None:
    return _DECISION_WORDS.get(str(decision or "").strip().lower())


def _map_row(raw: dict) -> dict:
    out = {}
    for key, value in raw.items():
        field = _ALIASES.get(_norm(key))
        if field and value not in (None, ""):
            out[field] = str(value).strip()
    return out


def parse(text: str, file_format: str = "csv") -> list[dict]:
    """Rows as ``{field: value}`` using :data:`FIELDS`."""
    if file_format == "xml":
        # Parses a file the admissions team chose to import: use defusedxml.
        from defusedxml import ElementTree as SafeET

        root = SafeET.fromstring(text)
        return [_map_row({child.tag: (child.text or "") for child in elem})
                for elem in root if len(elem)]
    reader = csv.DictReader(io.StringIO(text.lstrip("﻿")))
    return [_map_row(row) for row in reader]


def _check(row) -> str | None:
    missing = [f for f in REQUIRED if not row.get(f)]
    if missing:
        return "missing " + ", ".join(missing)
    if not personal_id(row["personal_id"]):
        return f"Personal ID {row['personal_id']!r} is not 10 digits"
    if not re.match(r"^\d{4}$", row["entry_year"]):
        return f"Entry year {row['entry_year']!r} is not a year"
    return None


def _open_application(row, pid) -> tuple[int, bool]:
    """The application for this Personal ID: adopted, or opened via the CRM."""
    from education_system.systems.university.domains.admissions.domain.services.admissions_crm_core import (  # noqa: E501
        ApplicationManager,
        ProspectManager,
    )
    with sa.session() as conn:
        existing = conn.execute(
            "SELECT application_id FROM admission_applications WHERE external_reference = ? "
            "AND (UPPER(program_applied) = ? OR application_id IN (SELECT application_id FROM "
            "ucas_import_records WHERE personal_id = ? AND course_code = ?)) "
            "ORDER BY application_id DESC LIMIT 1",
            (pid, row["course_code"].upper(), pid, row["course_code"].upper())).fetchone()
    if existing:
        return int(existing[0]), False
    prospect_id = ProspectManager.create_prospect(
        first_name=row.get("forenames", ""), last_name=row.get("surname", ""),
        email=row.get("email", ""), date_of_birth=row.get("date_of_birth", ""),
        intended_major=row["course_code"], source="ucas")
    application_id = ApplicationManager.submit_application(
        prospect_id=prospect_id, application_type="undergraduate",
        program_applied=row["course_code"], academic_year=row["entry_year"],
        semester="Autumn")
    with sa.session() as conn:
        conn.execute("UPDATE admission_applications SET external_reference = ? "
                     "WHERE application_id = ?", (pid, application_id))
    return int(application_id), True


def _sixth_form_choices() -> dict:
    """``{(personal id, course code): applicant}`` for our sixth formers'
    UCAS choices naming this university (empty if the sixth form is not
    reachable)."""
    try:
        from education_system.systems.university.domains.admissions.domain.ucas import ucas
        applicants = ucas.list_applicants(include_placed=True)
    except Exception:
        logger.debug("Sixth form UCAS choices unavailable", exc_info=True)
        return {}
    out = {}
    for a in applicants:
        pid = personal_id(a.ucas_id)
        if pid:
            out[(pid, str(a.course_code or "").upper())] = a
    return out


def _link(applicant, application_id, who) -> int | None:
    from education_system.systems.university.domains.admissions.domain.ucas import ucas_links

    link = ucas_links.ensure_link_for_choice(
        sf_application_id=applicant.application_id, sf_choice_id=applicant.choice_id,
        sf_student_id=applicant.student_id, linked_by=who.username)
    if not link.uni_application_id:
        ucas_links.attach_uni_application(link.link_id, application_id)
    return int(link.link_id)


def _record(conn, batch_id, row, pid, application_id, link_id) -> bool:
    """Upsert the import record; True when it was already known."""
    known = conn.execute("SELECT 1 FROM ucas_import_records WHERE personal_id = ? AND "
                         "course_code = ? AND entry_year = ?",
                         (pid, row["course_code"].upper(), row["entry_year"])).fetchone()
    conn.execute(
        "INSERT INTO ucas_import_records (batch_id, personal_id, scheme, choice_number, "
        "course_code, campus_code, entry_year, point_of_entry, ucas_status, ucas_decision, "
        "application_id, link_id, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(personal_id, course_code, entry_year) DO UPDATE SET "
        "batch_id = excluded.batch_id, scheme = excluded.scheme, "
        "choice_number = excluded.choice_number, campus_code = excluded.campus_code, "
        "point_of_entry = excluded.point_of_entry, ucas_status = excluded.ucas_status, "
        "ucas_decision = excluded.ucas_decision, application_id = excluded.application_id, "
        "link_id = COALESCE(excluded.link_id, ucas_import_records.link_id), "
        "updated_at = excluded.updated_at",
        (batch_id, pid, row.get("scheme"), row.get("choice_number"), row["course_code"].upper(),
         row.get("campus_code"), row["entry_year"], row.get("point_of_entry"),
         row.get("ucas_status"), row.get("decision"), application_id, link_id, sa.now()))
    return known is not None


def import_file(current, text: str, filename: str, file_format: str = "csv") -> dict:
    """Import a UCAS applicant file. Returns the batch with counts and the
    rows refused (line number and why)."""
    who = sa.officer(current)
    file_format = "xml" if str(file_format).lower() == "xml" else "csv"
    rows = parse(text, file_format)
    choices = _sixth_form_choices()
    results, errors = [], []
    for line, row in enumerate(rows, start=2 if file_format == "csv" else 1):
        problem = _check(row)
        if problem:
            errors.append({"line": line, "error": problem})
            continue
        pid = personal_id(row["personal_id"])
        try:
            application_id, created = _open_application(row, pid)
            applicant = choices.get((pid, row["course_code"].upper()))
            link_id = _link(applicant, application_id, who) if applicant else None
        except Exception as exc:
            errors.append({"line": line, "error": str(exc)})
            continue
        results.append((row, pid, application_id, created, link_id))
    return _store_batch(who, filename, file_format, len(rows), results, errors)


def _store_batch(who, filename, file_format, total, results, errors) -> dict:
    import json

    created = sum(1 for r in results if r[3])
    linked = sum(1 for r in results if r[4])
    with sa.session() as conn:
        batch_id = int(conn.execute(
            "INSERT INTO ucas_import_batches (filename, file_format, imported_by, rows_total, "
            "created, linked, errors_json) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (filename, file_format, who.username, total, created, linked,
             json.dumps(errors))).lastrowid)
        updated = sum(1 for row, pid, app, _new, link in results
                      if _record(conn, batch_id, row, pid, app, link))
        conn.execute("UPDATE ucas_import_batches SET updated = ? WHERE batch_id = ?",
                     (updated, batch_id))
        sa.audit(conn, who, "ucas", "import_batch", batch_id, "imported",
                 {"file": filename, "rows": total, "created": created, "errors": len(errors)})
    return {"batch_id": batch_id, "rows": total, "created": created, "updated": updated,
            "linked": linked, "errors": errors}


def batches(current, limit=50) -> list[dict]:
    sa.officer(current)
    with sa.session() as conn:
        return sa.dicts(conn.execute("SELECT * FROM ucas_import_batches ORDER BY batch_id DESC "
                                     "LIMIT ?", (limit,)))


def records(current, batch_id=None) -> list[dict]:
    sa.officer(current)
    with sa.session() as conn:
        if batch_id:
            return sa.dicts(conn.execute("SELECT * FROM ucas_import_records WHERE batch_id = ? "
                                         "ORDER BY personal_id", (batch_id,)))
        return sa.dicts(conn.execute("SELECT * FROM ucas_import_records ORDER BY updated_at DESC"))


# ── decisions file ──────────────────────────────────────────────────────


def pending_decisions(current) -> dict:
    """Decisions on UCAS applications not yet in a batch file, split into
    those ready to send and those needing a C/U/R/W decision."""
    sa.officer(current)
    ready, unclear = [], []
    with sa.session() as conn:
        course = {r["application_id"]: r for r in sa.dicts(conn.execute(
            "SELECT application_id, course_code, campus_code, entry_year, point_of_entry "
            "FROM ucas_import_records"))}
        for row in sa.dicts(conn.execute(
                "SELECT application_id, external_reference, program_applied, academic_year, "
                "decision, decision_date FROM admission_applications WHERE decision IS NOT NULL "
                "AND decision != '' AND external_reference IS NOT NULL ORDER BY decision_date")):
            pid = personal_id(row["external_reference"])
            if not pid:
                continue
            code = decision_code(row["decision"])
            day = str(row["decision_date"] or "")[:10]
            if code and conn.execute(
                    "SELECT 1 FROM ucas_decision_exports WHERE application_id = ? AND "
                    "decision_code = ? AND decision_date = ?",
                    (row["application_id"], code, day)).fetchone():
                continue
            imported = course.get(row["application_id"], {})
            item = {**row, "personal_id": pid, "decision_code": code, "decision_date": day,
                    "course_code": imported.get("course_code") or row["program_applied"],
                    "campus_code": imported.get("campus_code"),
                    "entry_year": imported.get("entry_year") or row["academic_year"],
                    "point_of_entry": imported.get("point_of_entry")}
            (ready if code else unclear).append(item)
    return {"ready": ready, "unclear": unclear}


def export_decisions(current) -> dict:
    """Write the decisions batch file into the ``ucas`` connector folder for
    upload to UCAS; each decision goes in one batch only."""
    who = sa.officer(current)
    pending = pending_decisions(current)
    if not pending["ready"]:
        return {"path": None, "count": 0, "unclear": pending["unclear"], "batch_id": None}
    batch_id = f"UCAS-DEC-{sa.stamp()}"
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["PersonalID", "CourseCode", "CampusCode", "EntryYear", "PointOfEntry",
                     "DecisionCode", "DecisionDate"])
    for d in pending["ready"]:
        writer.writerow([d["personal_id"], d["course_code"], d["campus_code"] or "",
                         d["entry_year"], d["point_of_entry"] or "", d["decision_code"],
                         d["decision_date"]])
    path = connectors.write_batch(CONNECTOR, batch_id, f"{batch_id}.csv", buf.getvalue())
    with sa.session() as conn:
        for d in pending["ready"]:
            conn.execute(
                "INSERT OR IGNORE INTO ucas_decision_exports (application_id, personal_id, "
                "decision_code, decision_date, batch_id, exported_by) VALUES (?, ?, ?, ?, ?, ?)",
                (d["application_id"], d["personal_id"], d["decision_code"], d["decision_date"],
                 batch_id, who.username))
        sa.audit(conn, who, "ucas", "decision_batch", batch_id, "file_written",
                 {"path": path, "count": len(pending["ready"])})
    return {"path": path, "count": len(pending["ready"]), "unclear": pending["unclear"],
            "batch_id": batch_id}


__all__ = ["CONNECTOR", "DECISION_CODES", "FIELDS", "REQUIRED", "batches", "decision_code",
           "export_decisions", "import_file", "parse", "pending_decisions", "personal_id",
           "records"]
