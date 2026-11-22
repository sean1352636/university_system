"""Tests for coursework submission handling.

Covers the file store, submission versions (drafts + resubmission),
word limits, similarity scoring, receipts, per-student extensions and
the automatic late sweep.
"""

from __future__ import annotations

import datetime as _dt
import sqlite3

import pytest

from education_system.systems.sixth_form.domain.academics.assignments import (
    crud as assignments_crud,
    integrity as assignments_integrity,
    models as assignments_models,
    store as assignments_store,
    submissions as assignments_submissions,
)
from education_system.systems.sixth_form.domain.academics.subjects import (
    subjects as subjects_mod,
)
from education_system.systems.sixth_form.domain.learners.students import (
    students as students_mod,
)
from education_system import paths


def _day(offset: int = 0) -> str:
    return (_dt.date.today() + _dt.timedelta(days=offset)).isoformat()


def _seed_students(db_path: str, *first_names: str) -> list[str]:
    """Insert student rows straight into the temp DB.

    Deliberately not ``students.create_student``: that provisions a
    login in the shared platform ``auth.db``, which no test should
    touch. Going in by SQL keeps the fixture inside its temp database
    and gives predictable ids to assert against.
    """
    conn = sqlite3.connect(db_path)
    ids = []
    for i, name in enumerate(first_names, 1):
        student_id = f"T{i:04d}"
        conn.execute(
            "INSERT INTO students (student_id, first_name, last_name, "
            "email, subject_1, subject_2, subject_3, status) "
            "VALUES (?, ?, 'Lovelace', ?, 'Mathematics', 'Physics', "
            "'Chemistry', 'Active')",
            (student_id, name, f"{student_id.lower()}@example.test"))
        ids.append(student_id)
    conn.commit()
    conn.close()
    return ids


@pytest.fixture
def cw_db(tmp_path, monkeypatch):
    """Assignments + students on a fresh DB, with an isolated file store.

    ``COURSEWORK_FILES_DIR`` is redirected too — an attachment test that
    wrote into the real data directory would leave student work behind.
    """
    db_path = str(tmp_path / "sixthform.db")
    for mod in (assignments_store, students_mod, subjects_mod):
        monkeypatch.setattr(mod, "DB_PATH", db_path)
        monkeypatch.setattr(mod, "_DB_READY", False)
    store = tmp_path / "coursework_files"
    monkeypatch.setattr(paths, "SIXTH_FORM_COURSEWORK_FILES_DIR", store)
    assignments_store.init_db()

    class NS:
        pass
    ns = NS()
    ns.s1, ns.s2 = _seed_students(db_path, "Ada", "Alan")
    ns.store = store
    ns.tmp = tmp_path
    return ns


def _assignment(**over):
    payload = {"title": "Source analysis", "subject_name": "History",
               "due_date": _day(7), "max_marks": 40, "status": "Set"}
    payload.update(over)
    return assignments_store.create_assignment(payload)


def _file(tmp_path, name="essay.docx", size=1024):
    p = tmp_path / name
    p.write_bytes(b"x" * size)
    return p


# ── Attachments (items 1 and 2) ────────────────────────────────────

def test_attach_file_to_assignment_stores_bytes_and_hash(cw_db):
    a = _assignment()
    src = _file(cw_db.tmp, "mark_scheme.pdf", 2048)

    att = assignments_submissions.attach_file(source_path=src, assignment_id=a.assignment_id,
                          kind="Mark Scheme", uploaded_by="J Smith")

    assert att.filename == "mark_scheme.pdf"
    assert att.byte_size == 2048
    assert att.kind == "Mark Scheme"
    assert att.exists
    assert att.path.read_bytes() == src.read_bytes()
    # sha256 of 2048 'x' bytes, recomputed rather than hard-coded.
    import hashlib
    assert att.sha256 == hashlib.sha256(b"x" * 2048).hexdigest()
    assert assignments_submissions.list_attachments(assignment_id=a.assignment_id) == [att]


def test_attach_file_from_bytes_needs_a_filename(cw_db):
    a = _assignment()
    with pytest.raises(assignments_models.ValidationError):
        assignments_submissions.attach_file(data=b"hello", assignment_id=a.assignment_id)
    att = assignments_submissions.attach_file(data=b"hello", filename="notes.txt",
                          assignment_id=a.assignment_id)
    assert att.path.read_bytes() == b"hello"


def test_attachment_needs_exactly_one_owner(cw_db):
    a = _assignment()
    sub = assignments_crud.add_student(a.assignment_id, cw_db.s1)
    with pytest.raises(assignments_models.ValidationError):
        assignments_submissions.attach_file(data=b"x", filename="a.txt")
    with pytest.raises(assignments_models.ValidationError):
        assignments_submissions.attach_file(data=b"x", filename="a.txt",
                        assignment_id=a.assignment_id,
                        submission_id=sub.submission_id)


def test_executable_attachments_are_refused(cw_db):
    a = _assignment()
    for name in ("payload.exe", "run.sh", "macro.vbs"):
        with pytest.raises(assignments_models.ValidationError):
            assignments_submissions.attach_file(data=b"x", filename=name,
                            assignment_id=a.assignment_id)


def test_oversized_and_empty_attachments_are_refused(cw_db):
    a = _assignment()
    with pytest.raises(assignments_models.ValidationError):
        assignments_submissions.attach_file(data=b"", filename="empty.txt",
                        assignment_id=a.assignment_id)
    with pytest.raises(assignments_models.ValidationError):
        assignments_submissions.attach_file(data=b"x" * (assignments_models.MAX_ATTACHMENT_BYTES + 1),
                        filename="huge.bin",
                        assignment_id=a.assignment_id)


def test_attachment_filename_cannot_escape_the_store(cw_db):
    a = _assignment()
    att = assignments_submissions.attach_file(data=b"x", filename="../../../etc/passwd",
                          assignment_id=a.assignment_id)
    assert att.filename == "passwd"
    assert ".." not in att.stored_path
    assert att.path.resolve().is_relative_to(cw_db.store.resolve())


def test_deleting_an_attachment_removes_the_file(cw_db):
    a = _assignment()
    att = assignments_submissions.attach_file(data=b"x", filename="brief.txt",
                          assignment_id=a.assignment_id)
    stored = att.path
    assert stored.is_file()

    assert assignments_submissions.delete_attachment(att.attachment_id) is True

    assert not stored.exists()
    assert assignments_submissions.list_attachments(assignment_id=a.assignment_id) == []
    assert assignments_submissions.delete_attachment(att.attachment_id) is False


def test_deleting_an_assignment_removes_every_stored_file(cw_db):
    a = _assignment()
    sub = assignments_crud.add_student(a.assignment_id, cw_db.s1)
    assignments_submissions.attach_file(data=b"brief", filename="brief.txt",
                    assignment_id=a.assignment_id)
    assignments_submissions.submit_work(sub.submission_id,
                    files=[_file(cw_db.tmp, "work.docx")])
    assert any(cw_db.store.rglob("*.docx"))

    assignments_store.delete_assignment(a.assignment_id)

    left = [p for p in cw_db.store.rglob("*") if p.is_file()]
    assert left == []


# ── Versions, drafts and resubmission (items 3 and 4) ──────────────

def test_each_submission_appends_a_version(cw_db):
    a = _assignment()
    sub = assignments_crud.add_student(a.assignment_id, cw_db.s1)

    v1 = assignments_submissions.submit_work(sub.submission_id, is_draft=True,
                         submitted_on=_day(1))
    v2 = assignments_submissions.submit_work(sub.submission_id, submitted_on=_day(2))

    assert (v1.attempt_no, v2.attempt_no) == (1, 2)
    assert [v.version_id for v in assignments_submissions.list_versions(sub.submission_id)] \
        == [v1.version_id, v2.version_id]
    assert assignments_submissions.latest_version(sub.submission_id).version_id == v2.version_id


def test_a_draft_leaves_the_work_still_owed(cw_db):
    """A draft is progress, not a hand-in — the final piece is still due."""
    a = _assignment()
    sub = assignments_crud.add_student(a.assignment_id, cw_db.s1)

    version = assignments_submissions.submit_work(sub.submission_id, is_draft=True,
                              submitted_on=_day(1))

    assert version.is_draft is True
    assert version.status == "In Progress"
    after = assignments_store.get_submission(sub.submission_id)
    assert after.status == "In Progress"
    assert after.is_draft is True
    assert after.submitted_on is None
    assert after.is_done is False


def test_a_final_attempt_marks_the_submission_done(cw_db):
    a = _assignment()
    sub = assignments_crud.add_student(a.assignment_id, cw_db.s1)

    assignments_submissions.submit_work(sub.submission_id, submitted_on=_day(1))

    after = assignments_store.get_submission(sub.submission_id)
    assert after.status == "Submitted"
    assert after.is_done is True
    assert after.submitted_on == _day(1)
    assert after.attempt_no == 1


def test_submitting_after_the_deadline_is_late(cw_db):
    a = _assignment(due_date=_day(-3))
    sub = assignments_crud.add_student(a.assignment_id, cw_db.s1)

    version = assignments_submissions.submit_work(sub.submission_id, submitted_on=_day(0))

    assert version.status == "Late"
    assert assignments_store.get_submission(sub.submission_id).status == "Late"


def test_files_attach_to_the_attempt_that_carried_them(cw_db):
    a = _assignment()
    sub = assignments_crud.add_student(a.assignment_id, cw_db.s1)
    first = _file(cw_db.tmp, "draft.docx")
    second = _file(cw_db.tmp, "final.docx")

    v1 = assignments_submissions.submit_work(sub.submission_id, files=[first], is_draft=True)
    v2 = assignments_submissions.submit_work(sub.submission_id, files=[second])

    assert [x.filename for x in
            assignments_submissions.list_attachments(version_id=v1.version_id)] == ["draft.docx"]
    assert [x.filename for x in
            assignments_submissions.list_attachments(version_id=v2.version_id)] == ["final.docx"]
    # The earlier attempt's file is untouched by the resubmission.
    assert assignments_submissions.list_attachments(version_id=v1.version_id)[0].exists


def test_resubmission_lock_blocks_a_second_final_attempt(cw_db):
    a = _assignment(allow_resubmission=False)
    sub = assignments_crud.add_student(a.assignment_id, cw_db.s1)
    assignments_submissions.submit_work(sub.submission_id)

    with pytest.raises(assignments_models.ValidationError, match="resubmission"):
        assignments_submissions.submit_work(sub.submission_id)

    # Drafts stay allowed, and staff can override for a genuine case.
    assert assignments_submissions.submit_work(sub.submission_id, is_draft=True).attempt_no == 2
    assert assignments_submissions.submit_work(sub.submission_id, force=True).attempt_no == 3


def test_a_closed_assignment_refuses_submissions(cw_db):
    a = _assignment(status="Closed")
    sub = assignments_crud.add_student(a.assignment_id, cw_db.s1)

    with pytest.raises(assignments_models.ValidationError, match="closed"):
        assignments_submissions.submit_work(sub.submission_id)

    assert assignments_submissions.submit_work(sub.submission_id, force=True).attempt_no == 1


# ── Word limits (item 5) ───────────────────────────────────────────

def test_word_limit_check_bands(cw_db):
    a = _assignment(word_limit=1000)

    assert assignments_submissions.check_word_limit(a, 900).over_by == 0
    assert assignments_submissions.check_word_limit(a, 900).breached is False

    tolerated = assignments_submissions.check_word_limit(a, 1050)
    assert tolerated.over_by == 50
    assert tolerated.within_tolerance is True
    assert tolerated.breached is False

    over = assignments_submissions.check_word_limit(a, 1500)
    assert over.over_by == 500
    assert over.breached is True
    assert "OVER LIMIT" in over.message


def test_word_limit_check_is_inert_without_a_limit_or_count(cw_db):
    a = _assignment()
    assert assignments_submissions.check_word_limit(a, 5000).applicable is False
    assert assignments_submissions.check_word_limit(_assignment(word_limit=100), None).breached \
        is False


def test_over_limit_work_is_still_accepted(cw_db):
    """Boards expect the marker to apply the penalty, not the system to
    refuse the work."""
    a = _assignment(word_limit=500)
    sub = assignments_crud.add_student(a.assignment_id, cw_db.s1)

    version = assignments_submissions.submit_work(sub.submission_id, word_count=2000)

    assert version.word_count == 2000
    assert assignments_store.get_submission(sub.submission_id).word_count == 2000
    assert assignments_submissions.check_word_limit(a, 2000).breached is True


def test_count_words():
    assert assignments_submissions.count_words("one two  three\nfour") == 4
    assert assignments_submissions.count_words("") == 0
    assert assignments_submissions.count_words(None) == 0


# ── Similarity (item 6) ────────────────────────────────────────────

def test_record_similarity_stores_the_result(cw_db):
    a = _assignment()
    sub = assignments_crud.add_student(a.assignment_id, cw_db.s1)

    out = assignments_integrity.record_similarity(sub.submission_id, score=42.5,
                                provider="Turnitin", report_ref="TII-1")

    assert out.similarity_score == 42.5
    assert out.similarity_provider == "Turnitin"
    assert out.similarity_report == "TII-1"
    assert out.similarity_checked_on == _day(0)


def test_flagging_uses_the_per_assignment_threshold(cw_db):
    strict = _assignment(title="Strict", similarity_threshold=10)
    lax = _assignment(title="Lax", similarity_threshold=90)
    s_sub = assignments_crud.add_student(strict.assignment_id, cw_db.s1)
    l_sub = assignments_crud.add_student(lax.assignment_id, cw_db.s1)

    assignments_integrity.record_similarity(s_sub.submission_id, score=20)
    assignments_integrity.record_similarity(l_sub.submission_id, score=20)

    flagged = {s.submission_id for s in assignments_integrity.list_flagged_submissions()}
    assert s_sub.submission_id in flagged
    assert l_sub.submission_id not in flagged


def test_default_threshold_applies_when_none_is_set(cw_db):
    a = _assignment()
    sub = assignments_crud.add_student(a.assignment_id, cw_db.s1)
    assert a.effective_similarity_threshold == \
        assignments_models.DEFAULT_SIMILARITY_THRESHOLD

    assignments_integrity.record_similarity(sub.submission_id,
                          score=assignments_models.DEFAULT_SIMILARITY_THRESHOLD)

    assert [s.submission_id for s in assignments_integrity.list_flagged_submissions()] \
        == [sub.submission_id]


def test_similarity_score_must_be_a_percentage(cw_db):
    a = _assignment()
    sub = assignments_crud.add_student(a.assignment_id, cw_db.s1)
    with pytest.raises(assignments_models.ValidationError):
        assignments_integrity.record_similarity(sub.submission_id, score=101)
    with pytest.raises(assignments_models.ValidationError):
        assignments_integrity.record_similarity(sub.submission_id, score=-1)


def test_similarity_check_without_a_provider_is_a_no_op(cw_db):
    a = _assignment()
    sub = assignments_crud.add_student(a.assignment_id, cw_db.s1)
    assignments_integrity.clear_similarity_provider()

    assert assignments_integrity.run_similarity_check(sub.submission_id) is None
    assert assignments_store.get_submission(sub.submission_id).similarity_score is None


def test_registered_provider_result_is_recorded(cw_db):
    a = _assignment()
    sub = assignments_crud.add_student(a.assignment_id, cw_db.s1)
    seen = {}

    def provider(submission, files):
        seen["submission_id"] = submission.submission_id
        seen["files"] = [f.filename for f in files]
        return assignments_models.SimilarityResult(score=71.0, provider="Fake",
                                    report_ref="F-1")

    assignments_integrity.register_similarity_provider(provider)
    try:
        assignments_submissions.submit_work(sub.submission_id,
                        files=[_file(cw_db.tmp, "work.docx")])
        result = assignments_integrity.run_similarity_check(sub.submission_id)
    finally:
        assignments_integrity.clear_similarity_provider()

    assert result.score == 71.0
    assert seen["submission_id"] == sub.submission_id
    assert seen["files"] == ["work.docx"]
    assert assignments_store.get_submission(sub.submission_id).similarity_score == 71.0


# ── Receipts (item 7) ──────────────────────────────────────────────

def test_submitting_issues_a_receipt(cw_db):
    a = _assignment()
    sub = assignments_crud.add_student(a.assignment_id, cw_db.s1)

    version = assignments_submissions.submit_work(sub.submission_id,
                              files=[_file(cw_db.tmp, "work.docx")])

    assert version.receipt_ref == assignments_submissions.receipt_reference(
        a.assignment_id, sub.submission_id, 1)
    assert version.receipt_hash
    assert (cw_db.store / version.receipt_path).is_file()
    assert assignments_store.get_submission(sub.submission_id).receipt_ref == \
        version.receipt_ref


def test_receipt_text_lists_every_file_with_its_hash(cw_db):
    a = _assignment()
    sub = assignments_crud.add_student(a.assignment_id, cw_db.s1)
    version = assignments_submissions.submit_work(sub.submission_id,
                              files=[_file(cw_db.tmp, "work.docx"),
                                      _file(cw_db.tmp, "data.csv")])

    text = assignments_submissions.build_receipt_text(version.version_id)

    assert version.receipt_ref in text
    assert "work.docx" in text and "data.csv" in text
    for att in assignments_submissions.list_attachments(version_id=version.version_id):
        assert att.sha256 in text
    assert "Ada Lovelace" in text


def test_receipt_fingerprint_changes_with_the_files(cw_db):
    a = _assignment()
    s1 = assignments_crud.add_student(a.assignment_id, cw_db.s1)
    s2 = assignments_crud.add_student(a.assignment_id, cw_db.s2)

    bare = assignments_submissions.submit_work(s1.submission_id)
    with_file = assignments_submissions.submit_work(s2.submission_id,
                                files=[_file(cw_db.tmp, "work.docx")])

    assert bare.receipt_hash != with_file.receipt_hash


def test_receipt_can_be_suppressed_and_reissued(cw_db):
    a = _assignment()
    sub = assignments_crud.add_student(a.assignment_id, cw_db.s1)

    version = assignments_submissions.submit_work(sub.submission_id, issue_receipt=False)
    assert version.receipt_ref is None

    reissued = assignments_submissions.issue_submission_receipt(version.version_id,
                                            email=False)
    assert reissued.receipt_ref
    assert reissued.receipt_hash


# ── Extensions (item 8) ────────────────────────────────────────────

def test_extension_replaces_the_deadline_for_one_student_only(cw_db):
    a = _assignment(due_date=_day(3))
    extended = assignments_crud.add_student(a.assignment_id, cw_db.s1)
    other = assignments_crud.add_student(a.assignment_id, cw_db.s2)

    assignments_submissions.grant_extension(extended.submission_id, _day(10),
                        reason="Hospital appointment",
                        authorised_by="HoD")

    extended = assignments_store.get_submission(extended.submission_id)
    assert extended.extended_due_date == _day(10)
    assert extended.extension_reason == "Hospital appointment"
    assert extended.extension_by == "HoD"
    assert extended.extension_on == _day(0)
    assert assignments_submissions.effective_due_date(extended, a) == _day(10)
    assert assignments_submissions.effective_due_date(other, a) == _day(3)


def test_extension_must_be_later_than_the_original_deadline(cw_db):
    a = _assignment(due_date=_day(5))
    sub = assignments_crud.add_student(a.assignment_id, cw_db.s1)

    with pytest.raises(assignments_models.ValidationError, match="after the original"):
        assignments_submissions.grant_extension(sub.submission_id, _day(5), reason="nope")
    with pytest.raises(assignments_models.ValidationError, match="after the original"):
        assignments_submissions.grant_extension(sub.submission_id, _day(1), reason="nope")


def test_extension_requires_a_reason(cw_db):
    a = _assignment()
    sub = assignments_crud.add_student(a.assignment_id, cw_db.s1)
    with pytest.raises(assignments_models.ValidationError):
        assignments_submissions.grant_extension(sub.submission_id, _day(30), reason="  ")


def test_extension_makes_late_work_on_time(cw_db):
    a = _assignment(due_date=_day(-5))
    sub = assignments_crud.add_student(a.assignment_id, cw_db.s1)
    assignments_submissions.grant_extension(sub.submission_id, _day(5), reason="Illness")

    version = assignments_submissions.submit_work(sub.submission_id, submitted_on=_day(0))

    assert version.status == "Submitted"


def test_a_future_extension_rescues_work_already_marked_missing(cw_db):
    a = _assignment(due_date=_day(-5))
    sub = assignments_crud.add_student(a.assignment_id, cw_db.s1)
    assignments_integrity.sweep_late_submissions()
    assert assignments_store.get_submission(sub.submission_id).status == "Missing"

    restored = assignments_submissions.grant_extension(sub.submission_id, _day(7),
                                   reason="Appeal upheld")

    assert restored.status == "Not Started"


def test_revoke_extension_restores_the_assignment_deadline(cw_db):
    a = _assignment(due_date=_day(2))
    sub = assignments_crud.add_student(a.assignment_id, cw_db.s1)
    assignments_submissions.grant_extension(sub.submission_id, _day(9), reason="Illness")

    out = assignments_submissions.revoke_extension(sub.submission_id)

    assert out.extended_due_date is None
    assert out.extension_reason is None
    assert assignments_submissions.effective_due_date(out, a) == _day(2)
    assert assignments_submissions.list_extensions() == []


# ── Automatic late detection (item 9) ──────────────────────────────

def test_sweep_marks_only_work_that_never_arrived(cw_db):
    a = _assignment(due_date=_day(-2))
    missing = assignments_crud.add_student(a.assignment_id, cw_db.s1)
    handed_in = assignments_crud.add_student(a.assignment_id, cw_db.s2)
    assignments_submissions.submit_work(handed_in.submission_id, submitted_on=_day(-3))

    result = assignments_integrity.sweep_late_submissions()

    assert result == {"overdue": 1, "marked_missing": 1}
    assert assignments_store.get_submission(missing.submission_id).status == "Missing"
    assert assignments_store.get_submission(missing.submission_id).auto_status_on == _day(0)
    assert assignments_store.get_submission(handed_in.submission_id).status == "Submitted"


def test_sweep_is_idempotent(cw_db):
    a = _assignment(due_date=_day(-1))
    assignments_crud.add_student(a.assignment_id, cw_db.s1)

    first = assignments_integrity.sweep_late_submissions()
    second = assignments_integrity.sweep_late_submissions()

    assert first["marked_missing"] == 1
    assert second == {"overdue": 0, "marked_missing": 0}


def test_sweep_honours_extensions(cw_db):
    a = _assignment(due_date=_day(-4))
    protected = assignments_crud.add_student(a.assignment_id, cw_db.s1)
    exposed = assignments_crud.add_student(a.assignment_id, cw_db.s2)
    assignments_submissions.grant_extension(protected.submission_id, _day(6),
                        reason="Bereavement")

    assignments_integrity.sweep_late_submissions()

    assert assignments_store.get_submission(protected.submission_id).status == "Not Started"
    assert assignments_store.get_submission(exposed.submission_id).status == "Missing"


def test_sweep_leaves_closed_assignments_alone(cw_db):
    a = _assignment(due_date=_day(-4), status="Graded")
    sub = assignments_crud.add_student(a.assignment_id, cw_db.s1)

    assert assignments_integrity.sweep_late_submissions()["overdue"] == 0
    assert assignments_store.get_submission(sub.submission_id).status == "Not Started"


def test_sweep_ignores_assignments_with_no_deadline(cw_db):
    a = _assignment(due_date=None)
    sub = assignments_crud.add_student(a.assignment_id, cw_db.s1)

    assert assignments_integrity.sweep_late_submissions()["overdue"] == 0
    assert assignments_store.get_submission(sub.submission_id).status == "Not Started"


def test_a_draft_does_not_protect_against_the_sweep(cw_db):
    """The student handed in a draft but never the final piece."""
    a = _assignment(due_date=_day(-2))
    sub = assignments_crud.add_student(a.assignment_id, cw_db.s1)
    assignments_submissions.submit_work(sub.submission_id, is_draft=True,
                    submitted_on=_day(-3))

    assignments_integrity.sweep_late_submissions()

    assert assignments_store.get_submission(sub.submission_id).status == "Missing"


def test_dry_run_reports_without_changing_anything(cw_db):
    a = _assignment(due_date=_day(-2))
    sub = assignments_crud.add_student(a.assignment_id, cw_db.s1)

    result = assignments_integrity.sweep_late_submissions(dry_run=True)

    assert result == {"overdue": 1, "marked_missing": 0}
    assert assignments_store.get_submission(sub.submission_id).status == "Not Started"


def test_sweep_can_be_scoped_to_one_assignment(cw_db):
    a1 = _assignment(title="One", due_date=_day(-2))
    a2 = _assignment(title="Two", due_date=_day(-2))
    s1 = assignments_crud.add_student(a1.assignment_id, cw_db.s1)
    s2 = assignments_crud.add_student(a2.assignment_id, cw_db.s1)

    assignments_integrity.sweep_late_submissions(assignment_id=a1.assignment_id)

    assert assignments_store.get_submission(s1.submission_id).status == "Missing"
    assert assignments_store.get_submission(s2.submission_id).status == "Not Started"


def test_resubmitting_clears_the_auto_missing_stamp(cw_db):
    a = _assignment(due_date=_day(-2))
    sub = assignments_crud.add_student(a.assignment_id, cw_db.s1)
    assignments_integrity.sweep_late_submissions()

    assignments_submissions.submit_work(sub.submission_id, submitted_on=_day(0))

    after = assignments_store.get_submission(sub.submission_id)
    assert after.status == "Late"
    assert after.auto_status_on is None


# ── Rollups ────────────────────────────────────────────────────────

def test_summary_counts_the_new_dimensions(cw_db):
    a = _assignment(due_date=_day(-1))
    overdue = assignments_crud.add_student(a.assignment_id, cw_db.s1)
    other = assignments_crud.add_student(a.assignment_id, cw_db.s2)
    assignments_submissions.grant_extension(other.submission_id, _day(30), reason="Illness")
    assignments_integrity.record_similarity(overdue.submission_id, score=95)
    assignments_submissions.attach_file(data=b"x" * 100, filename="brief.txt",
                    assignment_id=a.assignment_id)

    summ = assignments_integrity.summary()

    assert summ.overdue_submissions == 1
    assert summ.active_extensions == 1
    assert summ.flagged_similarity == 1
    assert summ.attachment_count == 1
    assert summ.attachment_bytes == 100


def test_legacy_submit_still_works(cw_db):
    """The old two-argument submit() is used elsewhere in the tree."""
    a = _assignment(due_date=_day(5))
    sub = assignments_crud.add_student(a.assignment_id, cw_db.s1)

    out = assignments_crud.submit(sub.submission_id, late=True)

    assert out.status == "Late"
    assert assignments_submissions.latest_version(sub.submission_id).attempt_no == 1
