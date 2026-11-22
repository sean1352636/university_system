"""Keeping submitted text no longer than needed.

* :func:`purge` — after ``retention_years`` the text of a submission is
  removed (the row, its scores and its matched-passage positions stay so
  past results still make sense). Text that is evidence in a case that is
  not closed is kept until the case closes. Evidence files of cases closed
  more than ``retention_years`` ago are deleted too (the evidence rows,
  with their hashes, stay on the case record).
* :func:`export` — everything held about one student's work, for a
  subject access request (the student themself or an officer).
* :func:`erase` — remove a student's documents, results and AI-writing
  readings (administrator only). Anything that is evidence in a case is
  kept, and listed. Readings' text follows the same retention period.
"""

from __future__ import annotations

from datetime import datetime

from education_system.systems.university.application.integrity import access

PURGED_TEXT = "[text removed under the retention policy]"

_IN_LIVE_CASE = ("SELECT 1 FROM plagiarism_results r JOIN integrity_cases c ON c.id = r.case_id "
                 "WHERE (r.document_id = d.id OR r.matched_document_id = d.id) "
                 "AND COALESCE(c.stage, 'referred') <> 'closed'")


def purge(conn, as_of=None) -> int:
    access.ensure(conn)
    years = int(access.number(conn, "retention_years"))
    day = as_of or datetime.now()
    cutoff = access.now(day.replace(year=day.year - years))
    cur = conn.execute(
        f"UPDATE document_repository AS d SET content = ?, content_hash = '', purged = 1, "  # nosec B608
        f"updated_at = ? WHERE COALESCE(purged, 0) = 0 AND kind = 'submission' "
        f"AND submission_date < ? AND NOT EXISTS ({_IN_LIVE_CASE})",
        (PURGED_TEXT, access.now(), cutoff))
    files = _purge_evidence_files(conn, cutoff)
    from education_system.systems.university.application.integrity import ai as integrity_ai
    readings = integrity_ai.purge(conn, cutoff)
    if cur.rowcount or files or readings:
        access.audit(conn, "retention", "retention", None, "purged",
                     {"documents": cur.rowcount, "evidence_files": files,
                      "ai_readings": readings, "cutoff": cutoff})
    return cur.rowcount


def _purge_evidence_files(conn, cutoff) -> int:
    from education_system.systems.university.infrastructure.integrity import evidence_store
    removed = 0
    for evidence_id, path in conn.execute(
            "SELECT e.evidence_id, e.file_path FROM integrity_evidence e JOIN integrity_cases c "
            "ON c.id = e.case_id WHERE e.file_path IS NOT NULL AND c.stage = 'closed' AND "
            "COALESCE(c.closed_at, c.updated_at) < ?", (cutoff,)).fetchall():
        evidence_store.remove(path)
        conn.execute("UPDATE integrity_evidence SET file_path = NULL, removed_at = COALESCE("
                     "removed_at, ?) WHERE evidence_id = ?", (access.now(), evidence_id))
        removed += 1
    return removed


def _student_docs(conn, student_id) -> list[dict]:
    return access.dicts(conn.execute(
        "SELECT * FROM document_repository WHERE student_id = ? OR (student_id IS NULL AND "
        "author_id = (SELECT id FROM users WHERE student_id = ? LIMIT 1))",
        (student_id, student_id)))


def export(conn, who: access.Person, student_id) -> dict:
    access.ensure(conn)
    access.require(access.is_officer(conn, who) or who.student_id == student_id,
                   "Only the student or an integrity officer can export this")
    docs = _student_docs(conn, student_id)
    ids = [d["id"] for d in docs] or [-1]
    marks = ",".join("?" * len(ids))
    results = access.dicts(conn.execute(
        f"SELECT * FROM plagiarism_results WHERE document_id IN ({marks})", ids))  # nosec B608
    cases = access.dicts(conn.execute("SELECT * FROM integrity_cases WHERE student_id = ?",
                                      (student_id,)))
    case_ids = [c["id"] for c in cases] or [-1]
    cmarks = ",".join("?" * len(case_ids))
    data = {
        "student_id": student_id,
        "documents": docs,
        "results": results,
        "cases": cases,
        "case_events": access.dicts(conn.execute(
            f"SELECT * FROM integrity_case_events WHERE case_id IN ({cmarks})",  # nosec B608
            case_ids)),
        "appeals": access.dicts(conn.execute(
            f"SELECT * FROM integrity_appeals WHERE case_id IN ({cmarks})", case_ids)),  # nosec B608
        "ai_readings": _ai().export(conn, student_id),
        "statements": access.dicts(conn.execute(
            f"SELECT * FROM integrity_statements WHERE case_id IN ({cmarks})",  # nosec B608
            case_ids)),
        # Items kept from the student (a third party's personal data) stay out
        # of a subject access export too.
        "evidence": [{k: v for k, v in e.items() if k != "file_path"} for e in access.dicts(
            conn.execute(f"SELECT * FROM integrity_evidence WHERE case_id IN ({cmarks}) "  # nosec B608
                         "AND visible_to_student = 1", case_ids))],
    }
    access.audit(conn, who.username, "student", student_id, "exported",
                 {k: len(v) for k, v in data.items() if isinstance(v, list)})
    return data


def erase(conn, who: access.Person, student_id) -> dict:
    access.require(who.is_admin, "Only an administrator can erase integrity records")
    access.ensure(conn)
    kept, removed = [], 0
    for doc in _student_docs(conn, student_id):
        evidence = conn.execute(
            "SELECT 1 FROM plagiarism_results WHERE (document_id = ? OR matched_document_id = ?) "
            "AND case_id IS NOT NULL", (doc["id"], doc["id"])).fetchone()
        if evidence:
            kept.append(doc["id"])
            continue
        conn.execute("DELETE FROM document_repository WHERE id = ?", (doc["id"],))
        removed += 1
    ai = _ai().erase(conn, student_id)
    access.audit(conn, who.username, "student", "(erased)", "erased",
                 {"removed": removed, "kept_as_evidence": len(kept),
                  "ai_readings_removed": ai["removed"]})
    return {"removed": removed, "kept_as_evidence": kept,
            "ai_readings_removed": ai["removed"],
            "ai_readings_kept_as_evidence": ai["kept_as_evidence"]}


def erase_closed_cases(conn, student_id) -> int:
    """Remove the parts of ``student_id``'s closed cases that hold no
    foreign key (events, statements, evidence and its files, appeals), ahead
    of the case rows themselves (system path, for student erasure, which
    refuses while a case is still open)."""
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE name = 'integrity_cases'").fetchone():
        return 0
    access.ensure(conn)
    from education_system.systems.university.infrastructure.integrity import evidence_store
    ids = [r[0] for r in conn.execute("SELECT id FROM integrity_cases WHERE student_id = ? AND "
                                      "stage = 'closed'", (str(student_id),))]
    for case_id in ids:
        for (path,) in conn.execute("SELECT file_path FROM integrity_evidence WHERE case_id = ? "
                                    "AND file_path IS NOT NULL", (case_id,)).fetchall():
            evidence_store.remove(path)
        for table in ("integrity_case_events", "integrity_statements", "integrity_evidence",
                      "integrity_appeals"):
            conn.execute(f'DELETE FROM "{table}" WHERE case_id = ?', (case_id,))  # nosec B608
        conn.execute("UPDATE plagiarism_results SET case_id = NULL WHERE case_id = ?", (case_id,))
    return len(ids)


def _ai():
    from education_system.systems.university.application.integrity import ai as integrity_ai
    return integrity_ai
