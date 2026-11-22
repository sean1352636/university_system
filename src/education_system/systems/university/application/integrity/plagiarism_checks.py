"""Similarity checks on university work.

Documents live in ``document_repository``. ``kind`` is ``submission`` (a
student's work, normally linked to an assignment submission),
``reference`` (a source staff add for comparison), ``template`` (set text
or starter code, which is never counted as a match) or ``external`` (a
published or essay-mill text found by an external search or imported by an
officer — see ``integrity_external``; compared with every module).

A check (:func:`run_check`) compares a document with:

* other students' submissions to the same assignment,
* other students' submissions to the same module in any year,
* reference documents for the module, and reference documents for no
  particular module,
* external documents.

The student's own other work is never a match, and neither is the same
group's submission to a group assignment. Where the module allows
collaboration, matches with classmates' work on the same assignment are
listed (``match_kind = 'peer'``) but not counted in the score.

Besides the word-for-word score the result keeps a paraphrase score (prose
reworded sentence by sentence) and how many disguised characters were found
(look-alike letters, hidden characters). The result keeps every matching
source with its score and passages (``plagiarism_matches``), and a review
status: anything at or above the module's threshold — or a paraphrase score
at or above ``paraphrase_threshold``, or ``obfuscation_chars`` or more
disguised characters — waits for a member of staff (``integrity_review``).

An automatic check that fails (no text could be read, the submission can't
be linked to a student) is recorded in ``integrity_check_failures`` so staff
see it (:func:`failures`) and it can be retried or checked by hand.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime

from education_system.systems.university.application.integrity import access
from education_system.systems.university.application.integrity import plagiarism_text as ptext

KINDS = ("submission", "reference", "template", "external")
PEER_KINDS = ("submission",)
MAX_SOURCES_KEPT = 20
SELF_CHECKS_PER_DAY = 3


def content_hash(text) -> str:
    return hashlib.sha256(" ".join(str(text).lower().split()).encode("utf-8")).hexdigest()


def academic_year(at=None) -> str:
    day = at or datetime.now()
    start = day.year if day.month >= 9 else day.year - 1
    return f"{start}/{str(start + 1)[-2:]}"


def _module_or_none(conn, module_code):
    if not module_code:
        return None
    found = conn.execute("SELECT module_code FROM modules WHERE module_code = ?",
                         (module_code,)).fetchone()
    return found[0] if found else None


# ── documents ───────────────────────────────────────────────────────────


def _store(conn, *, title, content, file_type, module_code, kind, author_id, student_id=None,
           assignment_id=None, submission_id=None, year=None, source_url=None) -> int:
    access.ensure(conn)
    title = str(title or "").strip() or "Untitled"
    if not str(content or "").strip():
        raise ValueError("The document has no text to check")
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {', '.join(KINDS)}")
    if author_id is None:
        raise ValueError("A document needs an author")
    row = (title, content, content_hash(content), author_id, _module_or_none(conn, module_code),
           access.now(), str(file_type or "txt").lower().lstrip("."), len(str(content).split()),
           submission_id, assignment_id, student_id, year or academic_year(), kind)
    if submission_id is not None:
        found = conn.execute("SELECT id FROM document_repository WHERE submission_id = ? "
                             "AND kind = 'submission'", (submission_id,)).fetchone()
        if found:
            conn.execute("UPDATE document_repository SET title = ?, content = ?, content_hash = ?, "
                         "author_id = ?, module_code = ?, submission_date = ?, file_type = ?, "
                         "word_count = ?, submission_id = ?, assignment_id = ?, student_id = ?, "
                         "academic_year = ?, kind = ?, purged = 0, updated_at = ? WHERE id = ?",
                         row + (access.now(), found[0]))
            return found[0]
    if kind == "external":
        found = conn.execute("SELECT id FROM document_repository WHERE content_hash = ? AND "
                             "kind = 'external'", (row[2],)).fetchone()
        if found:
            return found[0]
    cur = conn.execute(
        "INSERT INTO document_repository (title, content, content_hash, author_id, module_code, "
        "submission_date, file_type, word_count, submission_id, assignment_id, student_id, "
        "academic_year, kind, source_url) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        row + (source_url,))
    return cur.lastrowid


def add_document(conn, who: access.Person, *, title, content, file_type="txt",
                 module_code=None, kind="submission", assignment_id=None) -> int:
    """A document added by hand: a student's own work, or a reference or
    template added by staff who review the module."""
    if kind == "submission":
        access.require(who.is_student or access.can_review(conn, who, module_code),
                       "You cannot add work to this module")
        student_id = who.student_id if who.is_student else None
    elif kind == "external":
        access.require(access.is_officer(conn, who),
                       "Only an integrity officer can add external sources")
        student_id = None
    else:
        access.require(access.can_review(conn, who, module_code) and who.is_staff,
                       "Only the module's staff can add reference or template documents")
        student_id = None
    doc_id = _store(conn, title=title, content=content, file_type=file_type,
                    module_code=module_code, kind=kind, author_id=who.user_id,
                    student_id=student_id, assignment_id=assignment_id)
    access.audit(conn, who.username, "document", doc_id, "added", {"kind": kind})
    return doc_id


def register_submission(conn, submission_id, text, file_type="txt") -> int | None:
    """Put an assignment submission in the repository (system path, called
    after the submission is saved). ``None`` if it can't be linked."""
    sub = access.one(conn, "SELECT s.id, s.assignment_id, s.student_id, s.file_name, "
                           "s.submission_date, a.module_code, a.title FROM assignment_submissions s "
                           "JOIN assignments a ON a.id = s.assignment_id WHERE s.id = ?",
                     (submission_id,))
    if not sub:
        return None
    user = conn.execute("SELECT id FROM users WHERE student_id = ? OR username = ? LIMIT 1",
                        (sub["student_id"], sub["student_id"])).fetchone()
    if not user:
        return None
    try:
        when = datetime.fromisoformat(str(sub["submission_date"])[:19])
    except ValueError:
        when = None
    return _store(conn, title=f"{sub['title']} — {sub['file_name']}", content=text,
                  file_type=file_type, module_code=sub["module_code"], kind="submission",
                  author_id=user[0], student_id=sub["student_id"],
                  assignment_id=sub["assignment_id"], submission_id=submission_id,
                  year=academic_year(when))


def document(conn, who: access.Person, doc_id) -> dict:
    access.ensure(conn)
    doc = access.one(conn, "SELECT * FROM document_repository WHERE id = ?", (doc_id,))
    if not doc:
        raise ValueError(f"No document {doc_id}")
    access.require(access.can_see_document(conn, who, doc), "You cannot see this document")
    if not who.is_student:
        doc["student_id"] = access.student_label(conn, who, doc["student_id"],
                                                 doc["assignment_id"])
    return doc


DOCUMENT_FILTERS = ("module_code", "search", "kind", "file_type", "min_words", "max_words",
                    "date_from", "date_to", "student", "author")
EXPORT_COLUMNS = ("id", "title", "kind", "student_id", "author", "module_code", "assignment_id",
                  "submission_id", "academic_year", "file_type", "word_count", "submission_date",
                  "purged", "source_url")


def _day(value, name):
    value = str(value or "").strip()
    if not value:
        return None
    try:
        return datetime.strptime(value[:10], "%Y-%m-%d").strftime("%Y-%m-%d")
    except ValueError:
        raise ValueError(f"{name} must be a date (YYYY-MM-DD)") from None


def _words(value, name):
    if value in (None, ""):
        return None
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be a whole number") from None
    if number < 0:
        raise ValueError(f"{name} cannot be negative")
    return number


def documents(conn, who: access.Person, *, module_code=None, search=None, kind=None,
              file_type=None, min_words=None, max_words=None, date_from=None, date_to=None,
              student=None, author=None, limit=500) -> list[dict]:
    """Documents ``who`` may see, without their text.

    Filters: module, a text search (staff), kind, file type, word count
    range, submission date range, student and author (username). Staff
    filter by the student label they are shown, so a candidate number on an
    anonymously marked assignment cannot be used to find a student."""
    access.ensure(conn)
    if kind and kind not in KINDS:
        raise ValueError(f"kind must be one of {', '.join(KINDS)}")
    min_words, max_words = _words(min_words, "Minimum words"), _words(max_words, "Maximum words")
    if min_words is not None and max_words is not None and min_words > max_words:
        raise ValueError("The minimum word count is above the maximum")
    date_from, date_to = _day(date_from, "From date"), _day(date_to, "To date")
    if date_from and date_to and date_from > date_to:
        raise ValueError("The from date is after the to date")
    sql = ("SELECT d.id, d.title, d.author_id, u.username AS author, d.student_id, d.module_code, "
           "d.assignment_id, d.submission_id, d.academic_year, d.kind, d.file_type, d.word_count, "
           "d.submission_date, d.purged, d.source_url "
           "FROM document_repository d LEFT JOIN users u ON u.id = d.author_id WHERE 1 = 1")
    params: list = []
    if who.is_student:
        sql += " AND d.kind = 'submission' AND (d.student_id = ? OR d.author_id = ?)"
        params += [who.student_id or "", who.user_id or -1]
    else:
        modules = access.taught_modules(conn, who)
        if modules is not None:
            sql += (f" AND (d.module_code IN ({','.join('?' * len(modules)) or 'NULL'}) "
                    "OR d.kind = 'external')")
            params += modules
    for clause, value in ((" AND d.module_code = ?", module_code), (" AND d.kind = ?", kind),
                          (" AND LOWER(d.file_type) = LOWER(?)",
                           str(file_type).lstrip(".") if file_type else None),
                          (" AND d.word_count >= ?", min_words),
                          (" AND d.word_count <= ?", max_words),
                          (" AND substr(d.submission_date, 1, 10) >= ?", date_from),
                          (" AND substr(d.submission_date, 1, 10) <= ?", date_to),
                          (" AND u.username = ? COLLATE NOCASE", author or None)):
        if value is not None and value != "":
            sql += clause
            params.append(value)
    if search and not who.is_student:
        sql += " AND (d.title LIKE ? OR d.content LIKE ?)"
        params += [f"%{search}%", f"%{search}%"]
    sql += " ORDER BY d.id DESC LIMIT ?"
    params.append(int(limit))
    rows = access.dicts(conn.execute(sql, params))
    if not who.is_student:
        for r in rows:
            r["student_id"] = access.student_label(conn, who, r["student_id"], r["assignment_id"])
    if student:
        wanted = str(student).strip().lower()
        rows = [r for r in rows if str(r["student_id"] or "").lower() == wanted]
    return rows


def export_documents(conn, who: access.Person, **filters) -> str:
    """The filtered document list as CSV (metadata only, never the text).
    Staff only; every export is audited with its filters and row count."""
    import csv
    import io
    access.require(who.is_staff, "Only staff can export the document list")
    unknown = set(filters) - set(DOCUMENT_FILTERS)
    if unknown:
        raise ValueError(f"Unknown filter(s): {', '.join(sorted(unknown))}")
    rows = documents(conn, who, limit=100000, **filters)
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(EXPORT_COLUMNS)
    for r in rows:
        writer.writerow(["" if r.get(c) is None else r.get(c) for c in EXPORT_COLUMNS])
    access.audit(conn, who.username, "document", None, "exported list",
                 {"rows": len(rows), "filters": {k: v for k, v in filters.items() if v}})
    return out.getvalue()


def delete_document(conn, who: access.Person, doc_id) -> None:
    access.require(access.is_officer(conn, who), "Only an integrity officer can delete documents")
    open_case = conn.execute(
        "SELECT 1 FROM plagiarism_results r JOIN integrity_cases c ON c.id = r.case_id "
        "WHERE (r.document_id = ? OR r.matched_document_id = ?) AND c.status IN "
        "('open', 'investigating')", (doc_id, doc_id)).fetchone()
    if open_case:
        raise ValueError("This document is evidence in an open integrity case")
    conn.execute("DELETE FROM document_repository WHERE id = ?", (doc_id,))
    access.audit(conn, who.username, "document", doc_id, "deleted")


# ── checking ────────────────────────────────────────────────────────────


def _group_of(conn, submission_id):
    if not submission_id:
        return None
    if "group_id" not in {r[1] for r in conn.execute("PRAGMA table_info(assignment_submissions)")}:
        return None
    row = conn.execute("SELECT group_id FROM assignment_submissions WHERE id = ?",
                       (submission_id,)).fetchone()
    return row[0] if row else None


def _candidates(conn, doc) -> list[dict]:
    rows = access.dicts(conn.execute(
        "SELECT id, content, file_type, kind, student_id, author_id, assignment_id, "
        "submission_id FROM document_repository "
        "WHERE id <> ? AND COALESCE(purged, 0) = 0 AND kind IN ('submission', 'reference', "
        "'external') "
        "AND NOT (kind = 'submission' AND ((student_id IS NOT NULL AND student_id = ?) "
        "OR (student_id IS NULL AND author_id = ?))) "
        "AND ((assignment_id IS NOT NULL AND assignment_id = ?) OR module_code = ? "
        "OR (kind = 'reference' AND module_code IS NULL) OR kind = 'external')",
        (doc["id"], doc.get("student_id"), doc["author_id"], doc.get("assignment_id"),
         doc.get("module_code"))))
    group = _group_of(conn, doc.get("submission_id"))
    if group is not None:
        rows = [r for r in rows if not (r["kind"] == "submission"
                                        and r["assignment_id"] == doc.get("assignment_id")
                                        and _group_of(conn, r["submission_id"]) == group)]
    return rows


def _template_shingles(conn, doc, n) -> set[int]:
    found: set[int] = set()
    for row in conn.execute(
            "SELECT content, file_type FROM document_repository WHERE kind = 'template' AND "
            "((assignment_id IS NOT NULL AND assignment_id = ?) OR "
            "(assignment_id IS NULL AND module_code = ?))",
            (doc.get("assignment_id"), doc.get("module_code"))):
        if ptext.is_code(row[1]) == ptext.is_code(doc.get("file_type")):
            found |= set(ptext.prepare(row[0], row[1], n).shingles)
    return found


def compute(conn, doc) -> dict:
    """Compare ``doc`` with its corpus. Stores nothing."""
    n = int(access.number(conn, "shingle_words"))
    prepared = ptext.prepare(doc["content"], doc.get("file_type"), n)
    ignore = _template_shingles(conn, doc, n)
    peers_allowed = access.collaboration_allowed(conn, doc.get("module_code"))
    covered: set[int] = set()
    reworded: set[int] = set()
    sources = []
    for cand in _candidates(conn, doc):
        if ptext.is_code(cand["file_type"]) != ptext.is_code(doc.get("file_type")):
            continue
        other = ptext.prepare(cand["content"], cand["file_type"], n)
        found = ptext.compare(prepared, other, ignore=ignore)
        para = ptext.paraphrase(prepared, other, found["covered"])
        if not found["covered"] and not para["covered"]:
            continue
        peer = (peers_allowed and cand["kind"] in PEER_KINDS and doc.get("assignment_id")
                and cand["assignment_id"] == doc.get("assignment_id"))
        if not peer:
            covered |= found["covered"]
            reworded |= para["covered"]
        words = found["covered"] | para["covered"]
        sources.append({"document_id": cand["id"], "matched_words": len(words),
                        "score": ptext.score(len(words), prepared),
                        "kind": "peer" if peer else ("paraphrase" if not found["covered"]
                                                     else "exact"),
                        "counted": not peer,
                        "passages": found["passages"] + para["passages"]})
    sources.sort(key=lambda s: (s["counted"], s["score"]), reverse=True)
    return {"score": ptext.score(len(covered), prepared),
            "paraphrase_score": ptext.score(len(reworded - covered), prepared),
            "obfuscated": prepared.obfuscated, "sources": sources,
            "words_checked": len(prepared.tokens), "words_excluded": prepared.excluded_words}


def needs_review(conn, found, threshold) -> bool:
    return (found["score"] >= threshold
            or found["paraphrase_score"] >= access.number(conn, "paraphrase_threshold")
            or found["obfuscated"] >= access.number(conn, "obfuscation_chars"))


def _report(found, status, threshold) -> str:
    extra = ""
    if found["paraphrase_score"]:
        extra += (f" A further {found['paraphrase_score']:.0%} of the words are in sentences that "
                  "reword a source.")
    if found["obfuscated"]:
        extra += (f" {found['obfuscated']} disguised character(s) (look-alike letters from "
                  "another alphabet or hidden characters inside words) were found.")
    peers = sum(1 for s in found["sources"] if not s["counted"])
    if peers:
        extra += (f" {peers} match(es) with classmates on this assignment are listed but not "
                  "counted: the module allows collaboration.")
    if not found["sources"]:
        return (f"No matching text found in {found['words_checked']} words checked "
                f"({found['words_excluded']} quoted or reference-list words left out).{extra}")
    counted = sum(1 for s in found["sources"] if s["counted"])
    return (f"{found['score']:.0%} of {found['words_checked']} words checked also appear in "
            f"{counted} other source(s); status {status}. Review threshold "
            f"{threshold:.0%}. {found['words_excluded']} quoted or reference-list words were "
            f"left out.{extra}")


def run_check(conn, document_id, *, who: access.Person | None = None) -> int:
    """Check one document and store the result. ``who`` is ``None`` only
    for the automatic check on submission."""
    access.ensure(conn)
    doc = access.one(conn, "SELECT * FROM document_repository WHERE id = ?", (document_id,))
    if not doc:
        raise ValueError(f"No document {document_id}")
    if who is not None:
        access.require(access.can_review(conn, who, doc["module_code"]) and who.is_staff,
                       "Only the module's staff can run a check on this work")
    if doc.get("purged"):
        raise ValueError("This document's text has been removed under the retention policy")
    found = compute(conn, doc)
    threshold = access.module_threshold(conn, doc["module_code"])
    status = ptext.band(found["score"], threshold, access.number(conn, "high_threshold"))
    review = needs_review(conn, found, threshold)
    hold = review and access.setting(conn, "release_after_review") == "1"
    best = next((s["document_id"] for s in found["sources"] if s["counted"]), None)
    cur = conn.execute(
        "INSERT INTO plagiarism_results (document_id, matched_document_id, similarity_score, "
        "check_date, checked_by, status, report, threshold_used, submission_id, assignment_id, "
        "words_checked, words_excluded, review_status, released_to_student, paraphrase_score, "
        "obfuscated_chars) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (document_id, best, found["score"], access.now(), who.user_id if who else None, status,
         _report(found, status, threshold), threshold, doc.get("submission_id"),
         doc.get("assignment_id"), found["words_checked"], found["words_excluded"],
         "pending" if review else "not_needed", 0 if hold else 1, found["paraphrase_score"],
         found["obfuscated"]))
    result_id = cur.lastrowid
    for src in found["sources"][:MAX_SOURCES_KEPT]:
        conn.execute("INSERT INTO plagiarism_matches (result_id, matched_document_id, score, "
                     "matched_words, passages, match_kind, counted) VALUES (?, ?, ?, ?, ?, ?, ?)",
                     (result_id, src["document_id"], src["score"], src["matched_words"],
                      json.dumps(src["passages"]), src["kind"], 1 if src["counted"] else 0))
    if doc.get("submission_id"):
        resolve_failure(conn, doc["submission_id"], "checked")
    access.audit(conn, who.username if who else "automatic", "result", result_id, "checked",
                 {"document": document_id, "score": found["score"], "status": status,
                  "paraphrase": found["paraphrase_score"], "obfuscated": found["obfuscated"]})
    return result_id


def check_submission(conn, submission_id, text, file_type="txt") -> int | None:
    """The automatic check after a student submits. ``None`` when checks
    are off for the module; ``ValueError`` when the submission can't be
    linked to a student account."""
    access.ensure(conn)
    module = conn.execute("SELECT a.module_code FROM assignment_submissions s JOIN assignments a "
                          "ON a.id = s.assignment_id WHERE s.id = ?", (submission_id,)).fetchone()
    if not module or not access.checks_enabled(conn, module[0]):
        return None
    doc_id = register_submission(conn, submission_id, text, file_type)
    if not doc_id:
        raise ValueError("The submission could not be linked to a student account")
    return run_check(conn, doc_id)


# ── failed automatic checks ─────────────────────────────────────────────


def record_failure(conn, submission_id, error) -> None:
    """Note that the automatic check of ``submission_id`` failed (system
    path, on its own connection after the failed attempt rolled back)."""
    access.ensure(conn)
    conn.execute(
        "INSERT INTO integrity_check_failures (submission_id, attempts, last_error, "
        "first_failed_at, last_attempt_at) VALUES (?, 1, ?, ?, ?) ON CONFLICT(submission_id) "
        "DO UPDATE SET attempts = attempts + 1, last_error = excluded.last_error, "
        "last_attempt_at = excluded.last_attempt_at, resolved_at = NULL, resolved_by = NULL, "
        "resolution = NULL",
        (submission_id, str(error)[:500], access.now(), access.now()))
    access.audit(conn, "automatic", "submission", submission_id, "check failed",
                 {"error": str(error)[:200]})


def resolve_failure(conn, submission_id, resolution, by="automatic") -> None:
    conn.execute("UPDATE integrity_check_failures SET resolved_at = ?, resolved_by = ?, "
                 "resolution = ? WHERE submission_id = ? AND resolved_at IS NULL",
                 (access.now(), by, resolution, submission_id))


def failures(conn, who: access.Person, *, include_resolved=False) -> list[dict]:
    """Failed automatic checks on modules ``who`` reviews."""
    access.require(who.is_staff, "Failed checks are for staff")
    access.ensure(conn)
    sql = ("SELECT f.*, s.assignment_id, s.student_id, s.file_name, s.file_path, a.module_code, "
           "a.title AS assignment_title FROM integrity_check_failures f "
           "JOIN assignment_submissions s ON s.id = f.submission_id "
           "JOIN assignments a ON a.id = s.assignment_id WHERE 1 = 1")
    params: list = []
    if not include_resolved:
        sql += " AND f.resolved_at IS NULL"
    modules = access.taught_modules(conn, who)
    if modules is not None:
        sql += f" AND a.module_code IN ({','.join('?' * len(modules)) or 'NULL'})"
        params += modules
    rows = access.dicts(conn.execute(sql + " ORDER BY f.last_attempt_at DESC", params))
    for r in rows:
        r["student_id"] = access.student_label(conn, who, r["student_id"], r["assignment_id"])
    return rows


def _failure_module(conn, submission_id):
    row = conn.execute("SELECT a.module_code FROM assignment_submissions s JOIN assignments a "
                       "ON a.id = s.assignment_id WHERE s.id = ?", (submission_id,)).fetchone()
    if not row:
        raise ValueError(f"No submission {submission_id}")
    return row[0]


def check_by_hand(conn, who: access.Person, submission_id, text, file_type="txt") -> int:
    """Staff supply the text of a submission whose automatic check failed
    (a scanned PDF typed up or run through OCR) and check it."""
    access.require(who.is_staff and access.can_review(conn, who, _failure_module(conn,
                                                                                 submission_id)),
                   "Only the module's staff can check this submission")
    doc_id = register_submission(conn, submission_id, text, file_type)
    if not doc_id:
        raise ValueError("The submission could not be linked to a student account")
    result_id = run_check(conn, doc_id, who=who)
    resolve_failure(conn, submission_id, "checked by hand", who.username)
    return result_id


def dismiss_failure(conn, who: access.Person, submission_id, note) -> None:
    """Close a failed check that will not be checked (e.g. an image-only
    portfolio), with the reason."""
    access.require(who.is_staff and access.can_review(conn, who, _failure_module(conn,
                                                                                 submission_id)),
                   "Only the module's staff can dismiss this")
    if not str(note or "").strip():
        raise ValueError("Say why this submission will not be checked")
    resolve_failure(conn, submission_id, f"not checked: {note.strip()}", who.username)
    access.audit(conn, who.username, "submission", submission_id, "check dismissed",
                 {"note": note.strip()})


def self_check(conn, who: access.Person, *, text, file_type="txt", module_code=None,
               assignment_id=None) -> dict:
    """A student's draft check before submitting: the score and their own
    matching passages, nothing about the sources, nothing stored."""
    access.require(who.is_student, "Draft checks are for students")
    access.ensure(conn)
    today = access.now()[:10]
    used = conn.execute("SELECT COUNT(*) FROM integrity_audit WHERE actor = ? AND action = "
                        "'draft checked' AND at >= ?", (who.username, today)).fetchone()[0]
    if used >= SELF_CHECKS_PER_DAY:
        raise ValueError(f"You can check {SELF_CHECKS_PER_DAY} drafts a day")
    doc = {"id": -1, "content": str(text or ""), "file_type": file_type,
           "module_code": module_code, "assignment_id": assignment_id,
           "student_id": who.student_id, "author_id": who.user_id}
    found = compute(conn, doc)
    access.audit(conn, who.username, "draft", assignment_id, "draft checked",
                 {"score": found["score"]})
    passages = sorted({(p["start"], p["end"], p.get("kind", "exact"))
                       for s in found["sources"] if s["counted"] for p in s["passages"]})
    return {"score": found["score"], "paraphrase_score": found["paraphrase_score"],
            "obfuscated": found["obfuscated"], "words_checked": found["words_checked"],
            "words_excluded": found["words_excluded"],
            "passages": [{"start": a, "end": b, "kind": k, "text": doc["content"][a:b]}
                         for a, b, k in passages]}
