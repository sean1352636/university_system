"""Academic integrity API: similarity reports, reviews, cases and appeals.

Every route needs a signed-in user. The caller is the token's user; what
they may see and do is decided by ``application/integrity/access`` (a
student sees only their own released reports and cases; module staff and
reviewers the modules they review; integrity officers the cases).

Students:

* ``GET  /integrity/notice`` – the notice and whether it is acknowledged;
  ``POST /integrity/notice`` acknowledges it.
* ``GET  /integrity/results`` and ``GET /integrity/results/<id>`` – own
  released reports, with their own matching passages only.
* ``POST /integrity/draft-check`` ``{"text", "module_code"?}`` – a draft
  check (three a day, nothing stored).
* ``GET  /integrity/cases``, ``GET /integrity/cases/<id>``,
  ``POST /integrity/cases/<id>/appeal`` ``{"grounds"}``.
* ``GET  /integrity/cases/<id>/statements``; ``POST`` ``{"statement"}`` sends
  the student's account while the case is undecided.
* ``GET  /integrity/cases/<id>/evidence`` (the items the caller may see) and
  ``GET /integrity/evidence/<id>/file`` (the file itself).

Staff: ``GET /integrity/results?review_status=pending`` (the review queue),
``GET /integrity/results/<id>`` (both sides of each passage) and
``POST /integrity/results/<id>/review`` ``{"decision", "note", "case_type"?}``;
``GET /integrity/failed-checks``, ``POST /integrity/failed-checks/<submission>/text``
``{"text", "file_type"?}`` (check by hand) and ``/dismiss`` ``{"note"}``;
AI-writing readings (indicators, never evidence): ``GET /integrity/ai/readings``
(role-scoped: staff their modules, a student their own released readings;
``?flagged=1`` for those at the review strength, ``&include_reviewed=1``,
``&module_code=``), ``GET /integrity/ai/readings/<id>``, ``POST
/integrity/ai/readings`` (staff: ``{"submission_id"}`` or ``{"student_id",
"module_code", "text", "assignment_id"?, "title"?}``), ``POST
/integrity/ai/readings/<id>/review`` ``{"decision", "note", "case_type"?}`` and
``POST /integrity/ai/readings/<id>/comments`` ``{"comment"}`` (the student or
the module's staff). ``/integrity/ai-flags`` and ``/ai-flags/<id>/review``
remain as aliases;
``GET /integrity/documents`` (staff: the repository, filtered by
``module_code``, ``kind``, ``file_type``, ``min_words``, ``max_words``,
``date_from``, ``date_to``, ``student``, ``author``, ``search``; students:
their own work), ``GET /integrity/documents/export`` (the same filters, as
CSV — metadata only, audited);
``POST /integrity/documents/<id>/external-search`` (when allowed);
``POST /integrity/cases/<id>/evidence`` — JSON ``{"kind": "note" | "meeting_record",
"title", "detail", "visible_to_student"?, "internal_reason"?}``, or multipart with
a ``file`` and ``title`` / ``detail`` fields — for the staff who raised the case.

Integrity officers: ``POST /integrity/cases/<id>/advance`` ``{"stage",
"note"}``, ``/decide`` ``{"outcome", "note", "departure_reason"?}``, ``/close``
``{"note"}``, ``/response-due`` ``{"date", "reason"}``,
``POST /integrity/evidence/<id>/withdraw`` ``{"reason"}``,
``GET /integrity/students/<student_id>/history``,
``POST /integrity/external-sources`` ``{"title", "text", "url"?}`` and
``POST /integrity/appeals/<id>/decide`` ``{"upheld", "note"}``.

Tools (``application/integrity/tools``; staff, scoped to their modules):
``POST /integrity/documents/compare`` ``{"a", "b"}``; ``POST
/integrity/documents/import`` (multipart ``files`` plus ``kind``,
``module_code``, ``assignment_id``?, ``check``?); ``POST
/integrity/documents/bulk-check`` ``{"ids"}``; ``POST
/integrity/documents/bulk-delete`` ``{"ids", "reason"}`` (officers); ``POST
/integrity/documents/export-texts`` ``{"ids", "format"}`` (a ZIP); ``GET
/integrity/documents/<id>/history``; ``GET
/integrity/students/<id>/check-history``; ``GET /integrity/statistics/detail``
(``date_from``/``date_to``); ``GET /integrity/reports/<kind>?format=csv|html|pdf``;
``GET /integrity/repository/health`` and ``POST /integrity/repository/fix``
(officers); ``GET /integrity/results/<id>/export?format=…`` and ``POST
/integrity/results/<id>/email`` ``{"recipient": "me" | "student", "note"?}``
(also students, for their own released reports).

E-mails the rules return are sent after the transaction commits.
"""

from __future__ import annotations

import logging

import os
import tempfile

from flask import Blueprint, g, jsonify, request, send_file

from education_system.platform.delivery.api.rate_limiter import rate_limiter
from education_system.platform.delivery.api.university.auth import token_required
from education_system.systems.university.application.integrity import access
from education_system.systems.university.application.integrity import ai as integrity_ai
from education_system.systems.university.application.integrity import evidence
from education_system.systems.university.application.integrity import (
    external as integrity_external,
)
from education_system.systems.university.application.integrity import review
from education_system.systems.university.application.integrity import tools as integrity_tools
from education_system.systems.university.application.integrity import plagiarism_checks as checks
from education_system.systems.university.infrastructure.database.db import get_connection

logger = logging.getLogger(__name__)

academic_integrity_bp = Blueprint("academic_integrity", __name__, url_prefix="/api/integrity")


def _person(conn):
    user = g.get("current_user") or {}
    name = user.get("username") or user.get("sub")
    if not name:
        return None
    who = access.person(conn, name, str(user.get("role") or ""))
    if who.user_id is None:
        row = conn.execute("SELECT username FROM users WHERE student_id = ?", (name,)).fetchone()
        if row:
            who = access.person(conn, row[0], str(user.get("role") or ""))
    return who if who.user_id is not None else None


def _send(emails) -> None:
    if emails:
        from education_system.systems.university.infrastructure.ui.record_screens import (
            send_emails,
        )
        send_emails(emails)


def _call(fn, status=200):
    """Run ``fn(conn, who)``; commit; send any e-mails it returned in
    ``{"emails": [...]}`` or as a list of tuples."""
    conn = get_connection(row_factory=False)
    try:
        access.ensure(conn)
        who = _person(conn)
        if who is None:
            return jsonify({"error": "Sign in again"}), 401
        result = fn(conn, who)
        conn.commit()
    except PermissionError as exc:
        conn.rollback()
        return jsonify({"error": str(exc)}), 403
    except ValueError as exc:
        conn.rollback()
        return jsonify({"error": str(exc)}), 400
    except Exception:
        conn.rollback()
        logger.exception("integrity request failed")
        return jsonify({"error": "Something went wrong"}), 500
    finally:
        conn.close()
    emails = []
    if isinstance(result, dict) and "emails" in result:
        emails = result.pop("emails")
    elif isinstance(result, list) and all(isinstance(e, tuple) for e in result):
        emails, result = result, {"ok": True}
    _send(emails)
    return jsonify(result), status


def _body() -> dict:
    return request.get_json(silent=True) or {}


# ── students ────────────────────────────────────────────────────────────


@academic_integrity_bp.route("/notice", methods=["GET"])
@token_required
def notice():
    return _call(lambda conn, who: {**access.notice(conn),
                                    "acknowledged": access.has_acknowledged(conn, who)})


@academic_integrity_bp.route("/notice", methods=["POST"])
@token_required
def acknowledge_notice():
    def body(conn, who):
        access.acknowledge(conn, who)
        return {"acknowledged": True}
    return _call(body)


@academic_integrity_bp.route("/results", methods=["GET"])
@token_required
def list_results():
    args = request.args
    return _call(lambda conn, who: {"results": review.results(
        conn, who, review_status=args.get("review_status") or None,
        module_code=args.get("module_code") or None,
        assignment_id=args.get("assignment_id", type=int))})


@academic_integrity_bp.route("/results/<int:result_id>", methods=["GET"])
@token_required
def get_result(result_id: int):
    return _call(lambda conn, who: review.result_detail(conn, who, result_id))


@academic_integrity_bp.route("/draft-check", methods=["POST"])
@token_required
@rate_limiter.limit("10/hour")
def draft_check():
    data = _body()
    text = str(data.get("text") or "")[:400000]
    return _call(lambda conn, who: checks.self_check(
        conn, who, text=text, module_code=data.get("module_code") or None,
        assignment_id=data.get("assignment_id")))


@academic_integrity_bp.route("/cases", methods=["GET"])
@token_required
def list_cases():
    stage = request.args.get("stage") or None
    return _call(lambda conn, who: {"cases": review.cases(conn, who, stage=stage)})


@academic_integrity_bp.route("/cases/<int:case_id>", methods=["GET"])
@token_required
def get_case(case_id: int):
    return _call(lambda conn, who: review.case(conn, who, case_id))


@academic_integrity_bp.route("/cases/<int:case_id>/appeal", methods=["POST"])
@token_required
def appeal(case_id: int):
    grounds = str(_body().get("grounds") or "")
    return _call(lambda conn, who: review.lodge_appeal(conn, who, case_id, grounds), 201)


# ── staff ───────────────────────────────────────────────────────────────


@academic_integrity_bp.route("/results/<int:result_id>/review", methods=["POST"])
@token_required
def review_result(result_id: int):
    data = _body()
    return _call(lambda conn, who: review.review(
        conn, who, result_id, str(data.get("decision") or ""), str(data.get("note") or ""),
        case_type=str(data.get("case_type") or "plagiarism")))


# ── integrity officers ──────────────────────────────────────────────────


@academic_integrity_bp.route("/cases/<int:case_id>/advance", methods=["POST"])
@token_required
def advance_case(case_id: int):
    data = _body()
    return _call(lambda conn, who: review.advance(conn, who, case_id,
                                                  str(data.get("stage") or ""),
                                                  str(data.get("note") or "")))


@academic_integrity_bp.route("/cases/<int:case_id>/decide", methods=["POST"])
@token_required
def decide_case(case_id: int):
    data = _body()
    return _call(lambda conn, who: review.decide(
        conn, who, case_id, str(data.get("outcome") or ""), str(data.get("note") or ""),
        departure_reason=data.get("departure_reason") or None))


@academic_integrity_bp.route("/cases/<int:case_id>/close", methods=["POST"])
@token_required
def close_case(case_id: int):
    note = str(_body().get("note") or "")

    def body(conn, who):
        review.close(conn, who, case_id, note)
        return {"closed": True}
    return _call(body)


@academic_integrity_bp.route("/appeals/<int:appeal_id>/decide", methods=["POST"])
@token_required
def decide_appeal(appeal_id: int):
    data = _body()
    return _call(lambda conn, who: review.decide_appeal(conn, who, appeal_id,
                                                        bool(data.get("upheld")),
                                                        str(data.get("note") or "")))


# ── statements and evidence ─────────────────────────────────────────────


@academic_integrity_bp.route("/cases/<int:case_id>/statements", methods=["GET"])
@token_required
def list_statements(case_id: int):
    return _call(lambda conn, who: {"statements": evidence.statements(conn, who, case_id)})


@academic_integrity_bp.route("/cases/<int:case_id>/statements", methods=["POST"])
@token_required
def send_statement(case_id: int):
    text = str(_body().get("statement") or "")
    return _call(lambda conn, who: evidence.submit_statement(conn, who, case_id, text), 201)


@academic_integrity_bp.route("/cases/<int:case_id>/evidence", methods=["GET"])
@token_required
def list_evidence(case_id: int):
    def body(conn, who):
        rows = evidence.evidence(conn, who, case_id)
        for r in rows:
            r.pop("file_path", None)
        return {"evidence": rows}
    return _call(body)


@academic_integrity_bp.route("/cases/<int:case_id>/evidence", methods=["POST"])
@token_required
def add_evidence(case_id: int):
    upload = request.files.get("file")
    data = request.form if upload else _body()
    visible = str(data.get("visible_to_student", "true")).lower() not in ("0", "false", "no")
    temp_path = None
    if upload:
        from education_system.paths import UNIVERSITY_TEMP_DIR
        UNIVERSITY_TEMP_DIR.mkdir(parents=True, exist_ok=True)
        name = os.path.basename(upload.filename or "evidence")
        folder = tempfile.mkdtemp(dir=UNIVERSITY_TEMP_DIR)
        temp_path = os.path.join(folder, name)
        upload.save(temp_path)
    try:
        return _call(lambda conn, who: {"evidence_id": evidence.add_evidence(
            conn, who, case_id, kind="file" if upload else str(data.get("kind") or ""),
            title=str(data.get("title") or ""), detail=str(data.get("detail") or ""),
            file_path=temp_path, visible_to_student=visible,
            internal_reason=str(data.get("internal_reason") or ""))}, 201)
    finally:
        if temp_path:
            try:
                os.remove(temp_path)
                os.rmdir(os.path.dirname(temp_path))
            except OSError:
                logger.debug("Temporary evidence upload not removed", exc_info=True)


@academic_integrity_bp.route("/evidence/<int:evidence_id>/file", methods=["GET"])
@token_required
def evidence_file(evidence_id: int):
    conn = get_connection(row_factory=False)
    try:
        access.ensure(conn)
        who = _person(conn)
        if who is None:
            return jsonify({"error": "Sign in again"}), 401
        found = evidence.evidence_file(conn, who, evidence_id)
        conn.commit()       # the audit row
    except PermissionError as exc:
        conn.rollback()
        return jsonify({"error": str(exc)}), 403
    except ValueError as exc:
        conn.rollback()
        return jsonify({"error": str(exc)}), 404
    finally:
        conn.close()
    response = send_file(found["path"], as_attachment=True, download_name=found["name"])
    response.headers["X-Evidence-Intact"] = "yes" if found["intact"] else "no"
    return response


@academic_integrity_bp.route("/evidence/<int:evidence_id>/withdraw", methods=["POST"])
@token_required
def withdraw_evidence(evidence_id: int):
    reason = str(_body().get("reason") or "")

    def body(conn, who):
        evidence.withdraw_evidence(conn, who, evidence_id, reason)
        return {"withdrawn": True}
    return _call(body)


@academic_integrity_bp.route("/cases/<int:case_id>/response-due", methods=["POST"])
@token_required
def response_due(case_id: int):
    data = _body()
    return _call(lambda conn, who: evidence.set_response_due(
        conn, who, case_id, str(data.get("date") or ""), str(data.get("reason") or "")))


@academic_integrity_bp.route("/students/<student_id>/history", methods=["GET"])
@token_required
def student_history(student_id: str):
    return _call(lambda conn, who: {"cases": review.history(conn, who, student_id)})


# ── failed checks, AI flags, external sources ───────────────────────────


@academic_integrity_bp.route("/failed-checks", methods=["GET"])
@token_required
def failed_checks():
    every = request.args.get("all") in ("1", "true")
    return _call(lambda conn, who: {"failed": checks.failures(conn, who,
                                                               include_resolved=every)})


@academic_integrity_bp.route("/failed-checks/<int:submission_id>/text", methods=["POST"])
@token_required
def check_failed_by_hand(submission_id: int):
    data = _body()
    text = str(data.get("text") or "")[:400000]
    return _call(lambda conn, who: {"result_id": checks.check_by_hand(
        conn, who, submission_id, text, str(data.get("file_type") or "txt"))}, 201)


@academic_integrity_bp.route("/failed-checks/<int:submission_id>/dismiss", methods=["POST"])
@token_required
def dismiss_failed_check(submission_id: int):
    note = str(_body().get("note") or "")

    def body(conn, who):
        checks.dismiss_failure(conn, who, submission_id, note)
        return {"dismissed": True}
    return _call(body)


def _flag(name) -> bool:
    return request.args.get(name) in ("1", "true", "yes")


@academic_integrity_bp.route("/ai/readings", methods=["GET"])
@token_required
def ai_readings():
    module = request.args.get("module_code") or None

    def body(conn, who):
        if _flag("flagged"):
            rows = integrity_ai.flags(conn, who, include_reviewed=_flag("include_reviewed"))
            if module:
                rows = [r for r in rows if r["course_code"] == module]
        else:
            rows = integrity_ai.results(conn, who, module_code=module)
        return {"readings": rows, "notice": integrity_ai.NOTICE}
    return _call(body)


@academic_integrity_bp.route("/ai/readings/<int:ai_result_id>", methods=["GET"])
@token_required
def ai_reading(ai_result_id: int):
    return _call(lambda conn, who: integrity_ai.result_detail(conn, who, ai_result_id))


@academic_integrity_bp.route("/ai/readings", methods=["POST"])
@token_required
@rate_limiter.limit("60/hour")
def take_ai_reading():
    data = _body()

    def body(conn, who):
        if data.get("submission_id"):
            from education_system.systems.university.infrastructure.integrity import (
                text_extract,
            )
            sid = int(data["submission_id"])
            text, kind = text_extract.submission_text(conn, sid)
            result_id = integrity_ai.run_check(conn, who, text=text, module_code=None,
                                               submission_id=sid, file_type=kind)
        else:
            assignment = data.get("assignment_id")
            result_id = integrity_ai.run_check(
                conn, who, text=str(data.get("text") or "")[:400000],
                module_code=str(data.get("module_code") or ""),
                student_id=str(data.get("student_id") or ""),
                assignment_id=int(assignment) if assignment not in (None, "") else None,
                title=str(data.get("title") or ""))
        return {"reading_id": result_id}
    return _call(body, 201)


@academic_integrity_bp.route("/ai/readings/<int:ai_result_id>/comments", methods=["POST"])
@token_required
def comment_ai_reading(ai_result_id: int):
    text = str(_body().get("comment") or "")
    return _call(lambda conn, who: integrity_ai.comment(conn, who, ai_result_id, text), 201)


@academic_integrity_bp.route("/ai-flags", methods=["GET"])
@token_required
def ai_flags():
    every = request.args.get("all") in ("1", "true")
    return _call(lambda conn, who: {"flags": integrity_ai.flags(conn, who,
                                                                include_reviewed=every)})


@academic_integrity_bp.route("/ai/readings/<int:ai_result_id>/review", methods=["POST"])
@academic_integrity_bp.route("/ai-flags/<int:ai_result_id>/review", methods=["POST"])
@token_required
def review_ai_flag(ai_result_id: int):
    data = _body()
    return _call(lambda conn, who: integrity_ai.review_flag(
        conn, who, ai_result_id, str(data.get("decision") or ""), str(data.get("note") or ""),
        case_type=str(data.get("case_type") or "ai_misuse")))


def _document_filters() -> dict:
    return {key: request.args.get(key) for key in checks.DOCUMENT_FILTERS
            if request.args.get(key) not in (None, "")}


@academic_integrity_bp.route("/documents", methods=["GET"])
@token_required
def list_documents():
    filters = _document_filters()
    limit = min(request.args.get("limit", 500, type=int) or 500, 2000)
    return _call(lambda conn, who: {"documents": checks.documents(conn, who, limit=limit,
                                                                  **filters)})


@academic_integrity_bp.route("/documents/export", methods=["GET"])
@token_required
@rate_limiter.limit("30/hour")
def export_documents():
    filters = _document_filters()
    holder: dict = {}

    def body(conn, who):
        holder["csv"] = checks.export_documents(conn, who, **filters)
        return {"ok": True}
    response = _call(body)
    if "csv" not in holder or response[1] != 200:
        return response          # the refusal / error from _call
    from flask import Response
    return Response(holder["csv"], mimetype="text/csv", headers={
        "Content-Disposition": "attachment; filename=integrity_documents.csv"})


@academic_integrity_bp.route("/documents/<int:document_id>/external-search", methods=["POST"])
@token_required
@rate_limiter.limit("20/hour")
def external_search(document_id: int):
    return _call(lambda conn, who: integrity_external.search_external(conn, who, document_id))


@academic_integrity_bp.route("/external-sources", methods=["POST"])
@token_required
def add_external_source():
    data = _body()
    return _call(lambda conn, who: {"document_id": integrity_external.import_text(
        conn, who, title=str(data.get("title") or ""), content=str(data.get("text") or ""),
        source_url=data.get("url") or None)}, 201)


# ── tools ───────────────────────────────────────────────────────────────


def _file_response(build, mimetype, filename):
    """Run ``build(conn, who)`` for bytes and send them as a download, or
    the refusal from :func:`_call`."""
    holder: dict = {}

    def body(conn, who):
        holder["data"] = build(conn, who)
        return {"ok": True}
    response = _call(body)
    if "data" not in holder or response[1] != 200:
        return response
    from flask import Response
    return Response(holder["data"], mimetype=mimetype,
                    headers={"Content-Disposition": f"attachment; filename={filename}"})


_MIME = {"csv": "text/csv", "html": "text/html", "pdf": "application/pdf"}


@academic_integrity_bp.route("/documents/compare", methods=["POST"])
@token_required
def compare_documents():
    data = _body()
    return _call(lambda conn, who: integrity_tools.compare(conn, who, int(data.get("a") or 0),
                                                           int(data.get("b") or 0)))


@academic_integrity_bp.route("/documents/import", methods=["POST"])
@token_required
@rate_limiter.limit("30/hour")
def import_documents():
    uploads = request.files.getlist("files")
    if not uploads:
        return jsonify({"error": "Send the files as multipart field 'files'"}), 400
    from education_system.paths import UNIVERSITY_TEMP_DIR
    UNIVERSITY_TEMP_DIR.mkdir(parents=True, exist_ok=True)
    folder = tempfile.mkdtemp(dir=UNIVERSITY_TEMP_DIR)
    paths = []
    try:
        for upload in uploads:
            path = os.path.join(folder, os.path.basename(upload.filename or "document.txt"))
            upload.save(path)
            paths.append(path)
        form = request.form
        assignment = form.get("assignment_id", type=int)
        check = str(form.get("check", "true")).lower() not in ("0", "false", "no")
        return _call(lambda conn, who: {"files": integrity_tools.import_files(
            conn, who, paths, kind=str(form.get("kind") or "submission"),
            module_code=form.get("module_code") or None, assignment_id=assignment,
            check=check)}, 201)
    finally:
        for path in paths:
            try:
                os.remove(path)
            except OSError:
                logger.debug("Temporary import file not removed", exc_info=True)
        try:
            os.rmdir(folder)
        except OSError:
            logger.debug("Temporary import folder not removed", exc_info=True)


@academic_integrity_bp.route("/documents/bulk-check", methods=["POST"])
@token_required
@rate_limiter.limit("30/hour")
def bulk_check_documents():
    ids = [int(i) for i in (_body().get("ids") or []) if str(i).isdigit()]
    return _call(lambda conn, who: {"results": integrity_tools.bulk_check(conn, who, ids)})


@academic_integrity_bp.route("/documents/bulk-delete", methods=["POST"])
@token_required
def bulk_delete_documents():
    data = _body()
    ids = [int(i) for i in (data.get("ids") or []) if str(i).isdigit()]
    return _call(lambda conn, who: {"results": integrity_tools.bulk_delete(
        conn, who, ids, str(data.get("reason") or ""))})


@academic_integrity_bp.route("/documents/export-texts", methods=["POST"])
@token_required
@rate_limiter.limit("20/hour")
def export_document_texts():
    data = _body()
    ids = [int(i) for i in (data.get("ids") or []) if str(i).isdigit()]
    fmt = str(data.get("format") or "txt")

    def build(conn, who):
        from education_system.paths import UNIVERSITY_TEMP_DIR
        UNIVERSITY_TEMP_DIR.mkdir(parents=True, exist_ok=True)
        fd, path = tempfile.mkstemp(suffix=".zip", dir=UNIVERSITY_TEMP_DIR)
        os.close(fd)
        try:
            integrity_tools.export_texts(conn, who, ids, path, fmt)
            with open(path, "rb") as fh:
                return fh.read()
        finally:
            os.remove(path)
    return _file_response(build, "application/zip", "integrity_documents.zip")


@academic_integrity_bp.route("/documents/<int:document_id>/history", methods=["GET"])
@token_required
def document_history(document_id: int):
    return _call(lambda conn, who: integrity_tools.document_history(conn, who, document_id))


@academic_integrity_bp.route("/students/<student_id>/check-history", methods=["GET"])
@token_required
def student_check_history(student_id: str):
    return _call(lambda conn, who: integrity_tools.student_history(conn, who, student_id))


@academic_integrity_bp.route("/statistics/detail", methods=["GET"])
@token_required
def statistics_detail():
    args = request.args
    return _call(lambda conn, who: integrity_tools.statistics_detail(
        conn, who, args.get("date_from") or None, args.get("date_to") or None))


@academic_integrity_bp.route("/reports/<kind>", methods=["GET"])
@token_required
def integrity_report(kind: str):
    args = request.args
    fmt = args.get("format") or "csv"
    if fmt not in _MIME:
        return jsonify({"error": "format must be csv, html or pdf"}), 400
    return _file_response(lambda conn, who: integrity_tools.render(integrity_tools.report(
        conn, who, kind, args.get("date_from") or None, args.get("date_to") or None), fmt),
        _MIME[fmt], f"integrity_{kind}.{fmt}")


@academic_integrity_bp.route("/repository/health", methods=["GET"])
@token_required
def repository_health():
    return _call(lambda conn, who: integrity_tools.repository_health(conn, who))


@academic_integrity_bp.route("/repository/fix", methods=["POST"])
@token_required
def repository_fix():
    return _call(lambda conn, who: integrity_tools.fix_repository(conn, who))


@academic_integrity_bp.route("/results/<int:result_id>/export", methods=["GET"])
@token_required
def export_result(result_id: int):
    fmt = request.args.get("format") or "pdf"
    if fmt not in _MIME:
        return jsonify({"error": "format must be csv, html or pdf"}), 400
    return _file_response(lambda conn, who: integrity_tools.export_report(conn, who, result_id,
                                                                         fmt),
                          _MIME[fmt], f"similarity_report_{result_id}.{fmt}")


@academic_integrity_bp.route("/results/<int:result_id>/email", methods=["POST"])
@token_required
@rate_limiter.limit("20/hour")
def email_result(result_id: int):
    data = _body()
    return _call(lambda conn, who: {"emails": integrity_tools.email_report(
        conn, who, result_id, str(data.get("recipient") or "me"), str(data.get("note") or "")),
        "sent": True})

