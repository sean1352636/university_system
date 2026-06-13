"""CLI flows for Primary School Appraisals."""

from __future__ import annotations

import logging
from datetime import date as _date
from typing import Any, Callable
from education_system.nursery_system.modules.domain.appraisals import (
    appraisals as data,
)
from education_system.nursery_system.modules.domain.appraisals.appraisals import (
    Appraisal,
    DEFAULT_OBJECTIVE_STATUS,
    DEFAULT_OBJECTIVE_TYPE,
    DEFAULT_PAY_PROGRESSION,
    DEFAULT_STATUS,
    GRADES,
    OBJECTIVE_STATUSES,
    OBJECTIVE_TYPES,
    Objective,
    PAY_PROGRESSION,
    STATUSES,
    ValidationError,
    grade_label,
)
from education_system.nursery_system.modules.domain.staff import (
    staff as _staff,
)

logger = logging.getLogger(__name__)


class _UserAbort(Exception):
    pass


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
            return _input(prompt, default=default,
                            allow_empty=False)
        return ""
    return s


def _pause() -> None:
    try:
        input("\n  Press Enter to continue...")
    except (EOFError, KeyboardInterrupt):
        pass


def _yes_no(prompt: str, *, default: bool = False) -> bool:
    raw = _input(f"{prompt} (y/n)",
                  default="y" if default else "n").strip().lower()
    return raw in ("y", "yes")


def _multiline(prompt: str, *, default: str = "") -> str:
    print(f"\n  {prompt} (end with '.'; ENTER for default)")
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
        print(f"    {marker}{i:>2}) {opt or '(none)'}")
    while True:
        raw = _input(f"  Pick #1..{len(options)}",
                      default=default or "")
        if default and raw == default:
            return default
        if not raw.isdigit():
            print("    Enter a number.")
            continue
        n = int(raw)
        if not (1 <= n <= len(options)):
            print("    Out of range.")
            continue
        return options[n - 1]


def _pick_staff(*, optional: bool = False) -> str | None:
    rows = _staff.list_staff()
    if not rows:
        if optional:
            return None
        print("    No staff.")
        raise _UserAbort
    print("\n  Staff:")
    if optional:
        print("    0) (none)")
    for i, s in enumerate(rows, 1):
        full = f"{getattr(s, 'first_name', '')} " \
               f"{getattr(s, 'last_name', '')}".strip()
        print(f"    {i:>3}) {s.staff_id:<12}  {full}")
    while True:
        raw = _input(f"  Pick #1..{len(rows)}"
                      + (" (0 for none)" if optional else "")
                      + " (or id)",
                      allow_empty=optional)
        if optional and (not raw or raw == "0"):
            return None
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1].staff_id
        match = next((s for s in rows
                        if s.staff_id == raw.upper()), None)
        if match:
            return match.staff_id
        print("    No matching staff.")


def _pick_appraisal() -> Appraisal:
    rows = data.list_appraisals()
    if not rows:
        print("    No appraisals yet.")
        raise _UserAbort
    print("\n  Appraisals:")
    for i, a in enumerate(rows, 1):
        flag = "!" if a.mid_year_overdue else " "
        print(f"    {i:>3}){flag} #{a.appraisal_id}  "
              f"{a.staff_id:<12}  {a.cycle:<12}  "
              f"grade {a.overall_grade or '—'}  "
              f"[{a.status}]")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or id)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1]
            match = next((r for r in rows
                            if r.appraisal_id == n), None)
            if match:
                return match
        print("    No matching appraisal.")


def _pick_objective(appraisal_id: int) -> Objective:
    rows = data.list_objectives(appraisal_id)
    if not rows:
        print("    No objectives yet.")
        raise _UserAbort
    print("\n  Objectives:")
    for i, o in enumerate(rows, 1):
        print(f"    {i:>3}) O{o.objective_number}  "
              f"#{o.objective_id}  "
              f"{o.title[:38]:<38}  [{o.status}]")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or id)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1]
            match = next((r for r in rows
                            if r.objective_id == n), None)
            if match:
                return match
        print("    No matching objective.")


# ── Print helpers ────────────────────────────────────────

def _print_appraisals(rows: list[Appraisal]) -> None:
    if not rows:
        print("\n  (no appraisals)")
        return
    print()
    print(f"  {'#':>4}  {'Staff':<12}  {'Cycle':<12}  "
          f"{'Appraiser':<12}  {'Mid-Year':<10}  "
          f"{'End-Year':<10}  Grade  Pay   {'Status':<22}")
    print("  " + "-" * 130)
    for a in rows:
        print(f"  {a.appraisal_id:>4}  {a.staff_id:<12}  "
              f"{a.cycle:<12}  "
              f"{(a.appraiser_id or '—'):<12}  "
              f"{(a.mid_year_review_on or '—'):<10}  "
              f"{(a.end_year_review_on or '—'):<10}  "
              f"{a.overall_grade or '—':>5}  "
              f"{a.pay_progression[:5]:<5}  "
              f"{a.status}")
    print(f"\n  {len(rows)} appraisal(s).")


def _print_appraisal_full(a: Appraisal) -> None:
    print()
    print(f"    #{a.appraisal_id}  Staff {a.staff_id}  "
          f"Cycle {a.cycle}")
    print(f"    Appraiser            : "
          f"{a.appraiser_id or '—'}  "
          f"{a.appraiser_name or ''}")
    print(f"    Job role             : {a.job_role or '—'}")
    print(f"    Objectives set on    : "
          f"{a.objectives_set_on or '—'}")
    print(f"    Mid-year review      : "
          f"{a.mid_year_review_on or '—'}"
          + ("  (OVERDUE)"
              if a.mid_year_overdue else ""))
    print(f"    End-year review      : "
          f"{a.end_year_review_on or '—'}")
    print(f"    Self review complete : "
          f"{'yes' if a.self_review_completed else 'no'}")
    print(f"    Overall grade        : "
          f"{a.overall_grade or '—'}  ({a.grade_label})")
    print(f"    Upholding standards  : "
          f"{'yes' if a.upholding_standards else 'no'}")
    print(f"    Pay progression      : {a.pay_progression}")
    print(f"    Status               : {a.status}")
    for label, val in (
            ("Strengths",          a.strengths),
            ("Areas to develop",   a.areas_to_develop),
            ("CPD needs",          a.cpd_needs),
            ("Appraiser comments", a.appraiser_comments),
            ("Appraisee comments", a.appraisee_comments),
            ("Notes",              a.notes),
    ):
        if val:
            print(f"\n    {label}:")
            for line in val.splitlines():
                print(f"      {line}")
    objectives = data.list_objectives(a.appraisal_id)
    if objectives:
        print(f"\n    Objectives ({len(objectives)}):")
        for o in objectives:
            w = (f"  ({o.weighting:.0f}%)"
                  if o.weighting is not None else "")
            print(f"      O{o.objective_number}  "
                  f"[{o.objective_type}]  "
                  f"{o.title}  [{o.status}]{w}")


# ── Appraisal flows ──────────────────────────────────────

def appraisals_list() -> None:
    print("\n═══ All Appraisals ═══")
    _print_appraisals(data.list_appraisals())
    _pause()


def appraisals_open() -> None:
    print("\n═══ Open Appraisals ═══")
    _print_appraisals(data.list_appraisals(open_only=True))
    _pause()


def appraisals_mid_year_overdue() -> None:
    print("\n═══ Mid-Year Overdue ═══")
    _print_appraisals(data.list_appraisals(
        mid_year_overdue=True))
    _pause()


def appraisals_filter() -> None:
    print("\n═══ Filter Appraisals ═══")
    try:
        sid = _input("Staff id") or None
        cycle = _input("Cycle") or None
        status = _input(
            f"Status ({'/'.join(STATUSES[:3])}…)") or None
        grade_raw = _input("Grade (1-4)") or None
        pay = _input(
            f"Pay progression "
            f"({'/'.join(PAY_PROGRESSION)})") or None
        appr = _input("Appraiser staff id") or None
    except _UserAbort:
        print("\n  Cancelled.")
        return
    grade = (int(grade_raw) if grade_raw
              and grade_raw.isdigit() else None)
    try:
        rows = data.list_appraisals(staff_id=sid, cycle=cycle,
                                          status=status, grade=grade,
                                          pay_progression=pay,
                                          appraiser_id=appr)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    _print_appraisals(rows)
    _pause()


def appraisals_per_staff() -> None:
    print("\n═══ Per-Staff ═══")
    try:
        sid = _pick_staff()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _print_appraisals(data.list_appraisals(staff_id=sid))
    _pause()


def appraisals_view() -> None:
    print("\n═══ View Appraisal ═══")
    try:
        a = _pick_appraisal()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _print_appraisal_full(a)
    _pause()


def _collect_appraisal_form(
        existing: Appraisal | None) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    is_edit = existing is not None
    if is_edit:
        payload["staff_id"] = existing.staff_id
    else:
        payload["staff_id"] = _pick_staff()
    today = _date.today()
    default_cycle = f"{today.year}-{today.year + 1}"
    payload["cycle"] = _input(
        "Cycle (e.g. 2025-2026)",
        default=(existing.cycle if is_edit else default_cycle),
        allow_empty=False)
    if _yes_no("Set appraiser?",
               default=is_edit and bool(existing.appraiser_id)):
        try:
            payload["appraiser_id"] = _pick_staff(optional=True)
        except _UserAbort:
            payload["appraiser_id"] = None
    else:
        payload["appraiser_id"] = None
    payload["appraiser_name"] = _input(
        "Appraiser name",
        default=(existing.appraiser_name or "")
        if is_edit else "")
    payload["job_role"] = _input(
        "Job role",
        default=(existing.job_role or "") if is_edit else "")
    payload["objectives_set_on"] = _input(
        "Objectives set on (YYYY-MM-DD)",
        default=(existing.objectives_set_on or "")
        if is_edit else "")
    payload["mid_year_review_on"] = _input(
        "Mid-year review on (YYYY-MM-DD)",
        default=(existing.mid_year_review_on or "")
        if is_edit else "")
    payload["end_year_review_on"] = _input(
        "End-year review on (YYYY-MM-DD)",
        default=(existing.end_year_review_on or "")
        if is_edit else "")
    payload["self_review_completed"] = _yes_no(
        "Self review completed?",
        default=(existing.self_review_completed
                  if is_edit else False))
    payload["overall_grade"] = _input(
        "Overall grade (1-4, blank = none)",
        default=(str(existing.overall_grade)
                  if is_edit and existing.overall_grade is not None
                  else ""))
    payload["upholding_standards"] = _yes_no(
        "Upholding standards?",
        default=(existing.upholding_standards
                  if is_edit else True))
    payload["pay_progression"] = _pick_from(
        "Pay progression", list(PAY_PROGRESSION),
        default=(existing.pay_progression if is_edit
                  else DEFAULT_PAY_PROGRESSION))
    try:
        payload["strengths"] = _multiline(
            "Strengths",
            default=(existing.strengths or "")
            if is_edit else "")
        payload["areas_to_develop"] = _multiline(
            "Areas to develop",
            default=(existing.areas_to_develop or "")
            if is_edit else "")
        payload["cpd_needs"] = _multiline(
            "CPD needs",
            default=(existing.cpd_needs or "")
            if is_edit else "")
        payload["appraiser_comments"] = _multiline(
            "Appraiser comments",
            default=(existing.appraiser_comments or "")
            if is_edit else "")
        payload["appraisee_comments"] = _multiline(
            "Appraisee comments",
            default=(existing.appraisee_comments or "")
            if is_edit else "")
    except _UserAbort:
        raise
    payload["status"] = _pick_from(
        "Status", list(STATUSES),
        default=(existing.status if is_edit
                  else DEFAULT_STATUS))
    try:
        payload["notes"] = _multiline(
            "Notes",
            default=(existing.notes or "") if is_edit else "")
    except _UserAbort:
        raise
    return payload


def appraisals_new() -> None:
    print("\n═══ New Appraisal ═══")
    try:
        payload = _collect_appraisal_form(None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        a = data.create_appraisal(payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Created appraisal #{a.appraisal_id}")
    _pause()


def appraisals_edit() -> None:
    print("\n═══ Edit Appraisal ═══")
    try:
        a = _pick_appraisal()
        payload = _collect_appraisal_form(a)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_appraisal(a.appraisal_id, payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Updated #{a.appraisal_id}")
    _pause()


def appraisals_set_objectives() -> None:
    print("\n═══ Mark Objectives Set ═══")
    try:
        a = _pick_appraisal()
        when = _input("Objectives set on (YYYY-MM-DD)",
                        default=_date.today().isoformat())
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.set_objectives(a.appraisal_id,
                                objectives_set_on=when)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Objectives set on #{a.appraisal_id}")
    _pause()


def appraisals_record_mid_year() -> None:
    print("\n═══ Record Mid-Year Review ═══")
    try:
        a = _pick_appraisal()
        when = _input("Reviewed on (YYYY-MM-DD)",
                        default=_date.today().isoformat())
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.record_mid_year(a.appraisal_id, reviewed_on=when)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Mid-year recorded on #{a.appraisal_id}")
    _pause()


def appraisals_record_end_year() -> None:
    print("\n═══ Record End-Year Review ═══")
    try:
        a = _pick_appraisal()
        when = _input("Reviewed on (YYYY-MM-DD)",
                        default=_date.today().isoformat())
        grade_raw = _input("Overall grade (1-4)",
                              default=str(a.overall_grade)
                              if a.overall_grade else "")
        pay = _pick_from("Pay progression",
                             list(PAY_PROGRESSION),
                             default=a.pay_progression)
        upholding = _yes_no("Upholding standards?",
                              default=a.upholding_standards)
        strengths = _multiline("Strengths",
                                  default=a.strengths or "")
        areas = _multiline("Areas to develop",
                              default=a.areas_to_develop or "")
        cpd = _multiline("CPD needs",
                            default=a.cpd_needs or "")
        comments = _multiline("Appraiser comments",
                                  default=a.appraiser_comments or "")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    grade = (int(grade_raw) if grade_raw
              and grade_raw.isdigit() else None)
    try:
        data.record_end_year(
            a.appraisal_id, reviewed_on=when,
            overall_grade=grade,
            pay_progression=pay,
            upholding_standards=upholding,
            strengths=strengths or None,
            areas_to_develop=areas or None,
            cpd_needs=cpd or None,
            appraiser_comments=comments or None)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ End-year recorded on #{a.appraisal_id}")
    _pause()


def appraisals_close() -> None:
    print("\n═══ Close Appraisal ═══")
    try:
        a = _pick_appraisal()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.close_appraisal(a.appraisal_id)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{a.appraisal_id} → Closed")
    _pause()


def appraisals_set_status() -> None:
    print("\n═══ Change Status ═══")
    try:
        a = _pick_appraisal()
        new_status = _pick_from("New status", list(STATUSES),
                                  default=a.status)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.set_appraisal_status(a.appraisal_id, new_status)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{a.appraisal_id} → {new_status}")
    _pause()


def appraisals_delete() -> None:
    print("\n═══ Delete Appraisal ═══")
    try:
        a = _pick_appraisal()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if _input(f"Delete appraisal #{a.appraisal_id} "
              "(and all objectives)? Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_appraisal(a.appraisal_id):
        print(f"\n  ✓ Deleted #{a.appraisal_id}")
    _pause()


# ── Objective flows ─────────────────────────────────────

def objectives_list() -> None:
    print("\n═══ List Objectives ═══")
    try:
        a = _pick_appraisal()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    rows = data.list_objectives(a.appraisal_id)
    if not rows:
        print("\n  (none)")
    for o in rows:
        w = (f"  weighting {o.weighting:.0f}%"
              if o.weighting is not None else "")
        print(f"  O{o.objective_number}  "
              f"[{o.objective_type}]  "
              f"{o.title}  [{o.status}]{w}")
        if o.description:
            print(f"     {o.description[:100]}")
    _pause()


def objectives_add() -> None:
    print("\n═══ Add Objective ═══")
    try:
        a = _pick_appraisal()
        title = _input("Title", allow_empty=False)
        otype = _pick_from("Type", list(OBJECTIVE_TYPES),
                               default=DEFAULT_OBJECTIVE_TYPE)
        desc = _multiline("Description")
        target = _input("Target metric")
        criteria = _multiline("Success criteria")
        weighting_raw = _input("Weighting (%)")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    payload = {
        "title": title,
        "objective_type": otype,
        "description": desc or None,
        "target_metric": target or None,
        "success_criteria": criteria or None,
        "weighting": weighting_raw or None,
        "status": DEFAULT_OBJECTIVE_STATUS,
    }
    try:
        o = data.add_objective(a.appraisal_id, payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Added objective O{o.objective_number}")
    _pause()


def objectives_edit() -> None:
    print("\n═══ Edit Objective ═══")
    try:
        a = _pick_appraisal()
        o = _pick_objective(a.appraisal_id)
        title = _input("Title", default=o.title,
                          allow_empty=False)
        otype = _pick_from("Type", list(OBJECTIVE_TYPES),
                               default=o.objective_type)
        desc = _multiline("Description",
                              default=o.description or "")
        target = _input("Target metric",
                            default=o.target_metric or "")
        criteria = _multiline("Success criteria",
                                  default=o.success_criteria or "")
        progress = _multiline("Progress notes",
                                  default=o.progress_notes or "")
        mid = _multiline("Mid-year progress",
                            default=o.mid_year_progress or "")
        end_ev = _multiline("End-year evidence",
                                default=o.end_year_evidence or "")
        status = _pick_from("Status", list(OBJECTIVE_STATUSES),
                                default=o.status)
        weighting_raw = _input("Weighting (%)",
                                    default=str(o.weighting)
                                    if o.weighting is not None
                                    else "")
        reviewed_on = _input("Reviewed on (YYYY-MM-DD)",
                                  default=o.reviewed_on or "")
        notes = _multiline("Notes", default=o.notes or "")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    payload = {
        "title": title,
        "objective_type": otype,
        "description": desc or None,
        "target_metric": target or None,
        "success_criteria": criteria or None,
        "progress_notes": progress or None,
        "mid_year_progress": mid or None,
        "end_year_evidence": end_ev or None,
        "status": status,
        "weighting": weighting_raw or None,
        "reviewed_on": reviewed_on or None,
        "notes": notes or None,
    }
    try:
        data.update_objective(o.objective_id, payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Updated O{o.objective_number}")
    _pause()


def objectives_set_status() -> None:
    print("\n═══ Change Objective Status ═══")
    try:
        a = _pick_appraisal()
        o = _pick_objective(a.appraisal_id)
        new_status = _pick_from("New status",
                                  list(OBJECTIVE_STATUSES),
                                  default=o.status)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.set_objective_status(o.objective_id, new_status)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ O{o.objective_number} → {new_status}")
    _pause()


def objectives_delete() -> None:
    print("\n═══ Delete Objective ═══")
    try:
        a = _pick_appraisal()
        o = _pick_objective(a.appraisal_id)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if _input(f"Delete O{o.objective_number}? Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_objective(o.objective_id):
        print(f"\n  ✓ Deleted O{o.objective_number}")
    _pause()


# ── Summary ─────────────────────────────────────────────

def summary_flow() -> None:
    print("\n═══ Appraisals Summary ═══")
    s = data.summary()
    print(f"\n  Total appraisals       : {s.total}")
    print(f"  Open                   : {s.open_count}")
    print(f"  Mid-year overdue       : {s.mid_year_overdue}")
    print(f"  Completed              : {s.completed}")
    print(f"  Upholding standards    : {s.upholding_standards}")
    print(f"  Pay progression Yes    : {s.pay_progression_yes}")
    print(f"  Pay progression Defer  : {s.pay_progression_deferred}")
    print(f"  Distinct cycles        : {s.distinct_cycles}")
    print(f"  Average grade          : "
          f"{s.average_grade if s.average_grade is not None else '—'}")
    print(f"  Total objectives       : {s.total_objectives}")
    print(f"  Objectives achieved    : {s.objectives_achieved}")
    print("\n  By cycle:")
    for k, n in s.by_cycle.items():
        if n:
            print(f"    {k:<14}: {n}")
    print("\n  By status:")
    for k in STATUSES:
        n = s.by_status.get(k, 0)
        if n:
            print(f"    {k:<22}: {n}")
    print("\n  By grade:")
    for g in GRADES:
        n = s.by_grade.get(g, 0)
        if n:
            print(f"    {g}  {grade_label(g):<24}: {n}")
    print("\n  By pay progression:")
    for k in PAY_PROGRESSION:
        n = s.by_pay_progression.get(k, 0)
        if n:
            print(f"    {k:<16}: {n}")
    if s.by_objective_status:
        print("\n  By objective status:")
        for k in OBJECTIVE_STATUSES:
            n = s.by_objective_status.get(k, 0)
            if n:
                print(f"    {k:<22}: {n}")
    _pause()


_MENU: list[tuple[str, Callable[[], None]]] = [
    ("── Appraisals ──",       lambda: None),
    ("List all",               appraisals_list),
    ("Open only",              appraisals_open),
    ("Mid-year overdue",       appraisals_mid_year_overdue),
    ("Filter",                 appraisals_filter),
    ("Per-staff",              appraisals_per_staff),
    ("View",                   appraisals_view),
    ("New appraisal",          appraisals_new),
    ("Edit appraisal",         appraisals_edit),
    ("Mark objectives set",    appraisals_set_objectives),
    ("Record mid-year",        appraisals_record_mid_year),
    ("Record end-year",        appraisals_record_end_year),
    ("Close appraisal",        appraisals_close),
    ("Change status",          appraisals_set_status),
    ("Delete appraisal",       appraisals_delete),
    ("── Objectives ──",       lambda: None),
    ("List objectives",        objectives_list),
    ("Add objective",          objectives_add),
    ("Edit objective",         objectives_edit),
    ("Change objective status", objectives_set_status),
    ("Delete objective",       objectives_delete),
    ("──",                     lambda: None),
    ("Summary",                summary_flow),
]


def run() -> None:
    while True:
        print("\n── Appraisals ──")
        for i, (label, _) in enumerate(_MENU, 1):
            if label.startswith("─"):
                print(f"      {label}")
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
            logger.exception("Appraisals CLI crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Appraisals":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Appraisals CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
