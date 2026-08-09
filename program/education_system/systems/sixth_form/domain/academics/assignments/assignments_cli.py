"""CLI flows for Sixth Form Assignments."""

from __future__ import annotations

import logging
from datetime import date as _date
from pathlib import Path
from typing import Any, Callable
from education_system.systems.sixth_form.domain.academics.assignments import (
    assignments as data,
)
from education_system.systems.sixth_form.domain.learners.students import (
    students as student_data,
)
from education_system.systems.sixth_form.domain.academics.assignments.assignments import (
    ASSIGNMENT_ATTACHMENT_KINDS,
    ASSIGNMENT_STATUSES,
    ASSIGNMENT_TYPES,
    Assignment,
    Attachment,
    DEFAULT_ASSIGNMENT_STATUS,
    DEFAULT_ASSIGNMENT_TYPE,
    DEFAULT_SUBMISSION_STATUS,
    DONE_SUBMISSION_STATUSES,
    SUBMISSION_ATTACHMENT_KINDS,
    SUBMISSION_STATUSES,
    Submission,
    ValidationError,
    YEAR_GROUPS,
)

logger = logging.getLogger(__name__)


class _UserAbort(Exception):
    pass


# ── Prompt helpers ─────────────────────────────────────────────────

def _input(prompt: str, *, default: str = "",
            allow_empty: bool = True) -> str:
    suffix = f" [{default}]" if default else ""
    try:
        raw = input(f"  {prompt}{suffix}: ")
    except (EOFError, KeyboardInterrupt):
        print()
        raise _UserAbort
    s = raw.strip()
    if s.lower() == "cancel":
        raise _UserAbort
    if not s:
        if default:
            return default
        if not allow_empty:
            print("    Value is required.")
            return _input(prompt, default=default, allow_empty=False)
        return ""
    return s


def _pause() -> None:
    try:
        input("\n  Press Enter to continue...")
    except (EOFError, KeyboardInterrupt):
        pass


def _multiline(prompt: str, *, default: str = "") -> str:
    print(f"\n  {prompt} (end with '.' on its own line; ENTER for default)")
    if default:
        for line in default.splitlines():
            print(f"    | {line}")
    lines: list[str] = []
    try:
        while True:
            ln = input("  > ")
            if ln.strip() == ".":
                break
            if not lines and not ln:
                return default
            lines.append(ln)
    except (EOFError, KeyboardInterrupt):
        print()
        raise _UserAbort
    return "\n".join(lines)


def _pick_from(label: str, options: list[str],
                default: str | None = None) -> str:
    print(f"\n  {label}:")
    for i, opt in enumerate(options, 1):
        marker = " *" if opt == default else "  "
        print(f"    {marker}{i:>2}) {opt}")
    while True:
        raw = _input(f"  Pick #1..{len(options)}",
                      default=default or "")
        if default and raw == default:
            return default
        if not raw.isdigit():
            print("    Enter a number (or 'cancel' to abort).")
            continue
        n = int(raw)
        if not (1 <= n <= len(options)):
            print("    Out of range.")
            continue
        return options[n - 1]


def _pick_subject() -> str:
    try:
        from education_system.systems.sixth_form.domain.academics.subjects import (
            subjects as _subjects,
        )
        names = [s.name for s in _subjects.list_subjects()]
    except Exception:
        names = []
    if not names:
        return _input("Subject", allow_empty=False)
    return _pick_from("Subject", names)


def _pick_assignment() -> Assignment:
    rows = data.list_assignments()
    if not rows:
        print("    No assignments yet.")
        raise _UserAbort
    print("\n  Assignments:")
    for i, a in enumerate(rows, 1):
        print(f"    {i:>3}) #{a.assignment_id}  "
              f"{(a.due_date or '—'):<10}  "
              f"{a.subject_name[:14]:<14}  "
              f"{a.title[:32]:<32}  [{a.status}]")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or id)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1]
            match = next((a for a in rows
                            if a.assignment_id == n), None)
            if match:
                return match
        print("    No matching assignment.")


def _pick_student() -> str:
    rows = student_data.list_students()
    if not rows:
        print("    No students.")
        raise _UserAbort
    print("\n  Students:")
    for i, s in enumerate(rows, 1):
        print(f"    {i:>3}) {s.student_id}  {s.full_name}")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or student id)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1].student_id
            continue
        match = next((s for s in rows
                       if s.student_id.lower() == raw.lower()), None)
        if match:
            return match.student_id
        print("    No matching student.")


def _collect_paths(label: str = "File path") -> list[str]:
    """Prompt for file paths, one per line, until a blank line."""
    print(f"\n  {label} — one per line, blank line to finish:")
    out: list[str] = []
    while True:
        raw = _input(f"File {len(out) + 1}")
        if not raw:
            return out
        path = Path(raw).expanduser()
        if not path.is_file():
            print(f"    ✗ Not a file: {path}")
            continue
        out.append(str(path))
        print(f"    ✓ {path.name}")


def _print_attachments(rows: list[Attachment], *,
                        indent: str = "    ") -> None:
    if not rows:
        print(f"{indent}(no attachments)")
        return
    for att in rows:
        missing = "" if att.exists else "  [FILE MISSING]"
        version = (f"  attempt-file v#{att.version_id}"
                   if att.version_id else "")
        print(f"{indent}#{att.attachment_id:<4} [{att.kind:<10}] "
              f"{att.filename[:40]:<40} {att.size_label:>9}"
              f"{version}{missing}")


def _pick_attachment(*, assignment_id: int | None = None,
                      submission_id: int | None = None) -> Attachment:
    rows = data.list_attachments(assignment_id=assignment_id,
                                  submission_id=submission_id)
    if not rows:
        print("    No attachments here.")
        raise _UserAbort
    print("\n  Attachments:")
    _print_attachments(rows)
    while True:
        raw = _input("  Attachment id", allow_empty=False)
        match = next((a for a in rows
                       if str(a.attachment_id) == raw), None)
        if match:
            return match
        print("    No matching attachment.")


def _pick_submission(assignment_id: int) -> Submission:
    subs = data.list_submissions(assignment_id=assignment_id)
    if not subs:
        print("    No submissions on this assignment.")
        raise _UserAbort
    names = {s.student_id: s.full_name
              for s in student_data.list_students()}
    print("\n  Submissions:")
    for i, sub in enumerate(subs, 1):
        marks = (f"{sub.marks}" if sub.marks is not None else "—")
        print(f"    {i:>3}) #{sub.submission_id}  "
              f"{sub.student_id}  "
              f"{names.get(sub.student_id, '?')[:20]:<20}  "
              f"[{sub.status}]  marks={marks}")
    while True:
        raw = _input(f"  Pick #1..{len(subs)} (or id)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(subs):
                return subs[n - 1]
            match = next((s for s in subs
                            if s.submission_id == n), None)
            if match:
                return match
        print("    No matching submission.")


# ── Print helpers ──────────────────────────────────────────────────

def _print_assignments(rows: list[Assignment]) -> None:
    if not rows:
        print("\n  (no assignments)")
        return
    print()
    print(f"  {'#':>4}  {'Due':<10}  {'Subject':<16}  "
          f"{'Type':<14}  {'Teacher':<14}  "
          f"{'Status':<10}  Title")
    print("  " + "-" * 110)
    for a in rows:
        print(f"  {a.assignment_id:>4}  "
              f"{(a.due_date or '—'):<10}  "
              f"{a.subject_name[:16]:<16}  "
              f"{a.assignment_type[:14]:<14}  "
              f"{(a.teacher or '—')[:14]:<14}  "
              f"{a.status:<10}  {a.title[:40]}")
    print(f"\n  {len(rows)} assignment(s).")


def _print_assignment_full(a: Assignment) -> None:
    detail = data.get_assignment_detail(a.assignment_id)
    print()
    print(f"    #{a.assignment_id}  {a.title}")
    print(f"    Subject       : {a.subject_name}")
    print(f"    Type          : {a.assignment_type}")
    print(f"    Year / Course : "
          f"{a.year_group or '—'}  ·  course #{a.course_id or '—'}  "
          f"·  group #{a.class_group_id or '—'}")
    print(f"    Teacher       : {a.teacher or '—'}")
    print(f"    Set / Due     : "
          f"{a.set_date or '—'}  →  {a.due_date or '—'}")
    print(f"    Max marks     : {a.max_marks or '—'}")
    print(f"    Weight %      : {a.weight_percent or '—'}")
    print(f"    Status        : {a.status}"
          + ("  (overdue)" if a.is_overdue else ""))
    print(f"    Submission    : {a.submission_method or '—'}")
    print(f"    Word limit    : {a.word_limit or '—'}")
    print(f"    Resubmission  : "
          f"{'allowed' if a.allow_resubmission else 'locked after final'}")
    print(f"    Similarity    : flag at "
          f"{a.effective_similarity_threshold:.0f}%"
          + ("" if a.similarity_threshold is not None
              else "  (default)"))
    attachments = data.list_attachments(assignment_id=a.assignment_id)
    print(f"\n    Attachments ({len(attachments)}):")
    _print_attachments(attachments, indent="      ")
    for label, val in (
            ("Brief",      a.brief),
            ("Rubric",     a.rubric),
            ("Resources",  a.resources),
            ("Notes",      a.notes),
    ):
        if val:
            print()
            print(f"    {label}:")
            for line in val.splitlines():
                print(f"      {line}")
    if detail and detail.submissions:
        print()
        print(f"    Submissions ({detail.submitted_count}"
              f"/{detail.total_submissions}, "
              f"avg={detail.average_mark or '—'}):")
        names = {s.student_id: s.full_name
                  for s in student_data.list_students()}
        for sub in detail.submissions:
            marks = (f"{sub.marks}/{a.max_marks or '?'}"
                     if sub.marks is not None else "—")
            flags = []
            if sub.extended_due_date:
                flags.append(f"ext→{sub.extended_due_date}")
            if sub.attempt_no:
                flags.append(f"attempt {sub.attempt_no}"
                             + (" draft" if sub.is_draft else ""))
            if sub.similarity_score is not None:
                mark = ("!" if sub.similarity_score
                        >= a.effective_similarity_threshold else "")
                flags.append(f"sim {sub.similarity_score:.0f}%{mark}")
            print(f"      #{sub.submission_id}  "
                  f"{sub.student_id}  "
                  f"{names.get(sub.student_id, '?')[:18]:<18}  "
                  f"[{sub.status}]  marks={marks}"
                  + (f"  ({', '.join(flags)})" if flags else ""))


# ── Assignment flows ───────────────────────────────────────────────

def list_all() -> None:
    print("\n═══ All Assignments ═══")
    _print_assignments(data.list_assignments())
    _pause()


def list_open() -> None:
    print("\n═══ Open Assignments ═══")
    _print_assignments(data.list_assignments(open_only=True))
    _pause()


def list_overdue() -> None:
    print("\n═══ Overdue Assignments ═══")
    _print_assignments(data.list_assignments(overdue_only=True))
    _pause()


def filter_flow() -> None:
    print("\n═══ Filter Assignments ═══")
    try:
        subj = _input("Subject (exact)") or None
        teacher = _input("Teacher contains") or None
        status = _input(f"Status ({'/'.join(ASSIGNMENT_STATUSES)})") or None
        atype = _input(f"Type ({'/'.join(ASSIGNMENT_TYPES)})") or None
        year = _input(f"Year ({'/'.join(YEAR_GROUPS)})") or None
        title = _input("Title contains") or None
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        rows = data.list_assignments(
            subject_name=subj, teacher_like=teacher,
            status=status, assignment_type=atype,
            year_group=year, title_like=title,
        )
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    _print_assignments(rows)
    _pause()


def view_assignment_flow() -> None:
    print("\n═══ View Assignment ═══")
    try:
        a = _pick_assignment()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _print_assignment_full(a)
    _pause()


def _collect_form(existing: Assignment | None) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    is_edit = existing is not None
    payload["title"] = _input(
        "Title",
        default=(existing.title if is_edit else ""),
        allow_empty=False)
    if is_edit:
        payload["subject_name"] = _input(
            "Subject", default=existing.subject_name,
            allow_empty=False)
    else:
        payload["subject_name"] = _pick_subject()
    payload["assignment_type"] = _pick_from(
        "Type", list(ASSIGNMENT_TYPES),
        default=(existing.assignment_type if is_edit
                  else DEFAULT_ASSIGNMENT_TYPE))
    payload["year_group"] = _pick_from(
        "Year group", [""] + list(YEAR_GROUPS),
        default=(existing.year_group if is_edit else ""))
    payload["teacher"] = _input(
        "Teacher",
        default=(existing.teacher or "") if is_edit else "")
    payload["set_date"] = _input(
        "Set date (YYYY-MM-DD)",
        default=(existing.set_date or "") if is_edit
                  else _date.today().isoformat())
    payload["due_date"] = _input(
        "Due date (YYYY-MM-DD)",
        default=(existing.due_date or "") if is_edit else "")
    payload["max_marks"] = _input(
        "Max marks",
        default=(str(existing.max_marks)
                  if is_edit and existing.max_marks is not None
                  else ""))
    payload["weight_percent"] = _input(
        "Weight %",
        default=(str(existing.weight_percent)
                  if is_edit and existing.weight_percent is not None
                  else ""))
    payload["submission_method"] = _input(
        "Submission method",
        default=(existing.submission_method or "")
        if is_edit else "")
    payload["word_limit"] = _input(
        "Word limit (blank for none)",
        default=(str(existing.word_limit)
                  if existing and existing.word_limit is not None
                  else ""))
    payload["allow_resubmission"] = _input(
        "Allow resubmission after a final attempt? (y/n)",
        default=("y" if (existing.allow_resubmission
                          if existing else True) else "n")
    ).lower() in ("y", "yes", "true", "1")
    payload["similarity_threshold"] = _input(
        "Similarity flag threshold % (blank for default "
        f"{data.DEFAULT_SIMILARITY_THRESHOLD:.0f})",
        default=(str(existing.similarity_threshold)
                  if existing and existing.similarity_threshold is not None
                  else ""))
    payload["status"] = _pick_from(
        "Status", list(ASSIGNMENT_STATUSES),
        default=(existing.status if is_edit
                  else DEFAULT_ASSIGNMENT_STATUS))
    try:
        payload["brief"] = _multiline(
            "Brief",
            default=(existing.brief or "") if is_edit else "")
        payload["rubric"] = _multiline(
            "Rubric",
            default=(existing.rubric or "") if is_edit else "")
        payload["resources"] = _multiline(
            "Resources",
            default=(existing.resources or "") if is_edit else "")
    except _UserAbort:
        raise
    payload["notes"] = _input(
        "Notes",
        default=(existing.notes or "") if is_edit else "")
    return payload


def new_assignment() -> None:
    print("\n═══ New Assignment ═══")
    try:
        payload = _collect_form(None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        a = data.create_assignment(payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Created assignment #{a.assignment_id} {a.title!r}")
    _pause()


def edit_assignment() -> None:
    print("\n═══ Edit Assignment ═══")
    try:
        a = _pick_assignment()
        payload = _collect_form(a)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_assignment(a.assignment_id, payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Updated #{a.assignment_id}")
    _pause()


def set_status_flow() -> None:
    print("\n═══ Change Assignment Status ═══")
    try:
        a = _pick_assignment()
        new_status = _pick_from(
            "New status", list(ASSIGNMENT_STATUSES),
            default=a.status)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.set_assignment_status(a.assignment_id, new_status)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{a.assignment_id} → {new_status}")
    _pause()


def delete_assignment_flow() -> None:
    print("\n═══ Delete Assignment ═══")
    try:
        a = _pick_assignment()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if _input(f"Delete assignment #{a.assignment_id}? "
              "All submissions go too. Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_assignment(a.assignment_id):
        print(f"\n  ✓ Deleted #{a.assignment_id}")
    _pause()


# ── Submission flows ───────────────────────────────────────────────

def add_students_flow() -> None:
    print("\n═══ Add Student(s) to Assignment ═══")
    try:
        a = _pick_assignment()
        sid = _pick_student()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        sub = data.add_student(a.assignment_id, sid)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Added {sid} to #{a.assignment_id} "
          f"(submission #{sub.submission_id})")
    _pause()


def add_class_group_flow() -> None:
    print("\n═══ Add Class Group to Assignment ═══")
    try:
        a = _pick_assignment()
        gid = int(_input("Class group id", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    try:
        n = data.add_class_group(a.assignment_id, gid)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Added {n} new student(s) from group #{gid}")
    _pause()


def submit_flow() -> None:
    print("\n═══ Submit Work ═══")
    try:
        a = _pick_assignment()
        sub = _pick_submission(a.assignment_id)
        due = data.effective_due_date(sub, a)
        if due:
            print(f"\n  Deadline for this student: {due}"
                  + ("  (extended)" if sub.extended_due_date else ""))
        if sub.attempt_no:
            print(f"  Previous attempts: {sub.attempt_no} "
                  f"(latest {'draft' if sub.is_draft else 'final'})")
        is_draft = _input(
            "Is this a draft rather than the final piece? (y/n)",
            default="n").lower() in ("y", "yes")
        when = _input("Submitted on (YYYY-MM-DD)",
                       default=_date.today().isoformat())
        wc_raw = _input("Word count (blank if not counted)")
        files = _collect_paths("Files to attach")
        note = _input("Note (optional)")
    except _UserAbort:
        print("\n  Cancelled.")
        return

    word_count: int | None = None
    if wc_raw:
        try:
            word_count = int(wc_raw)
        except ValueError:
            print("  ✗ Word count must be a whole number.")
            _pause()
            return
    try:
        version = data.submit_work(
            sub.submission_id, files=files, word_count=word_count,
            is_draft=is_draft, submitted_on=when, note=note or None)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return

    print(f"\n  ✓ Recorded {version.label} — status {version.status}")
    print(f"    Receipt: {version.receipt_ref} "
          f"(hash {version.receipt_hash})")
    if files:
        print(f"    {len(files)} file(s) stored.")
    check = data.check_word_limit(a, word_count)
    if check.applicable:
        flag = "  ⚠" if check.breached else ""
        print(f"    Word count: {check.message}{flag}")
    if is_draft:
        print("    Note: a draft leaves the submission In Progress — "
              "the final piece is still owed.")
    _pause()


def versions_flow() -> None:
    print("\n═══ Submission History ═══")
    try:
        a = _pick_assignment()
        sub = _pick_submission(a.assignment_id)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    versions = data.list_versions(sub.submission_id)
    if not versions:
        print("\n  (no attempts recorded yet)")
        _pause()
        return
    for v in versions:
        print(f"\n  {v.label}  [{v.status}]")
        print(f"    Submitted : {v.submitted_on} "
              f"(recorded {v.submitted_at})")
        print(f"    Words     : {v.word_count if v.word_count is not None else '—'}")
        print(f"    Receipt   : {v.receipt_ref or '—'} "
              f"({v.receipt_hash or '—'})")
        if v.note:
            print(f"    Note      : {v.note}")
        _print_attachments(
            data.list_attachments(version_id=v.version_id),
            indent="    ")
    _pause()


def receipt_flow() -> None:
    print("\n═══ Submission Receipt ═══")
    try:
        a = _pick_assignment()
        sub = _pick_submission(a.assignment_id)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    versions = data.list_versions(sub.submission_id)
    if not versions:
        print("\n  No attempts recorded — nothing to receipt.")
        _pause()
        return
    labels = [v.label for v in versions]
    try:
        chosen = versions[labels.index(
            _pick_from("Attempt", labels, default=labels[-1]))]
        resend = _input("Email the receipt to the student? (y/n)",
                         default="n").lower() in ("y", "yes")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        if resend:
            data.issue_submission_receipt(chosen.version_id, email=True)
        print()
        print(data.build_receipt_text(chosen.version_id))
    except ValidationError as e:
        print(f"\n  ✗ {e}")
    _pause()


# ── Attachment flows ───────────────────────────────────────────────

def attach_to_assignment_flow() -> None:
    print("\n═══ Attach File to Assignment ═══")
    try:
        a = _pick_assignment()
        kind = _pick_from("Kind", list(ASSIGNMENT_ATTACHMENT_KINDS),
                           default=data.DEFAULT_ASSIGNMENT_ATTACHMENT_KIND)
        files = _collect_paths("Files to attach")
        by = _input("Uploaded by", default=a.teacher or "")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if not files:
        print("\n  Nothing to attach.")
        _pause()
        return
    ok = 0
    for path in files:
        try:
            att = data.attach_file(source_path=path,
                                    assignment_id=a.assignment_id,
                                    kind=kind, uploaded_by=by or None)
            print(f"  ✓ {att.filename} ({att.size_label})")
            ok += 1
        except ValidationError as e:
            print(f"  ✗ {Path(path).name}: {e}")
    print(f"\n  {ok}/{len(files)} file(s) attached to "
          f"#{a.assignment_id}.")
    _pause()


def attach_to_submission_flow() -> None:
    print("\n═══ Attach File to Submission ═══")
    try:
        a = _pick_assignment()
        sub = _pick_submission(a.assignment_id)
        kind = _pick_from("Kind", list(SUBMISSION_ATTACHMENT_KINDS),
                           default=data.DEFAULT_SUBMISSION_ATTACHMENT_KIND)
        files = _collect_paths("Files to attach")
        by = _input("Uploaded by")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    latest = data.latest_version(sub.submission_id)
    version_id = latest.version_id if latest else None
    ok = 0
    for path in files:
        try:
            att = data.attach_file(source_path=path,
                                    submission_id=sub.submission_id,
                                    version_id=version_id, kind=kind,
                                    uploaded_by=by or None)
            print(f"  ✓ {att.filename} ({att.size_label})")
            ok += 1
        except ValidationError as e:
            print(f"  ✗ {Path(path).name}: {e}")
    print(f"\n  {ok}/{len(files)} file(s) attached to submission "
          f"#{sub.submission_id}.")
    _pause()


def list_attachments_flow() -> None:
    print("\n═══ Attachments ═══")
    try:
        a = _pick_assignment()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    print(f"\n  Assignment material (#{a.assignment_id}):")
    _print_attachments(data.list_attachments(assignment_id=a.assignment_id))
    names = {s.student_id: s.full_name
              for s in student_data.list_students()}
    for sub in data.list_submissions(assignment_id=a.assignment_id):
        rows = data.list_attachments(submission_id=sub.submission_id)
        if not rows:
            continue
        print(f"\n  {sub.student_id} "
              f"{names.get(sub.student_id, '?')} "
              f"(submission #{sub.submission_id}):")
        _print_attachments(rows)
    _pause()


def delete_attachment_flow() -> None:
    print("\n═══ Delete Attachment ═══")
    try:
        a = _pick_assignment()
        scope = _pick_from("Delete from",
                            ["Assignment material", "A submission"],
                            default="Assignment material")
        if scope == "Assignment material":
            att = _pick_attachment(assignment_id=a.assignment_id)
        else:
            sub = _pick_submission(a.assignment_id)
            att = _pick_attachment(submission_id=sub.submission_id)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if _input(f"Delete {att.filename!r} and its stored file? Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_attachment(att.attachment_id):
        print(f"\n  ✓ Deleted attachment #{att.attachment_id}")
    _pause()


# ── Extension flows ────────────────────────────────────────────────

def grant_extension_flow() -> None:
    print("\n═══ Grant Extension ═══")
    try:
        a = _pick_assignment()
        sub = _pick_submission(a.assignment_id)
        print(f"\n  Current deadline: "
              f"{data.effective_due_date(sub, a) or '—'}")
        new_date = _input("New due date (YYYY-MM-DD)",
                           allow_empty=False)
        reason = _input("Reason", allow_empty=False)
        by = _input("Authorised by", default=a.teacher or "")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        out = data.grant_extension(sub.submission_id, new_date,
                                    reason=reason,
                                    authorised_by=by or None)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ {out.student_id} now due {out.extended_due_date} "
          f"(status {out.status})")
    _pause()


def revoke_extension_flow() -> None:
    print("\n═══ Revoke Extension ═══")
    try:
        a = _pick_assignment()
        sub = _pick_submission(a.assignment_id)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if not sub.extended_due_date:
        print("\n  That submission has no extension.")
        _pause()
        return
    if _input(f"Revoke the extension to {sub.extended_due_date}? "
              "Type 'yes'", default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    data.revoke_extension(sub.submission_id)
    print(f"\n  ✓ Extension revoked on #{sub.submission_id}")
    _pause()


def list_extensions_flow() -> None:
    print("\n═══ Active Extensions ═══")
    rows = data.list_extensions()
    if not rows:
        print("\n  (no extensions granted)")
        _pause()
        return
    names = {s.student_id: s.full_name
              for s in student_data.list_students()}
    print()
    print(f"  {'Sub':>5}  {'Student':<10}  {'Name':<20}  "
          f"{'New due':<12}  {'By':<14}  Reason")
    print("  " + "-" * 100)
    for s in rows:
        print(f"  {s.submission_id:>5}  {s.student_id:<10}  "
              f"{names.get(s.student_id, '?')[:20]:<20}  "
              f"{(s.extended_due_date or '—'):<12}  "
              f"{(s.extension_by or '—')[:14]:<14}  "
              f"{(s.extension_reason or '—')[:40]}")
    print(f"\n  {len(rows)} extension(s).")
    _pause()


# ── Similarity flows ───────────────────────────────────────────────

def record_similarity_flow() -> None:
    print("\n═══ Record Similarity Score ═══")
    try:
        a = _pick_assignment()
        sub = _pick_submission(a.assignment_id)
        score_raw = _input("Similarity % (0-100)", allow_empty=False)
        provider = _input("Provider", default="Turnitin")
        report = _input("Report reference / link")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        out = data.record_similarity(
            sub.submission_id, score=float(score_raw),
            provider=provider or None, report_ref=report or None)
    except ValueError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    threshold = a.effective_similarity_threshold
    verdict = ("FLAGGED for review"
               if (out.similarity_score or 0) >= threshold
               else "below the review threshold")
    print(f"\n  ✓ {out.similarity_score:.1f}% recorded — {verdict} "
          f"(threshold {threshold:.0f}%)")
    _pause()


def run_similarity_flow() -> None:
    print("\n═══ Run Similarity Check ═══")
    try:
        a = _pick_assignment()
        sub = _pick_submission(a.assignment_id)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    result = data.run_similarity_check(sub.submission_id)
    if result is None:
        print("\n  No similarity provider is configured on this "
              "installation.")
        print("  Record a score by hand instead, or register a "
              "provider via")
        print("  assignments.register_similarity_provider().")
    else:
        print(f"\n  ✓ {result.provider or 'provider'} returned "
              f"{result.score:.1f}%")
    _pause()


def flagged_flow() -> None:
    print("\n═══ Flagged for Similarity Review ═══")
    rows = data.list_flagged_submissions()
    if not rows:
        print("\n  (nothing at or above threshold)")
        _pause()
        return
    names = {s.student_id: s.full_name
              for s in student_data.list_students()}
    print()
    print(f"  {'Sub':>5}  {'Student':<10}  {'Name':<20}  "
          f"{'Score':>6}  {'Checked':<12}  Report")
    print("  " + "-" * 100)
    for s in rows:
        print(f"  {s.submission_id:>5}  {s.student_id:<10}  "
              f"{names.get(s.student_id, '?')[:20]:<20}  "
              f"{(s.similarity_score or 0):>5.1f}%  "
              f"{(s.similarity_checked_on or '—'):<12}  "
              f"{(s.similarity_report or '—')[:30]}")
    print(f"\n  {len(rows)} flagged. A score is a prompt to look, "
          f"not a finding.")
    _pause()


# ── Late detection ─────────────────────────────────────────────────

def overdue_submissions_flow() -> None:
    print("\n═══ Overdue Submissions ═══")
    rows = data.list_overdue_submissions()
    if not rows:
        print("\n  (nothing overdue)")
        _pause()
        return
    names = {s.student_id: s.full_name
              for s in student_data.list_students()}
    print()
    print(f"  {'Sub':>5}  {'Assign':>6}  {'Student':<10}  "
          f"{'Name':<20}  {'Due':<12}  Status")
    print("  " + "-" * 90)
    for s in rows:
        due = data.effective_due_date(s)
        print(f"  {s.submission_id:>5}  {s.assignment_id:>6}  "
              f"{s.student_id:<10}  "
              f"{names.get(s.student_id, '?')[:20]:<20}  "
              f"{(due or '—'):<12}  {s.status}")
    print(f"\n  {len(rows)} overdue.")
    _pause()


def late_sweep_flow() -> None:
    print("\n═══ Late Sweep ═══")
    print("  Marks work that is past its deadline and never arrived as")
    print("  Missing. Extensions are honoured; already-submitted work")
    print("  is left alone.")
    preview = data.sweep_late_submissions(dry_run=True)
    print(f"\n  {preview['overdue']} submission(s) would be marked "
          f"Missing.")
    if not preview["overdue"]:
        _pause()
        return
    try:
        if _input("Apply? Type 'yes'",
                   default="no").lower() != "yes":
            print("\n  Cancelled.")
            return
    except _UserAbort:
        print("\n  Cancelled.")
        return
    result = data.sweep_late_submissions()
    print(f"\n  ✓ Marked {result['marked_missing']} submission(s) "
          f"Missing.")
    _pause()


def mark_flow() -> None:
    print("\n═══ Mark Submission ═══")
    try:
        a = _pick_assignment()
        sub = _pick_submission(a.assignment_id)
        marks_raw = _input(
            f"Marks (0-{a.max_marks or '?'})", allow_empty=False)
        grade = _input("Grade letter (optional)") or None
        feedback = _multiline("Feedback")
        marked_by = _input("Marked by",
                              default=a.teacher or "")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        marks = float(marks_raw)
    except ValueError:
        print("  ✗ Marks must be a number.")
        _pause()
        return
    try:
        data.mark_submission(sub.submission_id,
                                marks=marks, grade=grade,
                                feedback=feedback or None,
                                marked_by=marked_by or None)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Marked #{sub.submission_id}: {marks}")
    _pause()


def set_sub_status_flow() -> None:
    print("\n═══ Change Submission Status ═══")
    try:
        a = _pick_assignment()
        sub = _pick_submission(a.assignment_id)
        new_status = _pick_from(
            "New status", list(SUBMISSION_STATUSES),
            default=sub.status)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.set_submission_status(sub.submission_id, new_status)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{sub.submission_id} → {new_status}")
    _pause()


def delete_submission_flow() -> None:
    print("\n═══ Delete Submission ═══")
    try:
        a = _pick_assignment()
        sub = _pick_submission(a.assignment_id)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if _input(f"Delete submission #{sub.submission_id}? Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_submission(sub.submission_id):
        print(f"\n  ✓ Deleted #{sub.submission_id}")
    _pause()


def summary_flow() -> None:
    print("\n═══ Assignments Summary ═══")
    try:
        win = int(_input("Upcoming window (days)", default="14"))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    summ = data.summary(upcoming_window_days=win)
    print(f"\n  Total assignments : {summ.total_assignments}")
    print(f"  Open              : {summ.open_count}")
    print(f"  Overdue           : {summ.overdue}")
    print(f"  Upcoming due ({win}d): {summ.upcoming_due}")
    print(f"\n  Submissions       : {summ.total_submissions}")
    print(f"  Submitted         : {summ.submitted_total}")
    print(f"  Marked            : {summ.marked_total}")
    print(f"  Overdue, not in   : {summ.overdue_submissions}")
    print(f"  Active extensions : {summ.active_extensions}")
    print(f"  Similarity flags  : {summ.flagged_similarity}")
    print(f"  Files stored      : {summ.attachment_count} "
          f"({summ.attachment_bytes / 1048576:.1f} MB)")
    print("\n  By status:")
    for s in ASSIGNMENT_STATUSES:
        n = summ.by_status.get(s, 0)
        if n:
            print(f"    {s:<12} : {n}")
    print("\n  By type:")
    for t in ASSIGNMENT_TYPES:
        n = summ.by_type.get(t, 0)
        if n:
            print(f"    {t:<22} : {n}")
    if summ.by_subject:
        print("\n  Top subjects:")
        for sub, n in list(summ.by_subject.items())[:10]:
            print(f"    {sub:<22} : {n}")
    _pause()


# ── Submenu ───────────────────────────────────────────────────────

_MENU: list[tuple[str, Callable[[], None]]] = [
    ("List all",                list_all),
    ("List open",               list_open),
    ("List overdue",            list_overdue),
    ("Filter",                  filter_flow),
    ("View assignment",         view_assignment_flow),
    ("New assignment",          new_assignment),
    ("Edit assignment",         edit_assignment),
    ("Change status",           set_status_flow),
    ("Delete assignment",       delete_assignment_flow),
    ("─" * 6,                   lambda: None),
    ("Add student",             add_students_flow),
    ("Add class group",         add_class_group_flow),
    ("Submit work",             submit_flow),
    ("Submission history",      versions_flow),
    ("Submission receipt",      receipt_flow),
    ("Mark",                    mark_flow),
    ("Change submission status", set_sub_status_flow),
    ("Delete submission",       delete_submission_flow),
    ("─" * 6,                   lambda: None),
    ("Attach file to assignment", attach_to_assignment_flow),
    ("Attach file to submission", attach_to_submission_flow),
    ("List attachments",        list_attachments_flow),
    ("Delete attachment",       delete_attachment_flow),
    ("─" * 6,                   lambda: None),
    ("Grant extension",         grant_extension_flow),
    ("Revoke extension",        revoke_extension_flow),
    ("Active extensions",       list_extensions_flow),
    ("─" * 6,                   lambda: None),
    ("Overdue submissions",     overdue_submissions_flow),
    ("Run late sweep",          late_sweep_flow),
    ("─" * 6,                   lambda: None),
    ("Record similarity score", record_similarity_flow),
    ("Run similarity check",    run_similarity_flow),
    ("Flagged for review",      flagged_flow),
    ("─" * 6,                   lambda: None),
    ("Marking, rubrics & moderation...", lambda: _marking_submenu()),
    ("Release, appeals & assessment...", lambda: _workflow_submenu()),
    ("Planning, reuse & scheduling...", lambda: _planning_submenu()),
    ("Analysis, digests & exports...", lambda: _insight_submenu()),
    ("─" * 6,                   lambda: None),
    ("Summary",                 summary_flow),
]


def _insight_submenu() -> None:
    """Hand off to the analytics/administration menu."""
    from education_system.systems.sixth_form.domain.academics.assignments import (
        assignments_insight_cli,
    )
    assignments_insight_cli.run()


def _planning_submenu() -> None:
    """Hand off to the catalogue/scheduling menu."""
    from education_system.systems.sixth_form.domain.academics.assignments import (
        assignments_planning_cli,
    )
    assignments_planning_cli.run()


def _workflow_submenu() -> None:
    """Hand off to the release/appeals/assessment menu."""
    from education_system.systems.sixth_form.domain.academics.assignments import (
        assignments_workflow_cli,
    )
    assignments_workflow_cli.run()


def _marking_submenu() -> None:
    """Hand off to the marking module's own menu (imported late to keep
    the two CLI modules from importing each other at module load)."""
    from education_system.systems.sixth_form.domain.academics.assignments import (
        assignments_marking_cli,
    )
    assignments_marking_cli.run()


def run() -> None:
    while True:
        print("\n── Assignments ──")
        for i, (label, _) in enumerate(_MENU, 1):
            if label.startswith("─"):
                print(f"      {label * 3}")
            else:
                print(f"  {i:>2}) {label}")
        print("   0) Back")
        try:
            choice = input("  Select: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if choice == "0":
            return
        if not choice.isdigit() or not (1 <= int(choice) <= len(_MENU)):
            print("  Invalid selection.")
            continue
        label, handler = _MENU[int(choice) - 1]
        if label.startswith("─"):
            continue
        try:
            handler()
        except _UserAbort:
            print("\n  Cancelled.")
        except Exception as e:
            logger.exception("Assignments CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Assignments":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Assignments CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
