"""Student documents: the ``documents`` table the GUI's Document Manager uses.

These are passports, ID cards, transcripts and medical certificates, so "staff"
is not good enough to read them. The rule is the one in
``services/bus/document_bus.can_access``: the owner, whoever uploaded it, and
administrators. Instructors and other staff are refused. ``owner_id`` is TEXT
holding a student id, so it is compared with the caller's username and local
student id, never with the numeric central id in the token.

Uploads are stored as the GUI stores them, under
``uploads/student_documents/<student_id>/``, after the same
``validate_upload`` check, with the same version chain. The path on the server
and the file content are never returned. Downloads only serve files inside the
upload folder.

Routes (under ``/api/v1/university/documents``):

* ``GET   /types``                 the active document types
* ``GET   /``                      the caller's own; administrators may filter by
                                   ``owner_id`` and ``verification_status``
* ``POST  /``                      multipart ``file`` and ``type_id``; administrators
                                   may give ``student_id``
* ``GET   /<id>``                  details
* ``GET   /<id>/download``         the file
* ``PATCH /<id>/verification``     administrators
"""

from __future__ import annotations

import hashlib
import logging
import os
from datetime import datetime
from pathlib import Path

from flask import Blueprint, jsonify, request, send_file

from education_system import paths
from education_system.api.university import _identity
from education_system.platform.delivery.api.kernel.problems import problem
from education_system.platform.delivery.api.university.auth import (
    authorize_object,
    current_subject_id,
    token_required,
)
from education_system.platform.delivery.api.university.pagination import (
    get_pagination_params,
    paginated_response,
)
from education_system.platform.delivery.api.university.validators import (
    validate_enum,
    validate_positive_int,
    validate_string_length,
)
from education_system.systems.university.infrastructure.activity_logger import log_activity
from education_system.systems.university.infrastructure.database.db import get_connection
from education_system.systems.university.infrastructure.email.messages_inbox import (
    deliver_inbox_message_on,
)
from education_system.systems.university.infrastructure.security.file_upload import (
    validate_upload,
)
from education_system.systems.university.services.bus.document_bus import (
    publish_document_changed,
)

logger = logging.getLogger(__name__)

document_bp = Blueprint("documents", __name__, url_prefix="/api/documents")

_ADMIN_ROLES = {"admin", "superadmin"}
_STATUSES = {"Pending", "Verified", "Rejected", "Expired"}
#: Named columns: ``file_path`` and ``file_content`` must not leave the server.
_COLUMNS = ("document_id, owner_id, source_type, document_type, document_name, "
            "original_filename, file_size, file_hash, upload_date, expiry_date, "
            "status, verification_status, verification_date, verification_notes, "
            "verified_by, version_number, parent_document_id, is_current_version, "
            "workflow_status, tags, notes, uploaded_by")


def _is_document_admin() -> bool:
    return authorize_object(None, staff_roles=_ADMIN_ROLES) is None


def _fetch(document_id: int, *, columns: str = _COLUMNS):
    with get_connection() as conn:
        return conn.execute(
            f"SELECT {columns} FROM documents WHERE document_id = ?",  # nosec B608
            (document_id,)).fetchone()


def _deny_unless_document_reader(row):
    """403 unless the caller owns it, uploaded it, or is an administrator."""
    denied = authorize_object(current_subject_id())
    if denied is not None:
        return denied
    if _is_document_admin() or _identity.owns(row["owner_id"]) or \
            str(row["uploaded_by"] or "") == _identity.username():
        return None
    return problem(403, "You may not access this document.")


def _deny_unless_document_admin():
    """403 unless the caller is an administrator."""
    return authorize_object(None, staff_roles=_ADMIN_ROLES)


@document_bp.route("/types", methods=["GET"])
@token_required
def list_types():
    denied = authorize_object(current_subject_id())
    if denied is not None:
        return denied
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT type_id, type_name, description, is_required, has_expiry, "
            "max_file_size_mb, allowed_extensions, category FROM document_types "
            "WHERE COALESCE(is_active, 1) = 1 ORDER BY sort_order, type_name").fetchall()
    return jsonify({"items": [dict(r) for r in rows], "total": len(rows)})


@document_bp.route("", methods=["GET"])
@token_required
def list_documents():
    denied = authorize_object(current_subject_id())
    if denied is not None:
        return denied
    conditions, params = ["COALESCE(status, 'active') = 'active'"], []
    owner_filter = request.args.get("owner_id")
    if _is_document_admin():
        if owner_filter:
            conditions.append("owner_id = ?")
            params.append(owner_filter)
    else:
        # Pinned before anything the caller asked for.
        if owner_filter and not _identity.owns(owner_filter):
            return problem(403, "You may only list your own documents.")
        keys = sorted({_identity.username(), str(_identity.local_identity()[1] or "")} - {""})
        placeholders = ",".join("?" for _ in keys)
        conditions.append(f"(owner_id IN ({placeholders}) OR uploaded_by = ?)")
        params += [*keys, _identity.username()]
    status = request.args.get("verification_status")
    if status:
        try:
            validate_enum(status, "verification_status", _STATUSES)
        except ValueError as exc:
            return problem(400, str(exc))
        conditions.append("verification_status = ?")
        params.append(status)
    if request.args.get("all_versions", "").lower() not in {"1", "true", "yes"}:
        conditions.append("COALESCE(is_current_version, 1) = 1")
    where = " WHERE " + " AND ".join(conditions)
    page, per_page, offset = get_pagination_params()
    with get_connection() as conn:
        total = conn.execute("SELECT COUNT(*) FROM documents" + where, params).fetchone()[0]
        rows = conn.execute(
            f"SELECT {_COLUMNS} FROM documents" + where +  # nosec B608
            " ORDER BY upload_date DESC, document_id DESC LIMIT ? OFFSET ?",
            [*params, per_page, offset]).fetchall()
    return jsonify(paginated_response([dict(r) for r in rows], total, page, per_page))


@document_bp.route("", methods=["POST"])
@token_required
def upload_document():
    denied = authorize_object(current_subject_id())
    if denied is not None:
        return denied
    upload = request.files.get("file")
    if upload is None or not upload.filename:
        return problem(400, "A 'file' is required.")
    try:
        type_id = validate_positive_int(request.form.get("type_id"), "type_id")
    except (TypeError, ValueError) as exc:
        return problem(400, str(exc))
    notes = (request.form.get("notes") or "").strip() or None
    if notes:
        try:
            validate_string_length(notes, "notes", 1, 2000)
        except ValueError as exc:
            return problem(400, str(exc))

    student_id = (request.form.get("student_id") or "").strip()
    if student_id and not _identity.owns(student_id):
        denied = _deny_unless_document_admin()
        if denied is not None:
            return denied
    student_id = student_id or str(_identity.local_identity()[1] or "")
    if not student_id:
        return problem(400, "You have no student record, so a 'student_id' is required.")

    with get_connection() as conn:
        # Also what makes student_id safe as a folder name: it must be a real id.
        if not conn.execute("SELECT 1 FROM students WHERE student_id = ?",
                            (student_id,)).fetchone():
            return problem(404, "Student not found.")
        doc_type = conn.execute(
            "SELECT type_name, max_file_size_mb, allowed_extensions FROM document_types "
            "WHERE type_id = ? AND COALESCE(is_active, 1) = 1", (type_id,)).fetchone()
    if doc_type is None:
        return problem(404, "Document type not found.")

    content = upload.read()
    limit_mb = doc_type["max_file_size_mb"] or 10
    if len(content) > int(limit_mb) * 1024 * 1024:
        return problem(413, f"This document type is limited to {limit_mb} MB.")
    extension = os.path.splitext(upload.filename)[1].lower()
    allowed = {e.strip().lower() for e in (doc_type["allowed_extensions"] or "").split(",")
               if e.strip()}
    if allowed and extension not in allowed:
        return problem(400, f"Allowed file types: {', '.join(sorted(allowed))}.")
    validation = validate_upload(upload.filename, content, category="documents")
    if not validation.get("valid"):
        return problem(400, f"File rejected: {validation.get('error')}")

    root = Path(paths.UNIVERSITY_UPLOAD_DIR)
    folder = root / "student_documents" / student_id
    folder.mkdir(parents=True, exist_ok=True)
    folder.chmod(0o700)
    now = datetime.now()
    stored = folder / f"{now:%Y%m%d_%H%M%S_%f}_{validation['safe_filename']}"
    # O_EXCL so a clash fails rather than overwriting another upload.
    with os.fdopen(os.open(stored, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as handle:
        handle.write(content)

    upload_date = now.strftime("%Y-%m-%d %H:%M:%S")
    try:
        with get_connection() as conn:
            previous = conn.execute(
                "SELECT document_id, version_number FROM documents WHERE owner_id = ? "
                "AND source_type = 'student' AND document_type = ? AND is_current_version = 1",
                (student_id, str(type_id))).fetchone()
            if previous:
                conn.execute("UPDATE documents SET is_current_version = 0 WHERE document_id = ?",
                             (previous["document_id"],))
            document_id = conn.execute(
                "INSERT INTO documents (source_type, owner_id, document_type, document_name, "
                "file_path, original_filename, upload_date, verification_status, version_number, "
                "parent_document_id, uploaded_by, file_size, file_hash, notes, workflow_status, "
                "is_current_version, status) "
                "VALUES ('student', ?, ?, ?, ?, ?, ?, 'Pending', ?, ?, ?, ?, ?, ?, 'submitted', 1, 'active')",
                (student_id, str(type_id), doc_type["type_name"], str(stored), upload.filename,
                 upload_date, (previous["version_number"] + 1) if previous else 1,
                 previous["document_id"] if previous else None, _identity.username(),
                 len(content), hashlib.sha256(content).hexdigest(), notes)).lastrowid
            deliver_inbox_message_on(
                conn, student_id, "[Documents] Document Uploaded",
                "Your document has been uploaded and is pending verification.")
            conn.commit()
    except Exception:
        stored.unlink(missing_ok=True)
        logger.exception("Could not record an uploaded document")
        return problem(500, "The document could not be saved.")

    publish_document_changed(document_id=document_id, action="uploaded", domain="student",
                             ref_id=student_id, name=doc_type["type_name"])
    log_activity("create", "documents", user=_identity.username())
    return jsonify(dict(_fetch(document_id))), 201


@document_bp.route("/<int:document_id>", methods=["GET"])
@token_required
def get_document(document_id: int):
    row = _fetch(document_id)
    if row is None:
        # Only an administrator learns that an id does not exist; everyone else
        # gets the same 403 as for a document that is not theirs.
        denied = _deny_unless_document_admin()
        return denied if denied is not None else problem(404, "Document not found.")
    denied = _deny_unless_document_reader(row)
    if denied is not None:
        return denied
    log_activity("view", "documents", user=_identity.username())
    return jsonify(dict(row))


@document_bp.route("/<int:document_id>/download", methods=["GET"])
@token_required
def download_document(document_id: int):
    row = _fetch(document_id, columns="owner_id, uploaded_by, file_path, original_filename")
    if row is None:
        denied = _deny_unless_document_admin()
        return denied if denied is not None else problem(404, "Document not found.")
    denied = _deny_unless_document_reader(row)
    if denied is not None:
        return denied
    root = Path(paths.UNIVERSITY_UPLOAD_DIR).resolve()
    target = Path(row["file_path"] or "").resolve()
    # Linked documents can point anywhere (document_bus stores a path as given),
    # so a stored path is not trusted to stay inside the upload folder.
    if not row["file_path"] or not target.is_relative_to(root) or not target.is_file():
        return problem(404, "The file for this document is not available.")
    log_activity("view", "documents_download", user=_identity.username())
    return send_file(target, as_attachment=True, mimetype="application/octet-stream",
                     download_name=row["original_filename"] or target.name)


@document_bp.route("/<int:document_id>/verification", methods=["PATCH"])
@token_required
def update_verification(document_id: int):
    denied = _deny_unless_document_admin()
    if denied is not None:
        return denied
    data = request.get_json(silent=True) or {}
    status = data.get("verification_status")
    notes = str(data.get("notes") or "").strip()
    try:
        validate_enum(status, "verification_status", _STATUSES)
        if notes:
            validate_string_length(notes, "notes", 1, 2000)
    except (TypeError, ValueError) as exc:
        return problem(400, str(exc))
    with get_connection() as conn:
        changed = conn.execute(
            "UPDATE documents SET verification_status = ?, verification_date = ?, "
            "verification_notes = ?, verified_by = ?, updated_at = ? WHERE document_id = ?",
            (status, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), notes or None,
             _identity.username(), datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
             document_id)).rowcount
        conn.commit()
    if not changed:
        return problem(404, "Document not found.")
    publish_document_changed(document_id=document_id, action="verified")
    log_activity("update", "documents", user=_identity.username())
    return jsonify(dict(_fetch(document_id)))
