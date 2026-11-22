"""Staff tools in Academic Integrity, brought back from the old plagiarism
checker on the current rules.

* :func:`compare` — two documents side by side: the share of each that
  appears in the other, word for word and reworded, with every passage in
  both texts (:func:`comparison_html` / :func:`comparison_text` to save it).
* :func:`import_files` — many files at once into the repository: student
  work for a module (the student number taken from each file name, or
  given), references or templates; submissions can be checked as they go
  in. Each file stands alone: one bad file does not stop the rest.
* :func:`bulk_check` / :func:`bulk_delete` — check, or (integrity officers)
  delete, several documents; documents that are case evidence stay.
* :func:`export_texts` — selected documents' text as a ZIP (plain text,
  Markdown or HTML, with a manifest); :func:`convert` is the conversion.
* :func:`document_history` / :func:`student_history` — every check on a
  document, and every document and check for a student.
* :func:`statistics_detail` and :func:`report` / :func:`render` — figures by
  module, band, file type and month, and the summary, trends, modules,
  staff activity and repository health reports as CSV, HTML or PDF.
* :func:`repository_health` / :func:`fix_repository` — orphaned results and
  matches, empty documents, unknown authors, duplicate texts.
* :func:`email_report` / :func:`export_report` — a similarity report by
  e-mail or as a file: the checked document's own passages and the kind of
  each source, never another student's text.
* :func:`original_file` — the file the student uploaded.

Everyone sees only what ``integrity_access`` lets them see; every action is
audited. Functions take an open connection and do not commit.
"""

from __future__ import annotations

import csv
import html
import io
import json
import os
import re
import zipfile
from datetime import datetime

from education_system.systems.university.application.integrity import access
from education_system.systems.university.application.integrity import review
from education_system.systems.university.application.integrity import plagiarism_checks as checks
from education_system.systems.university.application.integrity import plagiarism_text as ptext

TEXT_FORMATS = ("txt", "md", "html")
REPORT_FORMATS = ("csv", "html", "pdf")
REPORTS = {
    "summary": "Summary",
    "trends": "Trends by month",
    "modules": "By module",
    "users": "Staff activity",
    "health": "Repository health",
}
IMPORT_KINDS = ("submission", "reference", "template")
_STUDENT_IN_NAME = re.compile(r"(?<![0-9A-Za-z])([A-Za-z]?\d{5,10})(?![0-9])")


# ── seeing a document ───────────────────────────────────────────────────


def _raw(conn, doc_id) -> dict:
    access.ensure(conn)
    doc = access.one(conn, "SELECT * FROM document_repository WHERE id = ?", (doc_id,))
    if not doc:
        raise ValueError(f"No document {doc_id}")
    return doc


def _visible(conn, who: access.Person, doc_id) -> dict:
    """The document with its text, if ``who`` may see it. Shared sources
    (references and external texts for no particular module) are open to
    all staff."""
    doc = _raw(conn, doc_id)
    shared = doc["kind"] in ("reference", "external") and not doc["module_code"]
    access.require(access.can_see_document(conn, who, doc) or (shared and who.is_staff),
                   f"You cannot see document {doc_id}")
    return doc


def _label(conn, who, doc) -> dict:
    """Metadata of ``doc`` as ``who`` may see it (no text)."""
    student = doc.get("student_id")
    if who.is_staff:
        student = access.student_label(conn, who, student, doc.get("assignment_id"))
    return {"id": doc["id"], "title": doc["title"], "kind": doc["kind"],
            "module_code": doc["module_code"], "student": student,
            "file_type": doc["file_type"], "words": doc["word_count"],
            "submitted": doc["submission_date"], "year": doc.get("academic_year"),
            "purged": bool(doc.get("purged"))}


# ── compare two documents ───────────────────────────────────────────────


def _one_way(sub, src, text_sub, text_src) -> dict:
    exact = ptext.compare(sub, src)
    reworded = ptext.paraphrase(sub, src, exact["covered"])
    passages = []
    for p in exact["passages"] + reworded["passages"]:
        passages.append({**p, "text": text_sub[p["start"]:p["end"]],
                         "source_text": (text_src[p["source_start"]:p["source_end"]]
                                         if p.get("source_start") is not None else "")})
    passages.sort(key=lambda p: p["start"])
    return {"score": ptext.score(len(exact["covered"]), sub),
            "paraphrase_score": ptext.score(len(reworded["covered"] - exact["covered"]), sub),
            "words": len(sub.tokens), "passages": passages}


def compare(conn, who: access.Person, doc_a, doc_b) -> dict:
    """How much of each document appears in the other (staff)."""
    access.require(who.is_staff, "Comparing documents is for staff")
    if int(doc_a) == int(doc_b):
        raise ValueError("Choose two different documents")
    a, b = _visible(conn, who, doc_a), _visible(conn, who, doc_b)
    for d in (a, b):
        if d.get("purged"):
            raise ValueError(f"The text of document {d['id']} was removed under the retention "
                             "policy")
    if ptext.is_code(a["file_type"]) != ptext.is_code(b["file_type"]):
        raise ValueError("Compare code with code and prose with prose")
    n = int(access.number(conn, "shingle_words"))
    pa, pb = ptext.prepare(a["content"], a["file_type"], n), ptext.prepare(b["content"],
                                                                           b["file_type"], n)
    access.audit(conn, who.username, "document", a["id"], "compared", {"with": b["id"]})
    return {"a": {**_label(conn, who, a), "text": a["content"],
                  **_one_way(pa, pb, a["content"], b["content"])},
            "b": {**_label(conn, who, b), "text": b["content"],
                  **_one_way(pb, pa, b["content"], a["content"])},
            "compared_at": access.now(), "compared_by": who.username}


def _highlighted(text, passages) -> str:
    out, pos = [], 0
    for p in sorted(passages, key=lambda p: p["start"]):
        if p["start"] < pos:
            continue
        out.append(html.escape(text[pos:p["start"]]))
        colour = "#ffd59a" if p.get("kind") == "paraphrase" else "#ffe08a"
        out.append(f'<mark style="background:{colour}">'
                   f'{html.escape(text[p["start"]:p["end"]])}</mark>')
        pos = p["end"]
    out.append(html.escape(text[pos:]))
    return "".join(out).replace("\n", "<br>\n")


def comparison_html(result) -> str:
    a, b = result["a"], result["b"]

    def side(d, other):
        return (f"<td style='vertical-align:top;width:50%'><h2>{html.escape(d['title'])}</h2>"
                f"<p>Document {d['id']} · {html.escape(str(d['module_code'] or 'no module'))} · "
                f"{d['words']} words checked<br>{d['score']:.0%} also in document "
                f"{other['id']}; a further {d['paraphrase_score']:.0%} reworded</p>"
                f"<div style='font-family:serif'>{_highlighted(d['text'], d['passages'])}</div></td>")
    return ("<!doctype html><html><head><meta charset='utf-8'><title>Document comparison"
            "</title></head><body><h1>Document comparison</h1>"
            f"<p>{html.escape(result['compared_at'])} by {html.escape(result['compared_by'])}. "
            "Yellow: the same words in both; orange: the same sentence reworded.</p>"
            f"<table><tr>{side(a, b)}{side(b, a)}</tr></table></body></html>")


def comparison_text(result) -> str:
    lines = [f"Document comparison — {result['compared_at']} by {result['compared_by']}", ""]
    for d, other in ((result["a"], result["b"]), (result["b"], result["a"])):
        lines += [f"Document {d['id']}: {d['title']} ({d['module_code'] or 'no module'})",
                  f"  {d['score']:.0%} also in document {other['id']}, "
                  f"{d['paraphrase_score']:.0%} reworded, {d['words']} words checked", ""]
    lines.append("Matching passages")
    for p in result["a"]["passages"]:
        lines += [f"- [{p.get('kind', 'exact')}] {result['a']['id']}: {p['text']}",
                  f"  {result['b']['id']}: {p['source_text']}", ""]
    return "\n".join(lines)


# ── many files at once ──────────────────────────────────────────────────


def student_from_name(conn, name) -> str | None:
    """The student number in a file name such as ``5853694_essay.pdf``, if
    it is a real student."""
    for candidate in _STUDENT_IN_NAME.findall(os.path.basename(str(name))):
        if conn.execute("SELECT 1 FROM students WHERE student_id = ?", (candidate,)).fetchone():
            return candidate
    return None


def _user_of_student(conn, student_id):
    row = conn.execute("SELECT id FROM users WHERE student_id = ? OR username = ? LIMIT 1",
                       (student_id, student_id)).fetchone()
    return row[0] if row else None


def import_files(conn, who: access.Person, files, *, kind, module_code=None, assignment_id=None,
                 students=None, check=True) -> list[dict]:
    """Bring ``files`` (paths) into the repository. ``kind`` is
    ``submission`` (student work; each file's student number from
    ``students[path]`` or the file name), ``reference`` or ``template``.
    Returns one outcome per file."""
    from education_system.systems.university.infrastructure.integrity import text_extract
    access.ensure(conn)
    if kind not in IMPORT_KINDS:
        raise ValueError(f"kind must be one of {', '.join(IMPORT_KINDS)}")
    module = checks._module_or_none(conn, module_code)
    if module_code and not module:
        raise ValueError(f"No module {module_code}")
    if kind != "reference" and not module:
        raise ValueError("Choose the module")
    access.require(who.is_staff and (access.can_review(conn, who, module) if module
                                      else access.is_officer(conn, who)),
                   "Only the module's staff can bring work into the repository")
    if assignment_id and not conn.execute("SELECT 1 FROM assignments WHERE id = ? AND "
                                          "module_code = ?", (assignment_id, module)).fetchone():
        raise ValueError(f"Assignment {assignment_id} is not on {module}")
    students = students or {}
    outcomes = []
    for path in files:
        name = os.path.basename(str(path))
        outcome = {"file": name, "document_id": None, "result_id": None, "student": None,
                   "status": "added", "error": None}
        conn.execute("SAVEPOINT import_file")
        try:
            text = text_extract.extract(path)
            student = None
            if kind == "submission":
                student = students.get(path) or students.get(name) or student_from_name(conn, name)
                if not student:
                    raise ValueError("No student number in the file name; give one")
                if not conn.execute("SELECT 1 FROM students WHERE student_id = ?",
                                    (str(student),)).fetchone():
                    raise ValueError(f"No student {student}")
            author = (_user_of_student(conn, student) if student else None) or who.user_id
            doc_id = checks._store(conn, title=os.path.splitext(name)[0], content=text,
                                   file_type=text_extract.file_type(path), module_code=module,
                                   kind=kind, author_id=author, student_id=student,
                                   assignment_id=assignment_id)
            outcome.update(document_id=doc_id, student=student)
            if check and kind == "submission":
                outcome["result_id"] = checks.run_check(conn, doc_id, who=who)
                outcome["status"] = "added and checked"
            conn.execute("RELEASE SAVEPOINT import_file")
        except Exception as exc:          # one bad file must not stop the rest
            conn.execute("ROLLBACK TO SAVEPOINT import_file")
            conn.execute("RELEASE SAVEPOINT import_file")
            outcome.update(status="not added", error=str(exc))
        outcomes.append(outcome)
    access.audit(conn, who.username, "document", None, "files imported",
                 {"kind": kind, "module": module, "files": len(outcomes),
                  "added": sum(1 for o in outcomes if o["document_id"])})
    return outcomes


def bulk_check(conn, who: access.Person, doc_ids) -> list[dict]:
    """Check several documents; each result or the reason it was refused."""
    access.require(who.is_staff, "Only staff can run checks")
    outcomes = []
    for doc_id in doc_ids:
        conn.execute("SAVEPOINT bulk_check")
        try:
            result_id = checks.run_check(conn, int(doc_id), who=who)
            score = conn.execute("SELECT similarity_score, status FROM plagiarism_results "
                                 "WHERE id = ?", (result_id,)).fetchone()
            outcomes.append({"document_id": int(doc_id), "result_id": result_id,
                             "score": score[0], "band": score[1], "error": None})
            conn.execute("RELEASE SAVEPOINT bulk_check")
        except (ValueError, PermissionError) as exc:
            conn.execute("ROLLBACK TO SAVEPOINT bulk_check")
            conn.execute("RELEASE SAVEPOINT bulk_check")
            outcomes.append({"document_id": int(doc_id), "result_id": None, "score": None,
                             "band": None, "error": str(exc)})
    return outcomes


def bulk_delete(conn, who: access.Person, doc_ids, reason) -> list[dict]:
    """Delete several documents (integrity officers); evidence stays."""
    access.require(access.is_officer(conn, who), "Only an integrity officer can delete documents")
    if not str(reason or "").strip():
        raise ValueError("Give the reason for deleting these documents")
    outcomes = []
    for doc_id in doc_ids:
        conn.execute("SAVEPOINT bulk_delete")
        try:
            evidence = conn.execute(
                "SELECT 1 FROM plagiarism_results WHERE (document_id = ? OR matched_document_id "
                "= ?) AND case_id IS NOT NULL", (doc_id, doc_id)).fetchone()
            if evidence:
                raise ValueError("evidence in an integrity case")
            if not conn.execute("SELECT 1 FROM document_repository WHERE id = ?",
                                (doc_id,)).fetchone():
                raise ValueError("no such document")
            checks.delete_document(conn, who, int(doc_id))
            conn.execute("RELEASE SAVEPOINT bulk_delete")
            outcomes.append({"document_id": int(doc_id), "deleted": True, "error": None})
        except (ValueError, PermissionError) as exc:
            conn.execute("ROLLBACK TO SAVEPOINT bulk_delete")
            conn.execute("RELEASE SAVEPOINT bulk_delete")
            outcomes.append({"document_id": int(doc_id), "deleted": False, "error": str(exc)})
    access.audit(conn, who.username, "document", None, "bulk deleted",
                 {"reason": reason.strip(), "deleted": [o["document_id"] for o in outcomes
                                                       if o["deleted"]]})
    return outcomes


# ── export and conversion ───────────────────────────────────────────────


def convert(text, fmt, title="") -> str:
    """``text`` as plain text, Markdown or HTML."""
    if fmt not in TEXT_FORMATS:
        raise ValueError(f"format must be one of {', '.join(TEXT_FORMATS)}")
    text = str(text or "")
    if fmt == "txt":
        return text
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if fmt == "md":
        head = f"# {title}\n\n" if title else ""
        return head + "\n\n".join(p.replace("\n", "  \n") for p in paragraphs) + "\n"
    body = "\n".join(f"<p>{html.escape(p).replace(chr(10), '<br>')}</p>" for p in paragraphs)
    return (f"<!doctype html><html><head><meta charset='utf-8'><title>{html.escape(title)}"
            f"</title></head><body>{f'<h1>{html.escape(title)}</h1>' if title else ''}{body}"
            "</body></html>")


def _safe_name(text) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", str(text or "document"))[:60].strip("_") or "document"


def export_texts(conn, who: access.Person, doc_ids, path, fmt="txt") -> dict:
    """Write the documents ``who`` may see, with their text, to a ZIP at
    ``path`` (owner-only), with a manifest. Documents whose text was
    removed under the retention policy are listed in the manifest only."""
    if fmt not in TEXT_FORMATS:
        raise ValueError(f"format must be one of {', '.join(TEXT_FORMATS)}")
    docs = [_visible(conn, who, d) for d in doc_ids]
    if not docs:
        raise ValueError("Choose the documents to export")
    manifest = io.StringIO()
    writer = csv.writer(manifest)
    writer.writerow(["id", "file", "title", "kind", "module", "student", "file_type", "words",
                     "submitted", "text"])
    written = 0
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as fh, zipfile.ZipFile(fh, "w", zipfile.ZIP_DEFLATED) as zf:
        for d in docs:
            meta = _label(conn, who, d)
            name = f"{d['id']}_{_safe_name(d['title'])}.{fmt}"
            if d.get("purged"):
                name, state = "", "removed under the retention policy"
            else:
                zf.writestr(name, convert(d["content"], fmt, d["title"]))
                written += 1
                state = "included"
            writer.writerow([d["id"], name, d["title"], d["kind"], d["module_code"],
                             meta["student"], d["file_type"], d["word_count"],
                             d["submission_date"], state])
        zf.writestr("manifest.csv", manifest.getvalue())
    os.chmod(str(path), 0o600)
    access.audit(conn, who.username, "document", None, "texts exported",
                 {"documents": [d["id"] for d in docs], "format": fmt, "written": written})
    return {"path": str(path), "documents": len(docs), "written": written}


# ── history ─────────────────────────────────────────────────────────────


def document_history(conn, who: access.Person, doc_id) -> dict:
    """Every check on a document (a student sees their released ones)."""
    doc = _visible(conn, who, doc_id)
    sql = ("SELECT r.id, r.check_date, r.similarity_score, r.paraphrase_score, "
           "r.obfuscated_chars, r.status, r.review_status, r.reviewed_by, r.reviewed_at, "
           "r.case_id, r.released_to_student, r.threshold_used, r.external_checked_at, "
           "u.username AS checked_by FROM plagiarism_results r LEFT JOIN users u ON "
           "u.id = r.checked_by WHERE r.document_id = ?")
    if who.is_student:
        sql += " AND r.released_to_student = 1"
    results = access.dicts(conn.execute(sql + " ORDER BY r.id DESC", (doc["id"],)))
    for r in results:
        r["checked_by"] = r["checked_by"] or "automatic"
        r["sources"] = conn.execute("SELECT COUNT(*) FROM plagiarism_matches WHERE "
                                    "result_id = ? AND COALESCE(counted, 1) = 1",
                                    (r["id"],)).fetchone()[0]
        if who.is_student:
            r.pop("reviewed_by", None)
    if who.is_staff:
        access.audit(conn, who.username, "document", doc["id"], "history viewed")
    return {**_label(conn, who, doc), "results": results}


def student_history(conn, who: access.Person, student_id) -> dict:
    """A student's documents and checks on the modules ``who`` reviews
    (integrity officers: all, with their cases). Work on an assignment
    still marked anonymously is left out for everyone but officers, so
    searching by student number cannot undo the anonymity."""
    access.require(who.is_staff, "Student history is for staff")
    access.ensure(conn)
    student_id = str(student_id or "").strip()
    if not student_id:
        raise ValueError("Give the student number")
    officer = access.is_officer(conn, who)
    modules = access.taught_modules(conn, who)
    docs = []
    for d in access.dicts(conn.execute("SELECT * FROM document_repository WHERE student_id = ? "
                                       "AND kind = 'submission' ORDER BY id DESC",
                                       (student_id,))):
        if modules is not None and d["module_code"] not in modules:
            continue
        if not officer and access.anonymised(conn, d["assignment_id"]):
            continue
        latest = access.one(conn, "SELECT id, similarity_score, status, review_status, case_id, "
                                  "check_date FROM plagiarism_results WHERE document_id = ? "
                                  "ORDER BY id DESC LIMIT 1", (d["id"],))
        checks_run = conn.execute("SELECT COUNT(*) FROM plagiarism_results WHERE "
                                  "document_id = ?", (d["id"],)).fetchone()[0]
        docs.append({"id": d["id"], "title": d["title"], "module_code": d["module_code"],
                     "assignment_id": d["assignment_id"], "submitted": d["submission_date"],
                     "words": d["word_count"], "checks": checks_run, "latest": latest})
    cases = review.history(conn, who, student_id) if officer else []
    access.audit(conn, who.username, "student", student_id, "history viewed",
                 {"documents": len(docs)})
    return {"student_id": student_id, "documents": docs, "cases": cases}


# ── statistics and reports ──────────────────────────────────────────────


def _scope(conn, who, column="d.module_code"):
    modules = access.taught_modules(conn, who)
    if modules is None:
        return "", []
    return f" AND {column} IN ({','.join('?' * len(modules)) or 'NULL'})", list(modules)


def _period(date_from, date_to, column="r.check_date"):
    sql, params = "", []
    if date_from:
        sql += f" AND substr({column}, 1, 10) >= ?"
        params.append(checks._day(date_from, "From date"))
    if date_to:
        sql += f" AND substr({column}, 1, 10) <= ?"
        params.append(checks._day(date_to, "To date"))
    return sql, params


def statistics_detail(conn, who: access.Person, date_from=None, date_to=None) -> dict:
    """Figures over the checks on modules ``who`` reviews."""
    access.require(who.is_staff, "Statistics are for staff")
    access.ensure(conn)
    scope, sp = _scope(conn, who)
    period, pp = _period(date_from, date_to)
    base = ("FROM plagiarism_results r JOIN document_repository d ON d.id = r.document_id "
            f"WHERE 1 = 1{scope}{period}")
    params = sp + pp

    def rows(sql, extra=()):
        return access.dicts(conn.execute(sql, [*params, *extra]))

    overview = rows("SELECT COUNT(*) AS checks, COUNT(DISTINCT r.document_id) AS documents, "
                    "AVG(r.similarity_score) AS average, "
                    "SUM(r.review_status = 'pending') AS waiting, "
                    "SUM(r.review_status = 'referred') AS referred, "
                    "SUM(r.review_status IN ('no_concern', 'false_positive')) AS cleared " + base)[0]
    dscope, dsp = _scope(conn, who, "module_code")
    kinds = dict(conn.execute(f"SELECT kind, COUNT(*) FROM document_repository WHERE 1 = 1"
                              f"{dscope} GROUP BY kind", dsp).fetchall())  # nosec B608
    return {
        "overview": {**overview, "repository": kinds},
        "by_band": rows("SELECT r.status AS band, COUNT(*) AS checks " + base +
                        " GROUP BY r.status ORDER BY checks DESC"),
        "by_module": rows("SELECT d.module_code AS module, COUNT(*) AS checks, "
                          "COUNT(DISTINCT r.document_id) AS documents, "
                          "AVG(r.similarity_score) AS average, "
                          "SUM(r.status = 'HIGH') AS high, "
                          "SUM(r.review_status = 'pending') AS waiting, "
                          "SUM(r.review_status = 'referred') AS referred " + base +
                          " GROUP BY d.module_code ORDER BY checks DESC"),
        "by_month": rows("SELECT substr(r.check_date, 1, 7) AS month, COUNT(*) AS checks, "
                         "SUM(r.review_status <> 'not_needed') AS needing_review, "
                         "AVG(r.similarity_score) AS average " + base +
                         " GROUP BY month ORDER BY month"),
        "by_file_type": rows("SELECT d.file_type, COUNT(*) AS checks, "
                             "AVG(r.similarity_score) AS average " + base +
                             " GROUP BY d.file_type ORDER BY checks DESC"),
        "recent": [{**r, "student_id": access.student_label(conn, who, r["student_id"],
                                                             r["assignment_id"])}
                   for r in rows("SELECT r.id, d.title, d.student_id, d.assignment_id, "
                                 "d.module_code, r.similarity_score, r.status, r.review_status, "
                                 "r.check_date " + base + " ORDER BY r.id DESC LIMIT 10")],
    }


def repository_health(conn, who: access.Person) -> dict:
    """Problems in the repository (integrity officers)."""
    access.require(access.is_officer(conn, who), "Only an integrity officer can check this")
    access.ensure(conn)

    def ids(sql):
        return [r[0] for r in conn.execute(sql).fetchall()]

    return {
        "orphaned_results": ids("SELECT r.id FROM plagiarism_results r LEFT JOIN "
                                "document_repository d ON d.id = r.document_id "
                                "WHERE d.id IS NULL"),
        "orphaned_matches": ids("SELECT m.match_id FROM plagiarism_matches m LEFT JOIN "
                                "plagiarism_results r ON r.id = m.result_id WHERE r.id IS NULL"),
        "dangling_sources": ids("SELECT m.match_id FROM plagiarism_matches m LEFT JOIN "
                                "document_repository d ON d.id = m.matched_document_id "
                                "WHERE m.matched_document_id IS NOT NULL AND d.id IS NULL"),
        "empty_documents": ids("SELECT id FROM document_repository WHERE COALESCE(purged, 0) = "
                               "0 AND TRIM(COALESCE(content, '')) = ''"),
        "unknown_authors": ids("SELECT d.id FROM document_repository d LEFT JOIN users u ON "
                               "u.id = d.author_id WHERE u.id IS NULL"),
        "duplicate_texts": [
            {"hash": h, "documents": [int(x) for x in str(docs).split(",")]}
            for h, docs in conn.execute(
                "SELECT content_hash, GROUP_CONCAT(id) FROM document_repository WHERE "
                "COALESCE(purged, 0) = 0 AND COALESCE(content_hash, '') <> '' GROUP BY "
                "content_hash HAVING COUNT(*) > 1").fetchall()],
        "checked_at": access.now(),
    }


def fix_repository(conn, who: access.Person) -> dict:
    """Remove orphaned results and matches, clear links to deleted sources
    and delete empty documents that nothing refers to. Unknown authors and
    duplicate texts are left for a person to look at."""
    found = repository_health(conn, who)
    fixed = {"orphaned_results": 0, "orphaned_matches": 0, "dangling_sources": 0,
             "empty_documents": 0}
    for result_id in found["orphaned_results"]:
        case = conn.execute("SELECT case_id FROM plagiarism_results WHERE id = ?",
                            (result_id,)).fetchone()
        if case and case[0]:
            continue
        conn.execute("DELETE FROM plagiarism_matches WHERE result_id = ?", (result_id,))
        conn.execute("DELETE FROM plagiarism_results WHERE id = ?", (result_id,))
        fixed["orphaned_results"] += 1
    for match_id in found["orphaned_matches"]:
        conn.execute("DELETE FROM plagiarism_matches WHERE match_id = ?", (match_id,))
        fixed["orphaned_matches"] += 1
    for match_id in found["dangling_sources"]:
        conn.execute("UPDATE plagiarism_matches SET matched_document_id = NULL WHERE "
                     "match_id = ?", (match_id,))
        fixed["dangling_sources"] += 1
    for doc_id in found["empty_documents"]:
        used = conn.execute("SELECT 1 FROM plagiarism_results WHERE document_id = ? OR "
                            "matched_document_id = ?", (doc_id, doc_id)).fetchone()
        if not used:
            conn.execute("DELETE FROM document_repository WHERE id = ?", (doc_id,))
            fixed["empty_documents"] += 1
    access.audit(conn, who.username, "repository", None, "repaired", fixed)
    return {**fixed, "left_for_review": {"unknown_authors": found["unknown_authors"],
                                         "duplicate_texts": found["duplicate_texts"]}}


def report(conn, who: access.Person, kind, date_from=None, date_to=None) -> dict:
    """A report as ``{"title", "columns", "rows", "notes"}``. Staff activity
    and repository health are for integrity officers."""
    if kind not in REPORTS:
        raise ValueError(f"report must be one of {', '.join(REPORTS)}")
    span = f"{date_from or 'the start'} to {date_to or 'today'}"
    if kind in ("summary", "trends", "modules"):
        stats = statistics_detail(conn, who, date_from, date_to)
        if kind == "summary":
            o = stats["overview"]
            rows = [["Checks", o["checks"] or 0], ["Documents checked", o["documents"] or 0],
                    ["Average similarity", f"{float(o['average'] or 0):.1%}"],
                    ["Waiting for review", o["waiting"] or 0], ["Referred", o["referred"] or 0],
                    ["Cleared on review", o["cleared"] or 0]]
            rows += [[f"Band: {b['band']}", b["checks"]] for b in stats["by_band"]]
            rows += [[f"Repository: {k}", v] for k, v in sorted(o["repository"].items())]
            columns = ["Measure", "Value"]
        elif kind == "trends":
            columns = ["Month", "Checks", "Needing review", "Average similarity"]
            rows = [[m["month"], m["checks"], m["needing_review"] or 0,
                     f"{float(m['average'] or 0):.1%}"] for m in stats["by_month"]]
        else:
            columns = ["Module", "Checks", "Documents", "Average similarity", "High",
                       "Waiting", "Referred"]
            rows = [[m["module"] or "—", m["checks"], m["documents"],
                     f"{float(m['average'] or 0):.1%}", m["high"] or 0, m["waiting"] or 0,
                     m["referred"] or 0] for m in stats["by_module"]]
    elif kind == "users":
        access.require(access.is_officer(conn, who), "Staff activity is for integrity officers")
        period, params = _period(date_from, date_to, "at")
        columns = ["Who", "Action", "Times", "Last"]
        rows = [list(r) for r in conn.execute(
            "SELECT actor, action, COUNT(*), MAX(at) FROM integrity_audit WHERE 1 = 1"
            f"{period} GROUP BY actor, action ORDER BY actor, COUNT(*) DESC",  # nosec B608
            params)]
    else:
        found = repository_health(conn, who)
        columns, span = ["Problem", "Count", "Items"], f"as at {found['checked_at']}"
        rows = [[k.replace("_", " "), len(v), ", ".join(str(x if not isinstance(x, dict)
                                                           else x["documents"]) for x in v[:20])]
                for k, v in found.items() if k != "checked_at"]
    access.audit(conn, who.username, "report", kind, "generated",
                 {"from": date_from, "to": date_to, "rows": len(rows)})
    return {"title": f"Academic integrity — {REPORTS[kind]}", "columns": columns, "rows": rows,
            "notes": f"{span}. Generated {access.now()} by {who.username}."}


def render(rep, fmt) -> bytes:
    """A report from :func:`report` (or :func:`export_report`) as CSV, HTML
    or PDF."""
    if fmt not in REPORT_FORMATS:
        raise ValueError(f"format must be one of {', '.join(REPORT_FORMATS)}")
    if fmt == "csv":
        out = io.StringIO()
        writer = csv.writer(out)
        writer.writerow([rep["title"]])
        writer.writerow([rep["notes"]])
        writer.writerow(rep["columns"])
        writer.writerows(rep["rows"])
        return out.getvalue().encode("utf-8")
    if fmt == "html":
        head = "".join(f"<th>{html.escape(str(c))}</th>" for c in rep["columns"])
        body = "".join("<tr>" + "".join(f"<td>{html.escape(str(v))}</td>" for v in r) + "</tr>"
                       for r in rep["rows"])
        extra = rep.get("html_extra", "")
        return ("<!doctype html><html><head><meta charset='utf-8'><title>"
                f"{html.escape(rep['title'])}</title><style>table{{border-collapse:collapse}}"
                "td,th{border:1px solid #999;padding:4px 8px;text-align:left}</style></head>"
                f"<body><h1>{html.escape(rep['title'])}</h1><p>{html.escape(rep['notes'])}</p>"
                f"<table><tr>{head}</tr>{body}</table>{extra}</body></html>").encode("utf-8")
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except ImportError:
        raise ValueError("PDF needs the reportlab package; save as HTML or CSV") from None
    buffer = io.BytesIO()
    styles = getSampleStyleSheet()
    wide = len(rep["columns"]) > 4
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4) if wide else A4,
                            title=rep["title"])
    cell = styles["BodyText"]
    data = [[Paragraph(f"<b>{html.escape(str(c))}</b>", cell) for c in rep["columns"]]]
    data += [[Paragraph(html.escape(str(v)), cell) for v in r] for r in rep["rows"]]
    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                               ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eeeeee")),
                               ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story = [Paragraph(html.escape(rep["title"]), styles["Title"]),
             Paragraph(html.escape(rep["notes"]), cell), Spacer(1, 8), table]
    for para in rep.get("paragraphs", []):
        story += [Spacer(1, 6), Paragraph(html.escape(para), cell)]
    doc.build(story)
    return buffer.getvalue()


# ── a similarity report by e-mail or as a file ──────────────────────────


def _report_rows(detail) -> list[list]:
    return [["Work", detail["title"]], ["Module", detail.get("module_code") or "—"],
            ["Checked", detail.get("check_date")],
            ["Similarity", f"{float(detail.get('similarity_score') or 0):.0%}"],
            ["Reworded", f"{float(detail.get('paraphrase_score') or 0):.0%}"],
            ["Disguised characters", detail.get("obfuscated_chars") or 0],
            ["Band", detail.get("status")], ["Review", detail.get("review_status")]]


def export_report(conn, who: access.Person, result_id, fmt="html") -> bytes:
    """A similarity report as a file: its figures, each source by kind and
    the checked document's own matching passages — never a source's text."""
    detail = review.result_detail(conn, who, result_id)
    rows = _report_rows(detail)
    paragraphs = []
    for m in detail["matches"]:
        rows.append([f"Source ({m.get('match_kind', 'exact')}"
                     f"{'' if m.get('counted', True) else ', not counted'})",
                     f"{float(m['score']):.0%} — {m['source']}"])
        paragraphs += [f"“{p['text']}”" for p in m["passages"]]
    rep = {"title": f"Similarity report {result_id}", "columns": ["", ""], "rows": rows,
           "notes": f"{detail.get('report') or ''} Exported {access.now()} by {who.username}.",
           "paragraphs": paragraphs,
           "html_extra": "<h2>Matching passages in this work</h2>" + "".join(
               f"<blockquote>{html.escape(p)}</blockquote>" for p in paragraphs)}
    access.audit(conn, who.username, "result", result_id, "exported", {"format": fmt})
    if fmt == "csv":
        rep["rows"] = rows + [["Passage", p] for p in paragraphs]
    return render(rep, fmt)


def email_report(conn, who: access.Person, result_id, recipient="me", note="") -> list[tuple]:
    """E-mail a summary of a similarity report: to the signed-in person, or
    (staff) to the student once the report is released to them. The mail
    carries the figures and the kinds of source, not the passages."""
    detail = review.result_detail(conn, who, result_id)
    if recipient == "me":
        address = access.email_of(conn, who.username)
        if not address:
            raise ValueError("There is no e-mail address on your account")
    elif recipient == "student":
        access.require(who.is_staff, "Only staff can send a report to the student")
        raw = review._result(conn, result_id)
        if not raw["released_to_student"]:
            raise ValueError("This report has not been released to the student yet")
        address = review._student_email(conn, raw["student_id"])
        if not address:
            raise ValueError("There is no e-mail address for this student")
    else:
        raise ValueError("Send the report to 'me' or 'student'")
    sources = "\n".join(f"  - {float(m['score']):.0%}: {m['source']}"
                        + ("" if m.get("counted", True) else " (not counted)")
                        for m in detail["matches"]) or "  (none)"
    body = "\n".join(f"{k}: {v}" for k, v in _report_rows(detail))
    body += f"\n\nMatched sources:\n{sources}\n"
    if str(note or "").strip():
        body += f"\nNote from {who.username}: {note.strip()}\n"
    body += ("\nThe full report, with your matching passages highlighted, is in the University "
             "app under Academic Integrity.")
    access.audit(conn, who.username, "result", result_id, "e-mailed", {"to": recipient})
    return [(address, f"Similarity report: {detail['title']}", body)]


def original_file(conn, who: access.Person, doc_id) -> dict:
    """The file the student uploaded for a document, if it is still there."""
    doc = _visible(conn, who, doc_id)
    if not doc.get("submission_id"):
        raise ValueError("This document was not uploaded with an assignment submission")
    row = conn.execute("SELECT file_path, file_name FROM assignment_submissions WHERE id = ?",
                       (doc["submission_id"],)).fetchone()
    if not row or not row[0] or not os.path.isfile(row[0]):
        raise ValueError("The uploaded file is no longer on the server")
    access.audit(conn, who.username, "document", doc["id"], "file opened")
    return {"path": row[0], "name": row[1] or os.path.basename(row[0])}


def as_json(data) -> str:
    return json.dumps(data, default=str, indent=1)


def today() -> str:
    return datetime.now().strftime("%Y-%m-%d")
