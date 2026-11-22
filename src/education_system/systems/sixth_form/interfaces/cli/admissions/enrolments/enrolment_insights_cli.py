"""Enrolment CLI: course changes (window, override, log, settings),
capacity checks (class sizes, tutor group sizes, a learner's timetable),
targets and reports, and the enrolment data check (reconcile).

Refusals (ValidationError, AccessDenied) are raised to the submenu, which
prints the message; flows that keep a loop going show them in place."""

from __future__ import annotations

import logging

from education_system.systems.sixth_form.domain.admissions.enrolments import course_changes
from education_system.systems.sixth_form.domain.admissions.enrolments import enrolment_checks
from education_system.systems.sixth_form.domain.admissions.enrolments import enrolment_reports
from education_system.systems.sixth_form.domain.admissions.enrolments import enrolments as data
from education_system.systems.sixth_form.domain.admissions.enrolments import reconcile
from education_system.systems.sixth_form.interfaces.cli.admissions.enrolments._common import (
    _UserAbort,
    _default_academic_year,
    _input,
    _offer_csv,
    _pause,
    _pick_enrolment_for,
    _pick_from,
    _pick_student,
    _prompt_academic_year,
    _writes_ok,
)

logger = logging.getLogger(__name__)


# ── Course changes ──────────────────────────────────────────────────

def _subjects() -> list[str]:
    try:
        from education_system.systems.sixth_form.domain.academics.subjects import (
            subjects,
        )
        return subjects.get_active_names()
    except Exception:  # noqa: BLE001 — typing a subject still works
        logger.exception("Could not list subjects")
        return []


def change_course() -> None:
    """Swap one of the learner's subjects inside the change window; after
    the cut-off an override reason is required."""
    print("\n═══ Course Change ═══")
    if not _writes_ok():
        return
    try:
        e = _pick_enrolment_for()
        if e is None:
            return
        window = course_changes.change_window(e.enrolment_id)
        print(f"\n  #{e.enrolment_id} {e.student_id} {e.academic_year} Year "
              f"{e.year_group} — change window: {window}")
        aims = data.aims_for_enrolment(e)
        if not aims:
            print("  ✗ No active learning aims in this enrolment's year.")
            _pause()
            return
        pick = _pick_from("Aim to change", [f"#{a.aim_id} {a.label}" for a in aims])
        aim_id = int(pick.split()[0].lstrip("#"))
        names = _subjects()
        if names:
            print("\n  Subjects: " + ", ".join(f"{i}) {n}" for i, n in enumerate(names, 1)))
        raw = _input("New subject (# or name)", allow_empty=False)
        new_subject = (names[int(raw) - 1] if raw.isdigit() and names
                       and 1 <= int(raw) <= len(names) else raw)
        new_type = _input("New qualification type (blank = same)") or None
        eff = _input("Effective date (YYYY-MM-DD; blank = today)") or None
        reason = _input("Reason (required)", allow_empty=False)
        approved = _input("Approved by (required)", allow_empty=False)
        override = None
        if not window.is_open:
            print(f"  The window closed on {window.cutoff}.")
            override = _input("Override reason (required to go ahead)",
                              allow_empty=False)
        if _input("Make the change? Type 'yes' to confirm",
                  default="no").lower() != "yes":
            print("\n  Cancelled.")
            return
    except _UserAbort:
        print("\n  Cancelled.")
        return
    res = course_changes.change_course(
        e.enrolment_id, aim_id, new_subject, new_type, effective_date=eff,
        reason=reason, approved_by=approved, override_reason=override)
    print(f"\n  {'✓' if res.ok else '⚠'} {res.from_label} → {res.to_label} from "
          f"{res.effective_date}" + ("  (override used)" if res.override_used else ""))
    if res.qualifying_met is not None:
        print(f"    Qualifying period met on the old aim: "
              f"{'yes' if res.qualifying_met else 'no'}")
    for line in res.lines:
        print(f"    • {line}")
    for p in res.problems:
        print(f"    ✗ {p}")
    _pause()


def course_change_log() -> None:
    print("\n═══ Course Change Log ═══")
    try:
        year = _prompt_academic_year(_default_academic_year())
    except _UserAbort:
        print("\n  Cancelled.")
        return
    rows = course_changes.change_log(year)
    for r in rows:
        print(f"    {r['effective_date'] or '—'}  {r['student_id']:<10} "
              f"{r['from'] or '—'} → {r['to'] or '—'}  ({r['reason'] or '—'}; "
              f"approved {r['approved_by'] or '—'}, by {r['recorded_by'] or '—'})")
    if not rows:
        print("    (no course changes)")
    _offer_csv(rows, "course_changes.csv")
    _pause()


_SETTING_LABELS = {
    course_changes.CHANGE_CUTOFF_DAYS: "Course-change cut-off (days after start)",
    course_changes.TUTOR_GROUP_LIMIT: "Tutor group size limit",
    course_changes.VISA_WARNING_DAYS: "Visa expiry warning (days)",
}


def enrolment_settings() -> None:
    while True:
        print("\n═══ Enrolment Settings ═══")
        keys = list(course_changes.DEFAULTS)
        for i, (k, v) in enumerate(course_changes.settings().items(), 1):
            print(f"  {i}) {_SETTING_LABELS.get(k, k):<44} {v}"
                  f"   (default {course_changes.DEFAULTS[k]})")
        print("\n  S) Set a value   H) History   (Enter to go back)")
        try:
            choice = _input("Action").lower()
            if not choice:
                return
            if choice == "h":
                for h in course_changes.settings_history():
                    print(f"    {h['changed_at'][:16]}  {_SETTING_LABELS.get(h['key'], h['key'])}: "
                          f"{h['old_value']} → {h['new_value']} by {h.get('changed_by') or '—'}")
                if not course_changes.settings_history():
                    print("    (never changed)")
                continue
            if choice != "s":
                print("  ✗ Pick S or H.")
                continue
            pick = _pick_from("Setting", [_SETTING_LABELS.get(k, k) for k in keys])
            key = keys[[_SETTING_LABELS.get(k, k) for k in keys].index(pick)]
            value = _input("New value", default=str(course_changes.get_setting(key)))
        except _UserAbort:
            return
        try:
            n = course_changes.set_setting(key, value)
            print(f"  ✓ {pick}: {n}")
        except (ValueError, PermissionError) as exc:
            print(f"  ✗ {exc}")


# ── Capacity checks ─────────────────────────────────────────────────

def class_sizes() -> None:
    print("\n═══ Class Sizes ═══")
    try:
        year = _prompt_academic_year(_default_academic_year())
    except _UserAbort:
        print("\n  Cancelled.")
        return
    rows = enrolment_checks.class_size_report(year)
    for r in rows:
        flag = "  OVER" if r.over else ("  full" if r.full else "")
        cap = f"{r.members}/{r.cap}" if r.cap else f"{r.members} (no cap)"
        print(f"    {r.course_code:<10} {r.subject[:20]:<20} Y{r.year_group} "
              f"{r.group_name[:16]:<16} {cap}{flag}")
    if not rows:
        print("    (no class groups)")
    _offer_csv(rows, "class_sizes.csv")
    _pause()


def tutor_group_sizes() -> None:
    print("\n═══ Tutor Group Sizes ═══")
    rows = enrolment_checks.tutor_group_sizes()
    for r in rows:
        print(f"    Y{r.year_group}  {r}" + (f"  (tutor {r.tutor})" if r.tutor else ""))
    if not rows:
        print("    (no tutor groups)")
    _offer_csv(rows, "tutor_group_sizes.csv")
    _pause()


def learner_timetable() -> None:
    print("\n═══ Learner Timetable ═══")
    try:
        sid = _pick_student()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    rows = enrolment_checks.learner_timetable(sid)
    for r in rows:
        print(f"    {r.day:<9} P{r.period} {r.start}-{r.end}  {r.group_name:<16} "
              f"{r.course_code or '':<10} {r.room or '':<8} {r.teacher or ''}")
    if not rows:
        print("    (not in any timetabled class group)")
    _pause()


def run_enrolment_checks() -> None:
    print("\n═══ Enrolment Checks — One Learner ═══")
    from education_system.systems.sixth_form.interfaces.cli.admissions.enrolments._common import (
        _show_checks,
    )
    try:
        sid = _pick_student(include_leavers=True)
        year = _prompt_academic_year(_default_academic_year())
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _show_checks(sid, year)
    _pause()


# ── Targets and reports ─────────────────────────────────────────────

def targets_admin() -> None:
    while True:
        print("\n═══ Enrolment Targets ═══")
        rows = enrolment_reports.list_targets()
        for t in rows:
            print(f"    #{t.target_id:<4} {t.academic_year}  {t.label:<36} {t.target}"
                  f"  (set {(t.set_at or '')[:10]} by {t.set_by or '—'})")
        if not rows:
            print("    (no targets)")
        print("\n  S) Set / replace   D) Delete   (Enter to go back)")
        try:
            choice = _input("Action").lower()
            if not choice:
                return
            if choice == "s":
                year = _prompt_academic_year(_default_academic_year())
                yg = int(_pick_from("Year group", ["12", "13"], default="12"))
                programme = _input("Programme (optional)") or None
                subject = _input("Subject (optional)") or None
                target = _input("Target number of learners", allow_empty=False)
                t = enrolment_reports.set_target(year, yg, int(target),
                                                 programme=programme, subject=subject)
                print(f"  ✓ {t.academic_year} {t.label}: {t.target}")
            elif choice == "d":
                tid = int(_input("Target #", allow_empty=False).lstrip("#"))
                print("  ✓ Deleted" if enrolment_reports.delete_target(tid)
                      else f"  No target #{tid}")
            else:
                print("  ✗ Pick S or D.")
        except _UserAbort:
            return
        except (ValueError, PermissionError) as exc:  # bad number / refusal
            print(f"  ✗ {exc}")


def targets_vs_actuals() -> None:
    print("\n═══ Targets vs Actuals ═══")
    try:
        year = _prompt_academic_year(_default_academic_year())
    except _UserAbort:
        print("\n  Cancelled.")
        return
    rows = enrolment_reports.targets_vs_actuals(year)
    for r in rows:
        label = " ".join(x for x in (f"Year {r.year_group}", r.programme or "",
                                     r.subject or "") if x)
        pct = f"{r.pct_of_target:.0f}%" if r.pct_of_target is not None else "—"
        print(f"    {label:<36} target {r.target:<5} actual {r.actual:<5} "
              f"{r.variance:+d}  ({pct})")
    if not rows:
        print("    (no targets set for this year)")
    _offer_csv(rows, "targets_vs_actuals.csv")
    subjects = enrolment_reports.subject_actuals(year)
    if subjects:
        print("\n    Learners per subject:")
        for s in subjects:
            print(f"      Y{s.year_group} {s.qualification_type:<14} {s.subject:<24} "
                  f"{s.learners}")
        _offer_csv(subjects, "subject_actuals.csv")
    _pause()


def withdrawal_analytics() -> None:
    print("\n═══ Withdrawal Analytics ═══")
    try:
        year = _prompt_academic_year(_default_academic_year())
    except _UserAbort:
        print("\n  Cancelled.")
        return
    w = enrolment_reports.withdrawal_analytics(year)
    print(f"\n  {w.academic_year}: {w.starts} start(s), {w.withdrawals} withdrawal(s) "
          f"after the qualifying period, {w.early_leavers} early leaver(s); retention "
          + (f"{w.retention_pct:.1f}%" if w.retention_pct is not None else "—"))
    for dim, values in (("By ILR reason", w.by_reason), ("By month", w.by_month),
                        ("By year group", w.by_year_group),
                        ("By tutor group", w.by_tutor_group)):
        if values:
            print(f"    {dim}:")
            for k, v in values.items():
                print(f"      {str(k)[:46]:<46} {v}")
    _offer_csv(w.breakdown_rows(), "withdrawal_analytics.csv")
    _pause()


def status_counts_report() -> None:
    print("\n═══ Status Counts ═══")
    try:
        all_years = _input("All years? (y/n)", default="n").lower().startswith("y")
        year = None if all_years else _prompt_academic_year(_default_academic_year())
    except _UserAbort:
        print("\n  Cancelled.")
        return
    rows = enrolment_reports.status_counts(year)
    for r in rows:
        print(f"    {r.academic_year}  Year {r.year_group}  {r.status:<10} {r.count}")
    if not rows:
        print("    (no enrolments)")
    _offer_csv(rows, "status_counts.csv")
    _pause()


def return_intentions_report() -> None:
    print("\n═══ Year 12 Return Intentions (report) ═══")
    try:
        year = _prompt_academic_year(_default_academic_year())
    except _UserAbort:
        print("\n  Cancelled.")
        return
    rows = enrolment_reports.return_intentions(year)
    for r in rows:
        print(f"    {r['intention']:<14} {r['learners']}")
    _offer_csv(rows, "return_intentions.csv")
    _pause()


# ── Data check ──────────────────────────────────────────────────────

def data_check() -> None:
    """Find enrolment records that disagree with each other (and with the
    student record, aims and tutor groups); writers can repair the ones
    marked fixable."""
    print("\n═══ Enrolment Data Check ═══")
    issues = reconcile.check()
    counts = reconcile.summary(issues)
    print("\n  Summary:")
    for kind, n in counts.items():
        print(f"    {reconcile.KIND_LABELS.get(kind, kind):<52} {n}")
    if not issues:
        print("\n  ✓ No issues found.")
        _pause()
        return
    print(f"\n  {len(issues)} issue(s):")
    for i, issue in enumerate(issues, 1):
        where = f"#{issue.enrolment_id}" if issue.enrolment_id is not None else ""
        aim = f" aim #{issue.aim_id}" if issue.aim_id is not None else ""
        print(f"  {i:>3}) {issue.label} — {issue.student_id} {where}{aim}"
              + ("" if issue.fixable else "  [report only]"))
        print(f"         {issue.detail}")
        print(f"         Fix: {issue.fix_hint}")
    if not data.can_write():
        print("\n  (Repairs need the admissions or students.manage permission.)")
        _pause()
        return
    fixable = [i for i in issues if i.fixable]
    if not fixable:
        print("\n  None of these can be repaired here — follow the hints.")
        _pause()
        return
    kinds = sorted({i.kind for i in fixable})
    print("\n  Repair: issue numbers (e.g. 1 3 4), a check name ("
          + ", ".join(kinds) + "), or blank to leave.")
    try:
        raw = _input("Repair which")
        if not raw:
            return
        selection: list[str] = []
        for tok in raw.replace(",", " ").split():
            if tok in reconcile.KINDS:
                if tok not in kinds:
                    print(f"    {tok}: nothing fixable of that kind — skipped")
                    continue
                selection.append(tok)
            elif tok.isdigit() and 1 <= int(tok) <= len(issues):
                issue = issues[int(tok) - 1]
                if not issue.fixable:
                    print(f"    {tok}: report only — can't be repaired here, skipped")
                    continue
                selection.append(issue.issue_id)
            else:
                print(f"    {tok}: not an issue number or check name — skipped")
        if not selection:
            print("  Nothing to repair.")
            _pause()
            return
        if not _input(f"Repair {len(selection)} selection(s)? (y/n)",
                      default="n").lower().startswith("y"):
            print("  Cancelled.")
            return
    except _UserAbort:
        print("\n  Cancelled.")
        return
    lines = reconcile.fix(selection=selection)  # re-checks first
    print()
    for line in lines:
        print(f"    • {line}")
    if not lines:
        print("    (nothing changed)")
    _pause()


COURSE_MENU = [
    ("Course change", change_course),
    ("Course change log", course_change_log),
    ("Enrolment settings (view / set / history)", enrolment_settings),
    ("Class sizes", class_sizes),
    ("Tutor group sizes", tutor_group_sizes),
    ("Learner timetable", learner_timetable),
    ("Enrolment checks — one learner", run_enrolment_checks),
    ("Data check (find / repair)", data_check),
]

REPORT_MENU = [
    ("Targets (set / list / delete)", targets_admin),
    ("Targets vs actuals", targets_vs_actuals),
    ("Withdrawal analytics", withdrawal_analytics),
    ("Status counts", status_counts_report),
    ("Return intentions", return_intentions_report),
]
