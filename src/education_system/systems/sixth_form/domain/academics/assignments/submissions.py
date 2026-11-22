"""Sixth Form coursework assignments — attachments, word limits, extensions,
submission versions and receipts.

Split out of ``assignments.py``, which re-exports every name defined here."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any
import datetime as _dt
import hashlib
import mimetypes
import shutil
import uuid
from education_system import paths
from education_system.systems.sixth_form.domain.academics.assignments.models import (
    ASSIGNMENT_ATTACHMENT_KINDS,
    Assignment,
    Attachment,
    BLOCKED_ATTACHMENT_SUFFIXES,
    DEFAULT_ASSIGNMENT_ATTACHMENT_KIND,
    DEFAULT_SUBMISSION_ATTACHMENT_KIND,
    MAX_ATTACHMENT_BYTES,
    SUBMISSION_ATTACHMENT_KINDS,
    Submission,
    SubmissionVersion,
    ValidationError,
    WORD_LIMIT_TOLERANCE,
    WordLimitCheck,
    _UNSAFE_FILENAME_RE,
    logger,
)
from education_system.systems.sixth_form.domain.academics.assignments.store import (
    _connect,
    _require,
    _row_attachment,
    _row_submission,
    _row_version,
    _unlink_stored,
    _validate_date,
    _validate_number,
    get_assignment,
    get_submission,
    init_db,
)

# ── Attachments ───────────────────────────────────────────────────

def _files_root() -> Path:
    root = paths.SIXTH_FORM_COURSEWORK_FILES_DIR
    root.mkdir(parents=True, exist_ok=True)
    return root


def _safe_filename(name: Any) -> str:
    """Reduce a user-supplied name to something safe to write to disk.

    Strips any directory component first — a browser upload can carry
    ``../../etc/passwd`` as its filename — then collapses everything
    outside ``[A-Za-z0-9._-]``.
    """
    stem = Path(str(name or "")).name.strip()
    cleaned = _UNSAFE_FILENAME_RE.sub("_", stem).strip("._-")
    return cleaned[:120] or "file"


def _check_attachment_name(filename: str) -> None:
    suffix = Path(filename).suffix.lower()
    if suffix in BLOCKED_ATTACHMENT_SUFFIXES:
        raise ValidationError(
            f"{suffix} files are not accepted as coursework attachments")


def _attachment_dir(*, assignment_id: int,
                     submission_id: int | None = None,
                     attempt_no: int | None = None) -> Path:
    """Relative directory (under the file root) for a new attachment."""
    if submission_id is None:
        return Path(f"assignment_{assignment_id}") / "material"
    leaf = ("attempt_%d" % attempt_no) if attempt_no else "loose"
    return (Path(f"assignment_{assignment_id}")
            / f"submission_{submission_id}" / leaf)


def _validate_attachment_kind(kind: Any, *, for_assignment: bool) -> str:
    allowed = (ASSIGNMENT_ATTACHMENT_KINDS if for_assignment
                else SUBMISSION_ATTACHMENT_KINDS)
    default = (DEFAULT_ASSIGNMENT_ATTACHMENT_KIND if for_assignment
                else DEFAULT_SUBMISSION_ATTACHMENT_KIND)
    value = (str(kind).strip() if kind not in (None, "") else default)
    if value not in allowed:
        raise ValidationError(
            f"Attachment kind must be one of: {', '.join(allowed)}")
    return value


def attach_file(*,
                 source_path: str | Path | None = None,
                 data: bytes | None = None,
                 filename: str | None = None,
                 assignment_id: int | None = None,
                 submission_id: int | None = None,
                 version_id: int | None = None,
                 kind: str | None = None,
                 uploaded_by: str | None = None,
                 notes: str | None = None) -> Attachment:
    """Copy a file into the coursework store and record its metadata.

    Give either ``source_path`` (a file on disk) or ``data`` (bytes,
    for an upload that never touched the filesystem) plus ``filename``.
    Exactly one of ``assignment_id`` / ``submission_id`` identifies the
    owner; ``version_id`` optionally pins the file to one attempt.

    The stored copy is content-hashed so a submission receipt can prove
    later that the file has not been swapped.
    """
    init_db()
    if (assignment_id is None) == (submission_id is None):
        raise ValidationError(
            "Attach to exactly one of an assignment or a submission")
    if (source_path is None) == (data is None):
        raise ValidationError(
            "Provide exactly one of source_path or data")

    if source_path is not None:
        src = Path(source_path).expanduser()
        if not src.is_file():
            raise ValidationError(f"No such file: {src}")
        size = src.stat().st_size
        name = filename or src.name
    else:
        assert data is not None
        size = len(data)
        if not filename:
            raise ValidationError("filename is required with data=")
        name = filename

    if size == 0:
        raise ValidationError("File is empty")
    if size > MAX_ATTACHMENT_BYTES:
        raise ValidationError(
            f"File is {size / 1048576:.1f} MB — the limit is "
            f"{MAX_ATTACHMENT_BYTES // 1048576} MB")

    safe = _safe_filename(name)
    _check_attachment_name(safe)

    # Resolve the owning assignment (and attempt) so the file lands in
    # a directory that mirrors the record structure.
    attempt_no: int | None = None
    if assignment_id is not None:
        if get_assignment(assignment_id) is None:
            raise ValidationError(f"No assignment #{assignment_id}")
        owning_assignment = assignment_id
        for_assignment = True
    else:
        sub = get_submission(int(submission_id))  # type: ignore[arg-type]
        if sub is None:
            raise ValidationError(f"No submission #{submission_id}")
        owning_assignment = sub.assignment_id
        for_assignment = False
        if version_id is not None:
            version = get_version(version_id)
            if version is None or version.submission_id != sub.submission_id:
                raise ValidationError(
                    f"Version #{version_id} does not belong to "
                    f"submission #{sub.submission_id}")
            attempt_no = version.attempt_no

    kind_value = _validate_attachment_kind(kind,
                                            for_assignment=for_assignment)

    rel_dir = _attachment_dir(assignment_id=owning_assignment,
                               submission_id=submission_id,
                               attempt_no=attempt_no)
    abs_dir = _files_root() / rel_dir
    abs_dir.mkdir(parents=True, exist_ok=True)
    # A uuid prefix keeps two students' "essay.docx" apart without
    # mangling the name staff see in the UI.
    stored_name = f"{uuid.uuid4().hex[:12]}_{safe}"
    dest = abs_dir / stored_name

    digest = hashlib.sha256()
    if source_path is not None:
        shutil.copyfile(Path(source_path).expanduser(), dest)
        with dest.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                digest.update(chunk)
    else:
        assert data is not None
        dest.write_bytes(data)
        digest.update(data)

    content_type = mimetypes.guess_type(safe)[0]
    rel_path = str(rel_dir / stored_name)

    try:
        with _connect() as conn:
            cur = conn.execute(
                """INSERT INTO coursework_attachments
                       (assignment_id, submission_id, version_id, kind,
                        filename, stored_path, byte_size, sha256,
                        content_type, uploaded_by, uploaded_at, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                           datetime('now'), ?)""",
                (assignment_id, submission_id, version_id, kind_value,
                 safe, rel_path, size, digest.hexdigest(),
                 content_type, (uploaded_by or "").strip() or None,
                 (notes or "").strip() or None),
            )
            conn.commit()
            new_id = int(cur.lastrowid or 0)
    except Exception:
        # Never leave bytes on disk with no row pointing at them.
        dest.unlink(missing_ok=True)
        raise

    out = get_attachment(new_id)
    assert out is not None
    logger.info("Attached %r (%d bytes, %s) to %s #%s",
                safe, size, kind_value,
                "assignment" if for_assignment else "submission",
                assignment_id if for_assignment else submission_id)
    return out


def get_attachment(attachment_id: int) -> Attachment | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM coursework_attachments WHERE attachment_id = ?",
            (attachment_id,)).fetchone()
        return _row_attachment(r) if r else None


def list_attachments(*,
                      assignment_id: int | None = None,
                      submission_id: int | None = None,
                      version_id: int | None = None,
                      kind: str | None = None) -> list[Attachment]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if assignment_id is not None:
        clauses.append("assignment_id = ?")
        args.append(int(assignment_id))
    if submission_id is not None:
        clauses.append("submission_id = ?")
        args.append(int(submission_id))
    if version_id is not None:
        clauses.append("version_id = ?")
        args.append(int(version_id))
    if kind:
        clauses.append("kind = ?")
        args.append(str(kind).strip())
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with _connect() as conn:
        return [_row_attachment(r) for r in conn.execute(
            f"SELECT * FROM coursework_attachments {where} "
            "ORDER BY attachment_id ASC", args).fetchall()]


def delete_attachment(attachment_id: int) -> bool:
    """Remove the metadata row and unlink the stored file."""
    init_db()
    existing = get_attachment(attachment_id)
    if existing is None:
        return False
    with _connect() as conn:
        conn.execute(
            "DELETE FROM coursework_attachments WHERE attachment_id = ?",
            (attachment_id,))
        conn.commit()
    _unlink_stored([existing.stored_path])
    logger.info("Deleted attachment #%d (%s)",
                attachment_id, existing.filename)
    return True


# ── Word limits ───────────────────────────────────────────────────

def check_word_limit(assignment: Assignment,
                      word_count: int | None) -> WordLimitCheck:
    """Compare a word count against the brief's limit.

    Over-limit never blocks a submission — boards expect the marker to
    apply the penalty — so this returns a report rather than raising.
    """
    limit = assignment.word_limit
    if limit is None or word_count is None:
        return WordLimitCheck(limit=limit, word_count=word_count)
    over = max(0, int(word_count) - int(limit))
    within = int(word_count) <= int(limit) * (1 + WORD_LIMIT_TOLERANCE)
    return WordLimitCheck(limit=int(limit), word_count=int(word_count),
                           over_by=over, within_tolerance=within)


def count_words(text: str) -> int:
    """Whitespace word count — the same rule most boards apply."""
    return len(str(text or "").split())


# ── Extensions ────────────────────────────────────────────────────

def effective_due_date(submission: Submission,
                        assignment: Assignment | None = None) -> str | None:
    """The date this student is actually held to.

    An approved extension replaces the assignment's due date for that
    student alone; everything downstream (lateness at submit time, the
    late sweep, the overdue report) reads through here.
    """
    if submission.extended_due_date:
        return submission.extended_due_date
    if assignment is None:
        assignment = get_assignment(submission.assignment_id)
    return assignment.due_date if assignment else None


def grant_extension(submission_id: int, new_due_date: str, *,
                     reason: str,
                     authorised_by: str | None = None) -> Submission:
    """Give one student a later deadline, with an audit trail.

    If the sweep had already written the student off as ``Missing``,
    a future extension puts them back in play.
    """
    init_db()
    sub = get_submission(submission_id)
    if sub is None:
        raise ValidationError(f"No submission #{submission_id}")
    new_date = _validate_date(new_due_date, "Extended due date",
                               required=True)
    assert new_date is not None    # required=True guarantees it
    reason_text = _require(reason, "Extension reason").strip()

    assignment = get_assignment(sub.assignment_id)
    if (assignment and assignment.due_date
            and new_date <= assignment.due_date):
        raise ValidationError(
            f"Extension ({new_date}) must be after the original due "
            f"date ({assignment.due_date})")

    today = _dt.date.today().isoformat()
    restore = (sub.status == "Missing" and new_date >= today)
    with _connect() as conn:
        conn.execute(
            """UPDATE coursework_submissions SET
                   extended_due_date = ?, extension_reason = ?,
                   extension_by = ?, extension_on = ?,
                   status = CASE WHEN ? THEN 'Not Started' ELSE status END,
                   updated_at = datetime('now')
               WHERE submission_id = ?""",
            (new_date, reason_text,
             (authorised_by or "").strip() or None, today,
             1 if restore else 0, submission_id))
        conn.commit()
    out = get_submission(submission_id)
    assert out is not None
    logger.info(
        "Extension granted on submission #%d (student %s) to %s by %s: %s",
        submission_id, out.student_id, new_date,
        authorised_by or "(unrecorded)", reason_text)
    return out


def revoke_extension(submission_id: int) -> Submission:
    """Withdraw an extension, restoring the assignment's own due date."""
    init_db()
    if get_submission(submission_id) is None:
        raise ValidationError(f"No submission #{submission_id}")
    with _connect() as conn:
        conn.execute(
            """UPDATE coursework_submissions SET
                   extended_due_date = NULL, extension_reason = NULL,
                   extension_by = NULL, extension_on = NULL,
                   updated_at = datetime('now')
               WHERE submission_id = ?""", (submission_id,))
        conn.commit()
    out = get_submission(submission_id)
    assert out is not None
    logger.info("Extension revoked on submission #%d", submission_id)
    return out


def list_extensions(*, assignment_id: int | None = None) -> list[Submission]:
    init_db()
    clauses = ["extended_due_date IS NOT NULL"]
    args: list[Any] = []
    if assignment_id is not None:
        clauses.append("assignment_id = ?")
        args.append(int(assignment_id))
    with _connect() as conn:
        return [_row_submission(r) for r in conn.execute(
            "SELECT * FROM coursework_submissions WHERE "
            + " AND ".join(clauses)
            + " ORDER BY extended_due_date ASC", args).fetchall()]


# ── Submission versions (drafts + resubmission) ───────────────────

def get_version(version_id: int) -> SubmissionVersion | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM coursework_submission_versions "
            "WHERE version_id = ?", (version_id,)).fetchone()
        return _row_version(r) if r else None


def list_versions(submission_id: int) -> list[SubmissionVersion]:
    init_db()
    with _connect() as conn:
        return [_row_version(r) for r in conn.execute(
            "SELECT * FROM coursework_submission_versions "
            "WHERE submission_id = ? ORDER BY attempt_no ASC",
            (int(submission_id),)).fetchall()]


def latest_version(submission_id: int) -> SubmissionVersion | None:
    versions = list_versions(submission_id)
    return versions[-1] if versions else None


def submit_work(submission_id: int, *,
                 files: Sequence[str | Path] | None = None,
                 word_count: int | None = None,
                 is_draft: bool = False,
                 submitted_on: str | None = None,
                 submitted_by: str | None = None,
                 note: str | None = None,
                 late: bool | None = None,
                 issue_receipt: bool = True,
                 force: bool = False) -> SubmissionVersion:
    """Record one attempt at a submission: files, word count, receipt.

    Every call appends a new version rather than overwriting the last,
    so a draft → feedback → final cycle keeps the whole trail.

    A *draft* deliberately leaves the submission ``In Progress``: the
    student still owes the final piece, and the late sweep should still
    chase them for it. A final attempt sets ``Submitted`` or ``Late``,
    decided against :func:`effective_due_date` so an approved extension
    is honoured.

    Pass ``force=True`` to override a closed assignment or a
    resubmission lock (staff acting on a student's behalf).
    """
    init_db()
    sub = get_submission(submission_id)
    if sub is None:
        raise ValidationError(f"No submission #{submission_id}")
    assignment = get_assignment(sub.assignment_id)
    if assignment is None:
        raise ValidationError(f"No assignment #{sub.assignment_id}")

    if not force and assignment.status in ("Closed", "Graded", "Archived"):
        raise ValidationError(
            f"Assignment #{assignment.assignment_id} is {assignment.status}"
            f" — it is closed to submissions")

    existing = list_versions(submission_id)
    if (not force and not is_draft and not assignment.allow_resubmission
            and any(not v.is_draft for v in existing)):
        raise ValidationError(
            "This assignment does not allow resubmission — a final "
            "attempt has already been recorded")

    when = _validate_date(submitted_on, "Submitted on") \
        or _dt.date.today().isoformat()
    wc = _validate_number(word_count, "Word count", min_val=0)
    wc_int = int(wc) if wc is not None else None

    due = effective_due_date(sub, assignment)
    if late is None:
        late = bool(due and when > due)
    if is_draft:
        # A draft is progress, not a hand-in.
        status = "In Progress"
    else:
        status = "Late" if late else "Submitted"

    attempt_no = (existing[-1].attempt_no + 1) if existing else 1

    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO coursework_submission_versions
                   (submission_id, attempt_no, is_draft, status,
                    submitted_on, submitted_at, submitted_by,
                    word_count, note, created_at)
               VALUES (?, ?, ?, ?, ?, datetime('now'), ?, ?, ?,
                       datetime('now'))""",
            (submission_id, attempt_no, 1 if is_draft else 0, status,
             when, (submitted_by or "").strip() or None, wc_int,
             (note or "").strip() or None))
        conn.commit()
        version_id = int(cur.lastrowid or 0)

    for f in (files or []):
        attach_file(source_path=f, submission_id=submission_id,
                     version_id=version_id, kind="Work",
                     uploaded_by=submitted_by)

    # Roll the attempt up onto the submission row so the existing list
    # and summary views stay accurate without joining.
    with _connect() as conn:
        conn.execute(
            """UPDATE coursework_submissions SET
                   status = ?, attempt_no = ?, is_draft = ?,
                   word_count = COALESCE(?, word_count),
                   submitted_on = CASE WHEN ? THEN submitted_on ELSE ? END,
                   auto_status_on = NULL,
                   updated_at = datetime('now')
               WHERE submission_id = ?""",
            (status, attempt_no, 1 if is_draft else 0, wc_int,
             1 if is_draft else 0, when, submission_id))
        conn.commit()

    if issue_receipt:
        try:
            issue_submission_receipt(version_id)
        except Exception:
            logger.exception(
                "Receipt generation failed for version #%d "
                "(the submission itself is recorded)", version_id)

    out = get_version(version_id)
    assert out is not None
    check = check_word_limit(assignment, wc_int)
    if check.breached:
        logger.warning(
            "Submission #%d attempt %d is over the word limit: %s",
            submission_id, attempt_no, check.message)
    logger.info(
        "Recorded %s for submission #%d (student %s, attempt %d, "
        "status %s, %d file(s))",
        "draft" if is_draft else "submission", submission_id,
        sub.student_id, attempt_no, status, len(files or []))
    return out


# ── Submission receipts ───────────────────────────────────────────

def receipt_reference(assignment_id: int, submission_id: int,
                       attempt_no: int) -> str:
    return f"CW{assignment_id:04d}-{submission_id:05d}-A{attempt_no}"


def build_receipt_text(version_id: int) -> str:
    """Render the human-readable receipt for one attempt.

    Lists every file with its size and SHA-256 so the school can show
    later that what was marked is exactly what was handed in.
    """
    version = get_version(version_id)
    if version is None:
        raise ValidationError(f"No submission version #{version_id}")
    sub = get_submission(version.submission_id)
    assert sub is not None
    assignment = get_assignment(sub.assignment_id)
    assert assignment is not None

    student_name = sub.student_id
    try:
        from education_system.systems.sixth_form.domain.learners.students import (
            students as _students,
        )
        student = _students.get_student(sub.student_id)
        if student is not None:
            student_name = f"{student.full_name} ({sub.student_id})"
    except Exception:
        logger.debug("Could not resolve student name for receipt",
                      exc_info=True)

    files = list_attachments(version_id=version_id)
    due = effective_due_date(sub, assignment)
    check = check_word_limit(assignment, version.word_count)

    lines = [
        "SUBMISSION RECEIPT",
        "==================",
        f"Reference:    {version.receipt_ref or receipt_reference(assignment.assignment_id, sub.submission_id, version.attempt_no)}",
        f"Assignment:   #{assignment.assignment_id} {assignment.title}",
        f"Subject:      {assignment.subject_name}",
        f"Student:      {student_name}",
        f"Attempt:      {version.label}",
        f"Submitted on: {version.submitted_on} "
        f"(recorded {version.submitted_at} UTC)",
        f"Due:          {due or '—'}"
        + ("  [extension applied]" if sub.extended_due_date else ""),
        f"Status:       {version.status}",
    ]
    if check.applicable:
        lines.append(f"Word count:   {check.message}")
    elif version.word_count is not None:
        lines.append(f"Word count:   {version.word_count}")

    lines.append("")
    if files:
        lines.append(f"Files ({len(files)})")
        lines.append("-" * 40)
        for f in files:
            lines.append(f"  {f.filename}  [{f.size_label}]")
            lines.append(f"    sha256: {f.sha256 or '—'}")
    else:
        lines.append("Files: none attached "
                     "(submission recorded without an upload)")
    lines.append("")
    lines.append("Keep this receipt. If a submission is ever queried, "
                 "the reference and file hashes above")
    lines.append("identify exactly what was received and when.")
    return "\n".join(lines)


def issue_submission_receipt(version_id: int, *,
                              email: bool = True) -> SubmissionVersion:
    """Stamp a reference on an attempt, write the receipt, email it.

    The reference and hash are written back to the version row, and the
    receipt text is stored beside the submitted files.
    """
    init_db()
    version = get_version(version_id)
    if version is None:
        raise ValidationError(f"No submission version #{version_id}")
    sub = get_submission(version.submission_id)
    assert sub is not None

    ref = receipt_reference(sub.assignment_id, sub.submission_id,
                             version.attempt_no)
    files = list_attachments(version_id=version_id)
    # Hash over the content hashes: changing any file changes this.
    fingerprint = hashlib.sha256(
        "|".join([ref, version.submitted_at or "",
                  *(f.sha256 or "" for f in files)]).encode("utf-8")
    ).hexdigest()[:16]

    with _connect() as conn:
        conn.execute(
            "UPDATE coursework_submission_versions SET "
            "receipt_ref = ?, receipt_hash = ? WHERE version_id = ?",
            (ref, fingerprint, version_id))
        conn.execute(
            "UPDATE coursework_submissions SET receipt_ref = ?, "
            "updated_at = datetime('now') WHERE submission_id = ?",
            (ref, sub.submission_id))
        conn.commit()

    text = build_receipt_text(version_id)
    rel_dir = _attachment_dir(assignment_id=sub.assignment_id,
                               submission_id=sub.submission_id,
                               attempt_no=version.attempt_no)
    abs_dir = _files_root() / rel_dir
    abs_dir.mkdir(parents=True, exist_ok=True)
    rel_path = rel_dir / f"receipt_A{version.attempt_no}.txt"
    (_files_root() / rel_path).write_text(text, encoding="utf-8")

    with _connect() as conn:
        conn.execute(
            "UPDATE coursework_submission_versions SET receipt_path = ? "
            "WHERE version_id = ?", (str(rel_path), version_id))
        conn.commit()

    if email:
        _email_receipt(version_id, ref, fingerprint, text)

    out = get_version(version_id)
    assert out is not None
    logger.info("Issued receipt %s (hash %s) for version #%d",
                ref, fingerprint, version_id)
    return out


def _email_receipt(version_id: int, ref: str, fingerprint: str,
                    text: str) -> None:
    """Email the receipt to the student. Best-effort, like the
    assignment-set notification — a mail failure must never lose the
    submission that has already been recorded."""
    try:
        from education_system.systems.sixth_form import SYSTEM_NAME
        from education_system.systems.sixth_form.domains.communications.domain.messages import (
            email_templates,
        )
        from education_system.systems.sixth_form.domain.learners.students import (
            students as _students,
        )
        version = get_version(version_id)
        assert version is not None
        sub = get_submission(version.submission_id)
        assert sub is not None
        assignment = get_assignment(sub.assignment_id)
        assert assignment is not None
        student = _students.get_student(sub.student_id)
        if student is None:
            logger.info("No student record for %s — receipt %s not emailed",
                        sub.student_id, ref)
            return
        files = list_attachments(version_id=version_id)
        email_templates.send_from_template(
            "assignment_receipt",
            {
                "system_name":   SYSTEM_NAME,
                "first_name":    student.first_name,
                "full_name":     student.full_name,
                "student_id":    student.student_id,
                "title":         assignment.title,
                "subject_name":  assignment.subject_name,
                "reference":     ref,
                "fingerprint":   fingerprint,
                "attempt":       version.label,
                "submitted_on":  version.submitted_on,
                "submitted_at":  version.submitted_at,
                "status":        version.status,
                "due_date":      effective_due_date(sub, assignment) or "—",
                "file_count":    str(len(files)),
                "file_list":     ("\n".join(
                    f"  {f.filename} [{f.size_label}] sha256:{f.sha256}"
                    for f in files) or "  (no files attached)"),
                "receipt":       text,
            },
            to_name=student.full_name,
            to_address=student.email,
            student_id=student.student_id,
        )
        logger.info("Emailed receipt %s to %s", ref, sub.student_id)
    except Exception:
        logger.exception("Could not email receipt %s", ref)
