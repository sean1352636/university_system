"""CLI flows for coursework analysis and day-to-day administration.

Covers :mod:`assignments_analytics` (history, targets, trends, cohort
statistics, non-submission, weighted grades) and
:mod:`assignments_admin` (clashes, digests, cover, import/export,
coversheets).

Reached from the Assignments menu via "Analysis, digests & exports...".
"""

from __future__ import annotations

import logging
from typing import Callable

from education_system.systems.sixth_form.domain.academics.assignments import (
    assignments_admin as admin,
    assignments_analytics as analytics,
)
from education_system.systems.sixth_form.domain.academics.assignments import (
    models as assignments_models,
    store as assignments_store,
)
import datetime as _dt
from education_system.systems.sixth_form.interfaces.cli.academics.assignments.assignments_cli import (
    _input,
    _pause,
    _pick_assignment,
    _pick_from,
    _pick_student,
    _pick_submission,
    _UserAbort,
)

logger = logging.getLogger(__name__)


def _fmt(value: float | None, dash: str = "—") -> str:
    return f"{value:g}" if value is not None else dash


def _yes(prompt: str, *, default: str = "n") -> bool:
    return _input(prompt, default=default).lower() in ("y", "yes")


# ── Student history (item 43) ──────────────────────────────────────

def history_flow() -> None:
    print("\n═══ Student Coursework History ═══")
    print("  Every subject in one timeline — the view a tutor wants and")
    print("  no single department has.")
    try:
        sid = _pick_student()
        subject = _input("Subject (blank for all)")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    history = analytics.student_history(sid,
                                         subject_name=subject or None)
    if not history.entries:
        print("\n  (no coursework)")
        _pause()
        return
    print(f"\n  {history.student_name} ({history.student_id})")
    print()
    print(f"  {'Due':<12}  {'Subject':<16}  {'Title':<28}  "
          f"{'State':<12}  {'Mark':>10}  {'%':>6}  Grade")
    print("  " + "-" * 100)
    for entry in history.entries:
        mark = ("—" if entry.submission.marks is None
                else f"{entry.submission.marks:g}"
                     f"/{_fmt(entry.assignment.max_marks)}")
        print(f"  {(entry.due_date or '—'):<12}  "
              f"{entry.assignment.subject_name[:16]:<16}  "
              f"{entry.assignment.title[:28]:<28}  "
              f"{entry.state:<12}  {mark:>10}  "
              f"{_fmt(entry.percent):>6}  "
              f"{entry.submission.grade or '—'}")
    print(f"\n  {history.message}")
    _pause()


def subject_breakdown_flow() -> None:
    print("\n═══ History by Subject ═══")
    try:
        sid = _pick_student()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    breakdown = analytics.subject_breakdown(sid)
    if not breakdown:
        print("\n  (no coursework)")
        _pause()
        return
    for subject, history in breakdown.items():
        print(f"\n  {subject}")
        print(f"      {history.message}")
        trend = analytics.student_trend(sid, subject_name=subject)
        print(f"      {trend.message}")
    _pause()


# ── Targets and trends (items 44 and 46) ───────────────────────────

def target_flow() -> None:
    print("\n═══ Coursework Against Target ═══")
    try:
        sid = _pick_student()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    rows = analytics.student_target_report(sid)
    if not rows:
        print("\n  (no coursework)")
        _pause()
        return
    print()
    print(f"  {'Subject':<20}  {'Target':<7}  {'Predicted':<10}  "
          f"{'Actual':<7}  {'%':>6}  {'Pieces':>6}  Verdict")
    print("  " + "-" * 100)
    for row in rows:
        verdict = ("below target" if row.is_underperforming
                   else "at/above target" if row.actual_grade
                   else "—")
        print(f"  {row.subject_name[:20]:<20}  "
              f"{(row.target_grade or '—'):<7}  "
              f"{(row.predicted_grade or '—'):<10}  "
              f"{(row.actual_grade or '—'):<7}  "
              f"{_fmt(row.actual_percent):>6}  {row.pieces:>6}  "
              f"{verdict}")
    _pause()


def underperformers_flow() -> None:
    print("\n═══ Underperforming Against Target ═══")
    print("  One grade below is noise — a bad week, a hard paper. Two")
    print("  is a pattern worth acting on.")
    try:
        subject = _input("Subject (blank for all)")
        serious = _yes("Only two or more grades below? (y/n)")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    rows = analytics.underperformers(subject_name=subject or None,
                                      serious_only=serious)
    if not rows:
        print("\n  (nobody below target)")
        _pause()
        return
    print()
    print(f"  {'Student':<10}  {'Subject':<20}  {'Target':<7}  "
          f"{'Actual':<7}  {'Gap':>4}  {'%':>6}")
    print("  " + "-" * 70)
    for row in rows:
        print(f"  {row.student_id:<10}  {row.subject_name[:20]:<20}  "
              f"{(row.target_grade or '—'):<7}  "
              f"{(row.actual_grade or '—'):<7}  "
              f"{(row.grades_below_target or 0):>4}  "
              f"{_fmt(row.actual_percent):>6}")
    print(f"\n  {len(rows)} student-subject(s) below target.")
    _pause()


def trend_flow() -> None:
    print("\n═══ Declining Students ═══")
    print("  A single mark says far less than the gradient.")
    try:
        subject = _input("Subject (blank for all)")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    rows = analytics.declining_students(subject_name=subject or None)
    if not rows:
        print("\n  (nobody trending downwards)")
        _pause()
        return
    print()
    print(f"  {'Student':<10}  {'Change':>8}  {'Pieces':>7}  Recent marks")
    print("  " + "-" * 70)
    for trend in rows:
        marks = ", ".join(f"{p:g}%" for p in trend.percents)
        print(f"  {trend.student_id:<10}  {trend.change:>+7g}  "
              f"{trend.sample:>7}  {marks[:40]}")
    print(f"\n  {len(rows)} student(s) declining.")
    _pause()


# ── Cohort analytics (item 45) ─────────────────────────────────────

def cohort_flow() -> None:
    print("\n═══ Cohort Analytics ═══")
    try:
        subject = _input("Subject (blank for all)")
        year = _input("Year group (blank for all)")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    summary = analytics.cohort_summary(subject_name=subject or None,
                                        year_group=year or None)
    print(f"\n  Assignments : {summary['assignments']}")
    print(f"  Submissions : {summary['submissions']}")
    print(f"  Marked      : {summary['marked']} "
          f"({_fmt(summary['marked_percent'])}%)")
    print(f"  Missing     : {summary['missing']}")
    distribution = summary["distribution"]
    print(f"\n  {distribution.message}")
    if distribution.by_grade:
        print("\n  Grade distribution:")
        for grade in analytics.grade_order(distribution.qualification_type):
            n = distribution.by_grade.get(grade, 0)
            if n:
                print(f"    {grade:<12} {n:>4}  {'█' * min(n, 40)}")
    _pause()


def criterion_flow() -> None:
    print("\n═══ Criterion Weak Spots ═══")
    print("  A cohort that scores well overall but collapses on one")
    print("  objective has a teaching gap the total mark hides.")
    try:
        a = _pick_assignment()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    rows = analytics.criterion_weaknesses(a.assignment_id)
    if not rows:
        print("\n  (this assignment has no rubric criteria)")
        _pause()
        return
    print()
    print(f"  {'Criterion':<40}  {'Scored':>7}  {'Average':>8}  "
          f"{'Max':>6}  Facility")
    print("  " + "-" * 85)
    for row in rows:
        facility = ("—" if row.facility is None
                    else f"{row.facility:g}%")
        print(f"  {row.label[:40]:<40}  {row.scored:>7}  "
              f"{_fmt(row.average):>8}  {row.max_marks:>6g}  "
              f"{facility}")
    print("\n  Weakest first.")
    _pause()


def compare_flow() -> None:
    print("\n═══ Compare ═══")
    try:
        mode = _pick_from("Compare", ["Subjects", "Teachers"],
                           default="Subjects")
        scope = _input("Subject (teachers only, blank for all)") \
            if mode == "Teachers" else _input("Year group (blank for all)")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if mode == "Subjects":
        rows = analytics.compare_subjects(year_group=scope or None)
        label = "Subject"
    else:
        rows = analytics.compare_teachers(subject_name=scope or None)
        label = "Teacher"
    if not rows:
        print("\n  (nothing marked)")
        _pause()
        return
    print()
    print(f"  {label:<26}  {'Marked':>7}  {'Mean':>7}  {'Median':>7}  "
          f"{'Range':>12}")
    print("  " + "-" * 75)
    for name, distribution in rows.items():
        span = ("—" if distribution.lowest is None
                else f"{distribution.lowest:g}–"
                     f"{distribution.highest:g}%")
        print(f"  {name[:26]:<26}  {distribution.count:>7}  "
              f"{_fmt(distribution.mean):>7}  "
              f"{_fmt(distribution.median):>7}  {span:>12}")
    if mode == "Teachers":
        print("\n  A difference between two teachers has many innocent")
        print("  explanations — different sets, different pieces. This")
        print("  is a question to ask, not an answer.")
    _pause()


# ── Non-submission (item 47) ───────────────────────────────────────

def non_submission_flow() -> None:
    print("\n═══ Non-Submission Dashboard ═══")
    print("  A referral should rest on a pattern. Two missing out of")
    print("  three is a very different conversation from two out of 20.")
    try:
        subject = _input("Subject (blank for all)")
        minimum = _input("Minimum missing pieces",
                          default=str(analytics.CONCERN_THRESHOLD))
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        rows = analytics.non_submitters(subject_name=subject or None,
                                         minimum=int(minimum))
    except ValueError:
        print("\n  ✗ Minimum must be a number.")
        _pause()
        return
    if not rows:
        print("\n  (nobody over the threshold)")
        _pause()
        return
    print()
    print(f"  {'Student':<10}  {'Name':<22}  {'Missing':>8}  "
          f"{'Of':>4}  {'Rate':>7}  {'Level':<10}  Subjects")
    print("  " + "-" * 100)
    for row in rows:
        print(f"  {row.student_id:<10}  {row.student_name[:22]:<22}  "
              f"{row.missing:>8}  {row.total:>4}  {row.rate:>6g}%  "
              f"{row.level:<10}  {', '.join(row.subjects)[:28]}")
    referrals = [r for r in rows if r.needs_referral]
    print(f"\n  {len(rows)} flagged, {len(referrals)} at referral level.")
    _pause()


# ── Weighted grades (item 50) ──────────────────────────────────────

def weighted_flow() -> None:
    print("\n═══ Weighted Subject Grade ═══")
    print("  Built from the weighted pieces done so far, rescaled to")
    print("  the weight actually marked.")
    try:
        sid = _pick_student()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    rows = analytics.student_weighted_grades(sid)
    if not rows:
        print("\n  (no coursework)")
        _pause()
        return
    for row in rows:
        print(f"\n  {row.message}")
        for title, weight, percent in row.contributions:
            print(f"      {weight:>5g}%  {percent:>6g}%  {title[:40]}")
    _pause()


def weight_audit_flow() -> None:
    print("\n═══ Weighting Audit ═══")
    print("  Weights totalling 85% usually means a planned piece was")
    print("  never written — worth knowing before results day.")
    try:
        subject = _input("Subject", allow_empty=False)
        year = _input("Year group (blank for all)")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    audit = analytics.weight_audit(subject, year_group=year or None)
    print(f"\n  Weighted assignments: {audit['weighted_assignments']}")
    print(f"  Total weight        : {audit['total_weight']:g}%")
    print(f"  Balanced            : "
          f"{'yes' if audit['balanced'] else 'NO'}")
    if audit["assignments"]:
        print()
        for aid, title, weight in audit["assignments"]:
            print(f"      {weight:>5g}%  #{aid}  {title[:44]}")
    _pause()


def set_weight_flow() -> None:
    print("\n═══ Set Assignment Weighting ═══")
    try:
        a = _pick_assignment()
        weight = _input("Weight % of the subject grade",
                         default=(f"{a.weight_percent:g}"
                                   if a.weight_percent else ""))
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        out = assignments_store.update_assignment(a.assignment_id,
                                      {"weight_percent": weight or None})
    except assignments_models.ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{out.assignment_id} weighted "
          f"{_fmt(out.weight_percent)}%")
    audit = analytics.weight_audit(out.subject_name)
    print(f"    {out.subject_name} now totals "
          f"{audit['total_weight']:g}%")
    _pause()


# ── Clashes (item 40) ──────────────────────────────────────────────

def clashes_flow() -> None:
    print("\n═══ Deadline Clashes ═══")
    try:
        year = _input("Year group (blank for all)")
        threshold = _input("Deadlines per week to flag", default="2")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        rows = admin.clashes(year_group=year or None,
                              threshold=int(threshold))
    except ValueError:
        print("\n  ✗ Threshold must be a number.")
        _pause()
        return
    if not rows:
        print("\n  (no clashes)")
        _pause()
        return
    for clash in rows:
        print(f"\n  {clash.year_group or 'all years'} — "
              f"{clash.message}")
        for a in clash.assignments:
            print(f"      {a.due_date}  #{a.assignment_id}  "
                  f"{a.subject_name[:14]:<14}  {a.title[:32]}")
        suggestions = admin.suggest_reschedule(clash)
        for aid, title, moved in suggestions:
            print(f"      → consider moving #{aid} {title[:26]} "
                  f"to {moved}")
    print(f"\n  {len(rows)} clash(es).")
    _pause()


def student_clashes_flow() -> None:
    print("\n═══ One Student's Clashes ═══")
    print("  A student on an unusual combination can hit a clash their")
    print("  year group does not.")
    try:
        sid = _pick_student()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    rows = admin.student_clashes(sid)
    if not rows:
        print("\n  (no weeks with more than one deadline)")
        _pause()
        return
    for clash in rows:
        print(f"\n  {clash.message}")
        for a in clash.assignments:
            print(f"      {a.due_date}  {a.subject_name[:14]:<14}  "
                  f"{a.title[:36]}")
    _pause()


# ── Digests (item 41) ──────────────────────────────────────────────

def digest_flow() -> None:
    print("\n═══ Teacher Digest ═══")
    try:
        teacher = _input("Teacher", allow_empty=False)
        period = _pick_from("Period", list(admin.DIGEST_PERIODS),
                             default=admin.DEFAULT_DIGEST_PERIOD)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        digest = admin.build_digest(teacher, period=period)
    except assignments_models.ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print()
    print(digest.as_text())
    if digest.is_empty:
        _pause()
        return
    if _yes("Email it? (y/n)"):
        admin.send_digest(teacher, period=period, skip_if_empty=False)
        print("\n  ✓ Sent.")
    _pause()


def send_digests_flow() -> None:
    print("\n═══ Send All Digests ═══")
    print("  One per teacher with something outstanding. Teachers with")
    print("  nothing to do are skipped — an empty digest every morning")
    print("  trains people to ignore the useful ones.")
    try:
        period = _pick_from("Period", list(admin.DIGEST_PERIODS),
                             default=admin.DEFAULT_DIGEST_PERIOD)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if not _yes("Send now? (y/n)", default="y"):
        print("\n  Cancelled.")
        return
    sent = admin.send_all_digests(period=period)
    print(f"\n  ✓ {len(sent)} digest(s) sent.")
    for who, digest in sent.items():
        print(f"      {who:<26}  {digest.message}")
    _pause()


# ── Cover (item 42) ────────────────────────────────────────────────

def assign_cover_flow() -> None:
    print("\n═══ Assign Cover Marking ═══")
    print("  The substantive teacher stays on the assignment — editing")
    print("  the teacher field would lose who owns the work.")
    try:
        a = _pick_assignment()
        print(f"\n  Owned by: {a.teacher or '—'}")
        marker = _input("Cover marker", allow_empty=False)
        start = _input("From (YYYY-MM-DD)",
                        default=_dt.date.today().isoformat())
        until = _input("Until (blank for open-ended)")
        reason = _input("Reason")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        out = admin.assign_cover(a.assignment_id, cover_marker=marker,
                                  cover_from=start,
                                  cover_until=until or None,
                                  reason=reason or None)
    except assignments_models.ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ {out.cover_marker} marking #{out.assignment_id} "
          f"from {out.cover_from} "
          f"to {out.cover_until or 'further notice'}")
    print(f"    Owner remains {out.teacher or '—'}")
    _pause()


def cover_teacher_flow() -> None:
    print("\n═══ Cover a Teacher's Whole Load ═══")
    print("  What an office needs when somebody phones in sick: one")
    print("  instruction, not one per assignment.")
    try:
        teacher = _input("Teacher who is out", allow_empty=False)
        marker = _input("Cover marker", allow_empty=False)
        until = _input("Until (blank for open-ended)")
        reason = _input("Reason", default="Staff absence")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        rows = admin.cover_for_teacher(teacher, cover_marker=marker,
                                        cover_until=until or None,
                                        reason=reason or None)
    except assignments_models.ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ {len(rows)} assignment(s) now marked by {marker}:")
    for a in rows:
        print(f"      #{a.assignment_id}  {a.title[:44]}")
    _pause()


def end_cover_flow() -> None:
    print("\n═══ End Cover ═══")
    try:
        a = _pick_assignment()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if not a.cover_marker:
        print("\n  That assignment is not covered.")
        _pause()
        return
    out = admin.end_cover(a.assignment_id)
    print(f"\n  ✓ Marking returned to {out.teacher or '—'}")
    _pause()


def covered_flow() -> None:
    print("\n═══ Currently Covered ═══")
    rows = admin.list_covered()
    expired = admin.expired_cover()
    if not rows and not expired:
        print("\n  (nothing covered)")
        _pause()
        return
    if rows:
        print()
        print(f"  {'#':>4}  {'Owner':<20}  {'Cover':<20}  "
              f"{'From':<12}  {'Until':<12}  Reason")
        print("  " + "-" * 95)
        for a in rows:
            print(f"  {a.assignment_id:>4}  "
                  f"{(a.teacher or '—')[:20]:<20}  "
                  f"{(a.cover_marker or '—')[:20]:<20}  "
                  f"{(a.cover_from or '—'):<12}  "
                  f"{(a.cover_until or 'open'):<12}  "
                  f"{(a.cover_reason or '—')[:24]}")
    if expired:
        print(f"\n  {len(expired)} expired arrangement(s) still on "
              f"record (harmless, but worth tidying):")
        for a in expired:
            print(f"      #{a.assignment_id}  {a.cover_marker} "
                  f"until {a.cover_until}")
    _pause()


# ── Import and export (item 48) ────────────────────────────────────

def export_flow() -> None:
    print("\n═══ Export Marks ═══")
    print("  Raw mark, penalty and final mark go in separate columns —")
    print("  an export showing only the final figure cannot be")
    print("  reconciled later.")
    try:
        scope = _pick_from("Scope", ["One assignment", "A subject"],
                            default="One assignment")
        assignment_id = None
        subject = None
        if scope == "One assignment":
            assignment_id = _pick_assignment().assignment_id
        else:
            subject = _input("Subject", allow_empty=False)
        released = _yes("Released results only? (y/n)")
        path = _input("Write to file (blank to print)")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    text = admin.export_marks(assignment_id, subject_name=subject,
                               path=path or None,
                               released_only=released)
    rows = max(0, len(text.strip().splitlines()) - 1)
    if path:
        print(f"\n  ✓ {rows} row(s) written to {path}")
    else:
        print()
        for line in text.splitlines()[:25]:
            print(f"  {line}")
        if rows > 24:
            print(f"  ... {rows - 24} more row(s)")
    _pause()


def template_flow() -> None:
    print("\n═══ Blank Mark Sheet ═══")
    print("  Pre-filled with the cohort, so marks typed in on paper can")
    print("  be imported back without matching names by hand.")
    try:
        a = _pick_assignment()
        path = _input("Write to file (blank to print)")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    text = admin.export_template(a.assignment_id, path=path or None)
    if path:
        print(f"\n  ✓ Written to {path}")
    else:
        print()
        for line in text.splitlines():
            print(f"  {line}")
    _pause()


def import_flow() -> None:
    print("\n═══ Import Marks ═══")
    print("  Validated in full first: a file with one bad row is fixed")
    print("  and re-imported, not half-applied.")
    try:
        a = _pick_assignment()
        path = _input("CSV file path", allow_empty=False)
        marked_by = _input("Marked by", default=a.teacher or "")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        preview = admin.import_marks(path, a.assignment_id,
                                      dry_run=True)
    except (assignments_models.ValidationError, OSError) as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  {preview.message}")
    for row in preview.errors[:12]:
        print(f"    ✗ line {row.line}: {row.message}")
    if preview.errors:
        print("\n  Fix the file and try again, or import the good rows")
        print("  only.")
        if not _yes("Import the valid rows anyway? (y/n)"):
            print("\n  Cancelled.")
            return
    elif not _yes("Apply? (y/n)", default="y"):
        print("\n  Cancelled.")
        return
    result = admin.import_marks(path, a.assignment_id,
                                marked_by=marked_by or None,
                                allow_partial=True)
    print(f"\n  ✓ {result.message}")
    _pause()


def export_history_flow() -> None:
    print("\n═══ Export a Student's Record ═══")
    try:
        sid = _pick_student()
        path = _input("Write to file (blank to print)")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    text = admin.export_history(sid, path=path or None)
    if path:
        print(f"\n  ✓ Written to {path}")
    else:
        print()
        for line in text.splitlines():
            print(f"  {line}")
    _pause()


# ── Coversheets (item 49) ──────────────────────────────────────────

def coversheet_flow() -> None:
    print("\n═══ Coversheet ═══")
    try:
        a = _pick_assignment()
        sub = _pick_submission(a.assignment_id)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    print()
    print(admin.build_coversheet(sub.submission_id))
    _pause()


def print_coversheets_flow() -> None:
    print("\n═══ Print Coversheets ═══")
    try:
        a = _pick_assignment()
        directory = _input("Directory (blank for the coursework store)")
        feedback = _yes("Include feedback? (y/n)", default="y")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    written = admin.write_coversheets(a.assignment_id,
                                       directory=directory or None,
                                       include_feedback=feedback)
    print(f"\n  ✓ {len(written)} coversheet(s) written")
    if written:
        print(f"    to {written[0].parent}")
    _pause()


def sample_pack_flow() -> None:
    print("\n═══ Moderation Sample Pack ═══")
    print("  What actually goes to a moderator: the sample with marks")
    print("  and rubric breakdown, in one file rather than twelve.")
    try:
        a = _pick_assignment()
        path = _input("Write to file (blank to print)")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        text = admin.build_sample_pack(a.assignment_id)
    except assignments_models.ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    if path:
        from pathlib import Path
        Path(path).expanduser().write_text(text, encoding="utf-8")
        print(f"\n  ✓ Written to {path}")
    else:
        print()
        print(text[:3000])
    _pause()


# ── Submenu ────────────────────────────────────────────────────────

_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Student history",          history_flow),
    ("History by subject",       subject_breakdown_flow),
    ("Against target",           target_flow),
    ("Underperformers",          underperformers_flow),
    ("Declining students",       trend_flow),
    ("─" * 6,                    lambda: None),
    ("Cohort analytics",         cohort_flow),
    ("Criterion weak spots",     criterion_flow),
    ("Compare subjects/teachers", compare_flow),
    ("Non-submission dashboard", non_submission_flow),
    ("─" * 6,                    lambda: None),
    ("Weighted subject grade",   weighted_flow),
    ("Weighting audit",          weight_audit_flow),
    ("Set assignment weighting", set_weight_flow),
    ("─" * 6,                    lambda: None),
    ("Deadline clashes",         clashes_flow),
    ("One student's clashes",    student_clashes_flow),
    ("─" * 6,                    lambda: None),
    ("Teacher digest",           digest_flow),
    ("Send all digests",         send_digests_flow),
    ("─" * 6,                    lambda: None),
    ("Assign cover marking",     assign_cover_flow),
    ("Cover a whole load",       cover_teacher_flow),
    ("End cover",                end_cover_flow),
    ("Currently covered",        covered_flow),
    ("─" * 6,                    lambda: None),
    ("Export marks",             export_flow),
    ("Blank mark sheet",         template_flow),
    ("Import marks",             import_flow),
    ("Export a student record",  export_history_flow),
    ("─" * 6,                    lambda: None),
    ("Coversheet",               coversheet_flow),
    ("Print coversheets",        print_coversheets_flow),
    ("Moderation sample pack",   sample_pack_flow),
]


def run() -> None:
    admin.init_db()
    while True:
        print("\n── Analysis, Digests & Exports ──")
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
            logger.exception("Insight CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Insight":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Insight CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
