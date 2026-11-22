"""CLI: onboarding dashboard, outstanding-tasks report, CSV / PDF export
and the overdue chase log (all read-only, apart from the export file)."""

from __future__ import annotations

import os

from education_system.systems.sixth_form.domain.admissions.onboarding import (
    onboarding as data,
)
from education_system.systems.sixth_form.domain.admissions.onboarding import (
    onboarding_jobs as jobs,
)
from education_system.systems.sixth_form.domain.admissions.onboarding import (
    onboarding_reports as rep,
)
from education_system.systems.sixth_form.domain.admissions.onboarding import (
    templates as tpl,
)
from education_system.systems.sixth_form.interfaces.cli.admissions.onboarding.onboarding_cli import (
    _REFUSED,
    _input,
    _pause,
    _pick_checklist,
    _pick_from,
    _refused,
    _UserAbort,
    _yes_no,
)
from education_system.systems.sixth_form.interfaces.cli.admissions.onboarding.workflow_cli import (
    current_year,
)

_GROUP_LABELS = {"tutor_group": "Tutor group", "course": "Course",
                 "year_group": "Year group"}
_ANY = "(any)"


def _ask_year() -> str | None:
    raw = _input("Academic year ('all' for every year)",
                 default=current_year())
    return None if raw.lower() == "all" else raw


def _print_dashboard(rows: list[rep.DashboardRow], label: str) -> None:
    if not rows:
        print("\n  (no checklists)")
        return
    print(f"\n  {label:<24}  {'Learners':>8}  {'Lists':>5}  {'Done':>5}  "
          f"{'Tasks':>6}  {'% done':>6}  {'Overdue':>7}  {'Blocked':>7}")
    print("  " + "-" * 86)
    for r in rows:
        print(f"  {r.group[:24]:<24}  {r.learners:>8}  {r.checklists:>5}  "
              f"{r.completed:>5}  {r.tasks:>6}  {r.percent_complete:>6}  "
              f"{r.overdue:>7}  {r.blocked:>7}")


def dashboard_flow() -> None:
    print("\n═══ Onboarding Dashboard ═══")
    try:
        label = _pick_from("Group by", list(_GROUP_LABELS.values()),
                           default="Tutor group")
        group = next(k for k, v in _GROUP_LABELS.items() if v == label)
        year = _input("Academic year", default=current_year())
        open_only = _yes_no("Open checklists only?", default=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        rows = rep.dashboard(group, academic_year=year, open_only=open_only)
    except _REFUSED as e:
        return _refused(e)
    print(f"\n  {year} by {label.lower()}"
          + (" (open only)" if open_only else "")
          + (" — a learner counts once per subject" if group == "course"
             else ""))
    _print_dashboard(rows, label)
    _pause()


def _ask_filters() -> dict:
    kw: dict = {"academic_year": _ask_year()}
    kw["overdue_only"] = _yes_no("Overdue only?", default=False)
    kw["blocked_only"] = _yes_no("Blocked only?", default=False)
    kw["required_only"] = _yes_no("Required tasks only?", default=False)
    owner = _pick_from("Owner role", [_ANY, *tpl.OWNER_ROLES], default=_ANY)
    if owner != _ANY:
        kw["owner_role"] = owner
    cat = _pick_from("Category", [_ANY, *data.CATEGORIES], default=_ANY)
    if cat != _ANY:
        kw["category"] = cat
    tg = _input("Tutor group (blank = all)")
    if tg:
        kw["tutor_group"] = tg
    return kw


def outstanding_report_flow() -> None:
    print("\n═══ Outstanding Tasks Report ═══")
    try:
        kw = _ask_filters()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        rows = rep.outstanding_tasks(**kw)
    except _REFUSED as e:
        return _refused(e)
    print(f"\n  {'Due':<10}  {'Student':<10}  {'Name':<18}  {'Tutor':<6}  "
          f"{'Item':>5}  {'Status':<11}  {'Owner':<10}  {'Assigned':<10}  "
          "Task")
    print("  " + "-" * 110)
    for t in rows:
        flag = "LATE " if t.overdue else ""
        extra = (f"  [blocked: {t.blocked_reason}]"
                 if t.status == "Blocked" and t.blocked_reason else "")
        print(f"  {t.due_date or '—':<10}  {t.student_id:<10}  "
              f"{t.student_name[:18]:<18}  {(t.tutor_group or '—')[:6]:<6}  "
              f"{t.item_id:>5}  {t.status:<11}  "
              f"{(t.owner_role or '—')[:10]:<10}  "
              f"{(t.assigned_to or '—')[:10]:<10}  {flag}{t.task}{extra}")
    print(f"\n  {len(rows)} task(s), {sum(1 for t in rows if t.overdue)} "
          "overdue.")
    _pause()


def export_flow() -> None:
    print("\n═══ Export Onboarding Report ═══")
    kinds = {"Outstanding tasks": "outstanding",
             "Dashboard by tutor group": "tutor_group",
             "Dashboard by course": "course",
             "Dashboard by year group": "year_group"}
    try:
        label = _pick_from("Report", list(kinds), default="Outstanding tasks")
        kind = kinds[label]
        fmt = _pick_from("Format", ["CSV", "PDF"], default="CSV")
        kw = (_ask_filters() if kind == "outstanding"
              else {"academic_year": _input("Academic year",
                                            default=current_year())})
        path = os.path.abspath(os.path.expanduser(_input(
            f"Save to (file path, .{fmt.lower()})", allow_empty=False)))
        folder = os.path.dirname(path)
        if not os.path.isdir(folder):
            print(f"    The folder {folder} does not exist.")
            raise _UserAbort
        if os.path.exists(path) and not _yes_no(f"{path} exists — replace "
                                                "it?", default=False):
            raise _UserAbort
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        if fmt == "CSV":
            text = rep.export_csv(kind, path, **kw)
            n = max(0, len(text.splitlines()) - 1)
            print(f"\n  ✓ {n} row(s) written to {path}")
        else:
            rep.export_pdf(kind, path, **kw)
            print(f"\n  ✓ PDF written to {path}")
    except _REFUSED as e:
        return _refused(e)
    except OSError as e:
        return _refused(ValueError(f"Could not write {path}: {e}"))
    _pause()


def chase_log_flow() -> None:
    print("\n═══ Overdue Chase Log ═══")
    try:
        scope = _pick_from("Show", ["All checklists", "One checklist"],
                           default="All checklists")
        cid = _pick_checklist().checklist_id if scope == "One checklist" \
            else None
    except _UserAbort:
        print("\n  Cancelled.")
        return
    rows = jobs.chase_log(cid)
    print(f"\n  In-app reminders sent for overdue tasks (at most one per "
          f"checklist every {jobs.CHASE_EVERY_DAYS} days), newest first:")
    if not rows:
        print("    (no chases recorded)")
    for r in rows:
        print(f"    {r['chased_on']}  checklist #{r['checklist_id']:<5} "
              f"{r['recipient']:<14} {r['tasks']} overdue task(s)")
    _pause()
