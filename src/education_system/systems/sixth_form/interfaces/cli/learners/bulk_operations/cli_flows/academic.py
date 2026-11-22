"""CLI flows for academic, exams, UCAS, subjects and timetable bulk operations.

Split out of ``bulk_operations_cli.py``, which re-exports every name here.
"""

from __future__ import annotations

from datetime import date as _date

from education_system.systems.sixth_form.domain.learners.bulk_operations import ops_academic as bulk_ops_academic
from education_system.systems.sixth_form.domain.learners.bulk_operations import ops_records as bulk_ops_records
from education_system.systems.sixth_form.domain.learners.bulk_operations.base import ValidationError

from education_system.systems.sixth_form.interfaces.cli.learners.bulk_operations.cli_flows.prompts import (
    _input,
    _pause,
    _pick_from,
    _pick_group,
    _pick_students,
    _pick_subject,
    _print_result,
    _UserAbort,
    _yes_no,
)


def bulk_enrol_flow() -> None:
    print("\n═══ Bulk Enrol Students ═══")
    try:
        sids = _pick_students()
        year = _input("Academic year (e.g. 2025/26)", allow_empty=False)
        yg = _pick_from("Year group", ["12", "13"], default="12")
        tutor = _input("Tutor group") or None
        start = _input("Start date",
                         default=_date.today().isoformat())
        status = _pick_from("Status",
                              ["Enrolled", "Pending",
                                "Withdrawn", "Completed"],
                              default="Enrolled")
        notes = _input("Notes") or None
        dry = _yes_no("Preview (dry run)?", default=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        r = bulk_ops_academic.bulk_enrol(sids, academic_year=year, year_group=int(yg),
                             tutor_group=tutor, start_date=start,
                             status=status, notes=notes, dry_run=dry)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


def bulk_move_group_flow() -> None:
    print("\n═══ Bulk Move Class Group ═══")
    try:
        sids = _pick_students()
        print("  From-group (blank to skip removal):")
        from_id = _pick_group()
        print("  To-group (blank to skip add):")
        to_id = _pick_group()
        if from_id is None and to_id is None:
            print("  ✗ Pick at least one group.")
            _pause()
            return
        dry = _yes_no("Preview (dry run)?", default=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        r = bulk_ops_academic.bulk_move_class_group(
            sids, from_group_id=from_id, to_group_id=to_id, dry_run=dry)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


def bulk_predicted_grades_flow() -> None:
    print("\n═══ Bulk Assign Predicted Grades ═══")
    try:
        sids = _pick_students()
        subject = _pick_subject()
        from_baseline = _yes_no("Derive from baseline?", default=False)
        grade = None
        if not from_baseline:
            grade = _pick_from("Grade",
                                 ["A*", "A", "B", "C", "D", "E", "U"],
                                 default="C")
        confidence = _pick_from("Confidence",
                                   ["High", "Medium", "Low"],
                                   default="Medium")
        by = _input("Predicted by") or None
        dry = _yes_no("Preview (dry run)?", default=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        r = bulk_ops_academic.bulk_assign_predicted_grades(
            sids, subject=subject, grade=grade,
            from_baseline=from_baseline, confidence=confidence,
            predicted_by=by, dry_run=dry,
        )
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


def bulk_import_marks_flow() -> None:
    print("\n═══ Bulk Import Assessment Marks ═══")
    print("  Required: student_id, subject_name, assessment_type,")
    print("            assessment_date, raw_score, max_score")
    print("  Optional: percentage, baseline_grade, confidence,")
    print("            assessor, notes, is_primary")
    try:
        path = _input("CSV path", allow_empty=False)
        dry = _yes_no("Preview (dry run)?", default=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        r = bulk_ops_academic.bulk_import_assessment_marks(path, dry_run=dry)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


def bulk_recalc_grades_flow() -> None:
    print("\n═══ Bulk Recalculate Grade Reports ═══")
    try:
        sids = _pick_students()
        dry = _yes_no("Preview (dry run)?", default=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        r = bulk_ops_academic.bulk_recalc_grade_reports(sids, dry_run=dry)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


def bulk_export_progress_flow() -> None:
    print("\n═══ Bulk Export Progress Reports ═══")
    try:
        sids = _pick_students()
        out_dir = _input("Output directory", allow_empty=False)
        dry = _yes_no("Preview (dry run)?", default=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        r = bulk_ops_academic.bulk_export_progress_reports(
            sids, output_dir=out_dir, dry_run=dry)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


def bulk_publish_reports_flow() -> None:
    print("\n═══ Bulk Publish / Unpublish Report Cards ═══")
    try:
        sids = _pick_students()
        period = _input("Period (e.g. 2025/26 T1)", allow_empty=False)
        publish = _yes_no("Publish? (No = unpublish)", default=True)
        by = _input("Published by") or None
        dry = _yes_no("Preview (dry run)?", default=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        r = bulk_ops_academic.bulk_publish_report_cards(
            sids, period=period, publish=publish,
            published_by=by, dry_run=dry,
        )
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


def bulk_grade_boundaries_flow() -> None:
    print("\n═══ Bulk Apply Grade Boundaries ═══")
    try:
        raw = _input("Assignment ids (comma-separated)",
                       allow_empty=False)
        ids = [int(t) for t in raw.replace(" ", ",").split(",") if t]
        a_star = _input("A* threshold") or ""
        a = _input("A threshold") or ""
        b = _input("B threshold") or ""
        c = _input("C threshold") or ""
        d = _input("D threshold") or ""
        e_ = _input("E threshold") or ""
        dry = _yes_no("Preview (dry run)?", default=False)
    except (_UserAbort, ValueError):
        print("\n  Cancelled / bad input.")
        return
    def _n(s: str) -> int | None:
        return int(s) if s else None
    try:
        r = bulk_ops_academic.bulk_apply_grade_boundaries(
            ids, a_star=_n(a_star), a=_n(a), b=_n(b),
            c=_n(c), d=_n(d), e=_n(e_), dry_run=dry,
        )
    except ValidationError as ve:
        print(f"\n  ✗ {ve}")
        _pause()
        return
    _print_result(r, dry_run=dry)


def bulk_exam_entries_flow() -> None:
    print("\n═══ Bulk Exam Entries ═══")
    from education_system.systems.sixth_form.domain.assessment.exam_entries.exam_entries import (
        SEASONS, DEFAULT_SEASON, TIERS,
    )
    try:
        sids = _pick_students()
        subject = _pick_subject()
        board = _input("Exam board (e.g. AQA, OCR, Edexcel)",
                          allow_empty=False)
        code = _input("Paper code", allow_empty=False)
        season = _pick_from("Season", list(SEASONS),
                              default=DEFAULT_SEASON)
        year = int(_input("Year", default=str(_date.today().year)))
        tier_pick = _pick_from("Tier", [""] + list(TIERS), default="")
        fee_raw = _input("Fee (£, optional)") or ""
        prefix = _input("Candidate-no prefix (optional)") or None
        dry = _yes_no("Preview (dry run)?", default=False)
    except (_UserAbort, ValueError):
        print("\n  Cancelled / bad input.")
        return
    fee = float(fee_raw) if fee_raw else None
    try:
        r = bulk_ops_records.bulk_exam_entries(
            sids, subject=subject, exam_board=board,
            paper_code=code, season=season, year=year,
            tier=tier_pick or None, fee=fee,
            candidate_no_prefix=prefix, dry_run=dry)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


def bulk_exam_access_flow() -> None:
    print("\n═══ Bulk Exam Access Arrangements ═══")
    try:
        sids = _pick_students()
        arrangement = _pick_from(
            "Arrangement",
            ["25% Extra Time", "50% Extra Time", "Scribe", "Reader",
             "Rest Breaks", "Word Processor", "Separate Room",
             "Prompter", "Other"], default="25% Extra Time")
        desc = _input("Description") or None
        start = _input("Start date",
                          default=_date.today().isoformat())
        end = _input("End date (optional)") or None
        by = _input("Approved by") or None
        dry = _yes_no("Preview (dry run)?", default=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        r = bulk_ops_records.bulk_exam_access_arrangements(
            sids, arrangement=arrangement, description=desc,
            start_date=start, end_date=end, approved_by=by,
            dry_run=dry)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


def bulk_exam_timetables_flow() -> None:
    print("\n═══ Bulk Export Exam Timetables ═══")
    try:
        sids = _pick_students()
        out_dir = _input("Output directory", allow_empty=False)
        year_raw = _input("Year filter (optional)") or ""
        season = _input("Season filter (optional)") or None
        dry = _yes_no("Preview (dry run)?", default=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    year = int(year_raw) if year_raw else None
    try:
        r = bulk_ops_records.bulk_export_exam_timetables(
            sids, output_dir=out_dir, year=year, season=season,
            dry_run=dry)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


# ── Lifecycle / admin / meta flows ─────────────────────────────────

def bulk_ucas_export_flow() -> None:
    print("\n═══ Bulk UCAS Export Predictions ═══")
    try:
        sids = _pick_students()
        path = _input("Output CSV path", allow_empty=False)
        dry = _yes_no("Preview (dry run)?", default=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        r = bulk_ops_records.bulk_ucas_export_predictions(
            sids, output_path=path, dry_run=dry)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


def bulk_ucas_status_flow() -> None:
    print("\n═══ Bulk Update UCAS Status ═══")
    from education_system.systems.sixth_form.domain.progression.university.ucas import (
        APP_STATUSES,
    )
    try:
        sids = _pick_students()
        status = _pick_from("Status", list(APP_STATUSES),
                              default=APP_STATUSES[0])
        dry = _yes_no("Preview (dry run)?", default=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        r = bulk_ops_records.bulk_ucas_update_status(
            sids, status=status, dry_run=dry)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


def bulk_assign_subjects_flow() -> None:
    print("\n═══ Bulk Assign Subjects ═══")
    try:
        sids = _pick_students()
        print("  Pick up to 3 subjects (one at a time, blank to finish).")
        picks: list[str] = []
        for _ in range(3):
            try:
                pick = _pick_subject()
            except _UserAbort:
                break
            if not pick or pick in picks:
                break
            picks.append(pick)
            if not _yes_no("Add another subject?", default=False):
                break
        if not picks:
            print("  ✗ At least one subject required.")
            _pause()
            return
        overwrite = _yes_no(
            "Overwrite existing slots? (no = fill blanks only)",
            default=False)
        dry = _yes_no("Preview (dry run)?", default=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        r = bulk_ops_academic.bulk_assign_subjects(
            sids, subjects=picks, overwrite=overwrite, dry_run=dry,
        )
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


def bulk_withdraw_subjects_flow() -> None:
    print("\n═══ Bulk Withdraw Subjects ═══")
    try:
        sids = _pick_students()
        print("  Pick subjects to remove (blank to finish).")
        picks: list[str] = []
        for _ in range(3):
            try:
                pick = _pick_subject()
            except _UserAbort:
                break
            if not pick or pick in picks:
                break
            picks.append(pick)
            if not _yes_no("Withdraw another?", default=False):
                break
        if not picks:
            print("  ✗ At least one subject required.")
            _pause()
            return
        # Withdrawals go through the learning-aim workflow: effective
        # date (last day in learning), reason and approver are recorded
        # and the funding qualifying period is checked.
        import datetime as _dt
        eff = _input("Effective date (last day in learning, YYYY-MM-DD)",
                     default=_dt.date.today().isoformat())
        reason = _input("Reason", default="Bulk withdrawal")
        approver = _input("Approved by", allow_empty=False)
        dry = _yes_no("Preview (dry run)?", default=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        r = bulk_ops_academic.bulk_withdraw_subjects(
            sids, subjects=picks, dry_run=dry,
            effective_date=eff, reason=reason, approved_by=approver,
        )
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


def bulk_set_teaching_set_flow() -> None:
    print("\n═══ Bulk Set Teaching Set ═══")
    try:
        sids = _pick_students()
        print("  Target group (the set to move students INTO):")
        target = _pick_group()
        if target is None:
            print("  ✗ Pick a target group.")
            _pause()
            return
        dry = _yes_no("Preview (dry run)?", default=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        r = bulk_ops_academic.bulk_set_teaching_set(
            sids, target_group_id=target, dry_run=dry,
        )
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)


def bulk_import_timetable_csv_flow() -> None:
    print("\n═══ Bulk Import Timetable CSV ═══")
    print("  Required columns: group_id, day, period")
    print("  Optional:         start_time, end_time, room, notes")
    try:
        path = _input("CSV path", allow_empty=False)
        dry = _yes_no("Preview (dry run)?", default=True)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        r = bulk_ops_academic.bulk_import_timetable_csv(
            path, dry_run=dry,
        )
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_result(r, dry_run=dry)
