"""CLI flows for Sixth Form Target Setting."""

from __future__ import annotations

import logging
from datetime import date as _date
from typing import Any, Callable
from education_system.post_16.sixthform_system.modules.domain.assessment.target_setting import (
    target_setting as data,
)
from education_system.post_16.sixthform_system.modules.domain.students.students import (
    students as student_data,
)
from education_system.post_16.sixthform_system.modules.domain.assessment.target_setting.target_setting import (
    A_LEVEL_GRADES,
    DEFAULT_STATUS,
    PROGRESS_TAGS,
    Review,
    STATUSES,
    Target,
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


def _pick_grade(label: str, *,
                 default: str | None = None,
                 allow_empty: bool = False) -> str | None:
    options = list(A_LEVEL_GRADES) if not allow_empty \
        else [""] + list(A_LEVEL_GRADES)
    res = _pick_from(label, options, default=default)
    return res or None


def _pick_subject() -> str:
    try:
        from education_system.post_16.sixthform_system.modules.domain.academics.subjects import (
            subjects as _subjects,
        )
        names = [s.name for s in _subjects.list_subjects()]
    except Exception:
        names = []
    if not names:
        return _input("Subject", allow_empty=False)
    return _pick_from("Subject", names)


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


def _pick_target() -> Target:
    rows = data.list_targets()
    if not rows:
        print("    No targets yet.")
        raise _UserAbort
    names = {s.student_id: s.full_name
              for s in student_data.list_students()}
    print("\n  Targets:")
    for i, t in enumerate(rows, 1):
        print(f"    {i:>3}) #{t.target_id}  {t.student_id}  "
              f"{names.get(t.student_id, '?')[:14]:<14}  "
              f"{t.subject_name[:18]:<18}  "
              f"MTE={t.mte_grade}  cur={t.current_grade or '—'}  "
              f"[{t.status}]")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or id)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1]
            match = next((t for t in rows if t.target_id == n), None)
            if match:
                return match
        print("    No matching target.")


def _pick_review(target_id: int) -> Review:
    rows = data.list_reviews(target_id=target_id)
    if not rows:
        print("    No reviews on this target.")
        raise _UserAbort
    print("\n  Reviews:")
    for i, r in enumerate(rows, 1):
        print(f"    {i:>3}) #{r.review_id}  {r.review_date}  "
              f"current={r.current_grade or '—'}  "
              f"on_track={r.on_track or '—'}  "
              f"by {r.reviewer or '—'}")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or id)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1]
            match = next((r for r in rows if r.review_id == n), None)
            if match:
                return match
        print("    No matching review.")


# ── Print helpers ──────────────────────────────────────────────────

def _print_targets(rows: list[Target]) -> None:
    if not rows:
        print("\n  (no targets)")
        return
    names = {s.student_id: s.full_name
              for s in student_data.list_students()}
    print()
    print(f"  {'#':>4}  {'Student':<10}  {'Name':<20}  "
          f"{'Subject':<20}  {'MTE':<4}  {'Asp':<4}  "
          f"{'Cur':<4}  {'Δ':>4}  Status")
    print("  " + "-" * 110)
    for t in rows:
        delta = t.points_vs_target
        delta_s = (f"{delta:+d}" if delta is not None else "—")
        print(f"  {t.target_id:>4}  {t.student_id:<10}  "
              f"{names.get(t.student_id, '?')[:20]:<20}  "
              f"{t.subject_name[:20]:<20}  "
              f"{t.mte_grade:<4}  "
              f"{(t.aspirational_grade or '—'):<4}  "
              f"{(t.current_grade or '—'):<4}  "
              f"{delta_s:>4}  {t.status}")
    print(f"\n  {len(rows)} target(s).")


def _print_target_full(t: Target) -> None:
    detail = data.get_target_detail(t.target_id)
    print()
    print(f"    #{t.target_id}  {t.student_id} × {t.subject_name}")
    print(f"    Year group       : {t.year_group or '—'}")
    print(f"    MTE              : {t.mte_grade}")
    print(f"    Aspirational     : {t.aspirational_grade or '—'}")
    print(f"    Current          : {t.current_grade or '—'}")
    delta = t.points_vs_target
    print(f"    Vs MTE           : "
          f"{(format(delta, '+d') if delta is not None else '—')}")
    print(f"    Status           : {t.status}")
    print(f"    Baseline ref     : "
          f"{('#' + str(t.baseline_record_id)) if t.baseline_record_id else '—'}")
    print(f"    Set on           : {t.set_on or '—'}")
    print(f"    Set by           : {t.set_by or '—'}")
    print(f"    Last reviewed    : {t.last_reviewed or '—'}")
    print(f"    Next review due  : {t.next_review_due or '—'}")
    if t.rationale:
        print()
        print("    Rationale:")
        for line in t.rationale.splitlines():
            print(f"      {line}")
    if t.notes:
        print()
        print("    Notes:")
        for line in t.notes.splitlines():
            print(f"      {line}")
    if detail and detail.reviews:
        print()
        print(f"    Reviews ({len(detail.reviews)}):")
        for r in detail.reviews:
            print(f"      #{r.review_id}  {r.review_date}  "
                  f"cur={r.current_grade or '—'}  "
                  f"on_track={r.on_track or '—'}  "
                  f"by {r.reviewer or '—'}")
            if r.comments:
                for line in r.comments.splitlines():
                    print(f"        {line}")


# ── Target flows ───────────────────────────────────────────────────

def list_all() -> None:
    print("\n═══ All Targets ═══")
    _print_targets(data.list_targets())
    _pause()


def list_at_risk() -> None:
    print("\n═══ At-Risk / Below Target ═══")
    _print_targets(data.list_targets(at_risk_only=True))
    _pause()


def list_on_track() -> None:
    print("\n═══ On-Track / Above / Met ═══")
    _print_targets(data.list_targets(on_track_only=True))
    _pause()


def list_overdue_reviews() -> None:
    print("\n═══ Review Overdue ═══")
    _print_targets(data.list_targets(review_overdue=True))
    _pause()


def filter_flow() -> None:
    print("\n═══ Filter Targets ═══")
    try:
        sid = _input("Student id") or None
        subject = _input("Subject") or None
        status = _input(f"Status ({'/'.join(STATUSES)})") or None
        year = _input(f"Year ({'/'.join(YEAR_GROUPS)})") or None
        mte = _input(f"MTE ({'/'.join(A_LEVEL_GRADES)})") or None
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        rows = data.list_targets(
            student_id=sid, subject_name=subject,
            status=status, year_group=year, mte_grade=mte,
        )
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    _print_targets(rows)
    _pause()


def per_student_flow() -> None:
    print("\n═══ Per-Student Targets ═══")
    try:
        sid = _pick_student()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _print_targets(data.list_targets(student_id=sid))
    _pause()


def view_flow() -> None:
    print("\n═══ View Target ═══")
    try:
        t = _pick_target()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _print_target_full(t)
    _pause()


def _collect_form(existing: Target | None) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    is_edit = existing is not None
    if is_edit:
        payload["student_id"] = existing.student_id
        payload["subject_name"] = existing.subject_name
        print(f"\n  Editing {existing.student_id} × "
              f"{existing.subject_name}")
    else:
        payload["student_id"] = _pick_student()
        payload["subject_name"] = _pick_subject()
    payload["year_group"] = _pick_from(
        "Year group", [""] + list(YEAR_GROUPS),
        default=(existing.year_group if is_edit else ""))
    payload["mte_grade"] = _pick_grade(
        "Minimum target (MTE)",
        default=(existing.mte_grade if is_edit else None))
    payload["aspirational_grade"] = _pick_grade(
        "Aspirational target",
        default=(existing.aspirational_grade if is_edit else None),
        allow_empty=True)
    payload["current_grade"] = _pick_grade(
        "Current grade (optional)",
        default=(existing.current_grade if is_edit else None),
        allow_empty=True)
    payload["baseline_record_id"] = _input(
        "Baseline record id (optional)",
        default=(str(existing.baseline_record_id)
                  if is_edit and existing.baseline_record_id else ""))
    payload["set_on"] = _input(
        "Set on (YYYY-MM-DD)",
        default=(existing.set_on if is_edit
                  else _date.today().isoformat()))
    payload["set_by"] = _input(
        "Set by",
        default=(existing.set_by or "") if is_edit else "")
    payload["next_review_due"] = _input(
        "Next review due (YYYY-MM-DD, optional)",
        default=(existing.next_review_due or "") if is_edit else "")
    payload["status"] = _pick_from(
        "Status (auto-derived from current grade)",
        list(STATUSES),
        default=(existing.status if is_edit else DEFAULT_STATUS))
    payload["rationale"] = _input(
        "Rationale",
        default=(existing.rationale or "") if is_edit else "")
    payload["notes"] = _input(
        "Notes",
        default=(existing.notes or "") if is_edit else "")
    return payload


def new_target() -> None:
    print("\n═══ New Target ═══")
    try:
        payload = _collect_form(None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        t = data.create_target(payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Created target #{t.target_id} "
          f"(MTE={t.mte_grade}, status={t.status})")
    _pause()


def edit_target() -> None:
    print("\n═══ Edit Target ═══")
    try:
        t = _pick_target()
        payload = _collect_form(t)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_target(t.target_id, payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Updated #{t.target_id}")
    _pause()


def set_current_flow() -> None:
    print("\n═══ Set Current Grade ═══")
    try:
        t = _pick_target()
        new_grade = _pick_grade("New current grade",
                                  default=t.current_grade,
                                  allow_empty=True)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        upd = data.set_current_grade(t.target_id, new_grade)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{t.target_id} current={upd.current_grade or '—'}  "
          f"status={upd.status}")
    _pause()


def set_status_flow() -> None:
    print("\n═══ Change Status ═══")
    try:
        t = _pick_target()
        new_status = _pick_from("New status", list(STATUSES),
                                  default=t.status)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.set_status(t.target_id, new_status)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{t.target_id} → {new_status}")
    _pause()


def delete_target_flow() -> None:
    print("\n═══ Delete Target ═══")
    try:
        t = _pick_target()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if _input(f"Delete target #{t.target_id}? "
              "Reviews go too. Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_target(t.target_id):
        print(f"\n  ✓ Deleted #{t.target_id}")
    _pause()


# ── Review flows ──────────────────────────────────────────────────

def add_review_flow() -> None:
    print("\n═══ Add Review ═══")
    try:
        t = _pick_target()
        review_date = _input("Review date",
                               default=_date.today().isoformat())
        current = _pick_grade(
            "Current grade",
            default=t.current_grade, allow_empty=True)
        on_track = _pick_from(
            "On track?", [""] + list(PROGRESS_TAGS),
            default="")
        reviewer = _input("Reviewer", default=t.set_by or "")
        comments = _input("Comments")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        r = data.add_review(
            t.target_id, review_date=review_date,
            current_grade=current,
            on_track=on_track or None,
            reviewer=reviewer or None,
            comments=comments or None,
        )
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Added review #{r.review_id} "
          f"(target now current={current or '—'})")
    _pause()


def list_reviews_flow() -> None:
    print("\n═══ Reviews for Target ═══")
    try:
        t = _pick_target()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    rows = data.list_reviews(target_id=t.target_id)
    if not rows:
        print("\n  (no reviews)")
    else:
        print()
        print(f"  {'#':>4}  {'Date':<10}  {'Current':<8}  "
              f"{'On Track':<14}  Reviewer")
        print("  " + "-" * 60)
        for r in rows:
            print(f"  {r.review_id:>4}  {r.review_date:<10}  "
                  f"{(r.current_grade or '—'):<8}  "
                  f"{(r.on_track or '—')[:14]:<14}  "
                  f"{r.reviewer or '—'}")
    _pause()


def edit_review_flow() -> None:
    print("\n═══ Edit Review ═══")
    try:
        t = _pick_target()
        r = _pick_review(t.target_id)
        date_str = _input("Date", default=r.review_date,
                            allow_empty=False)
        current = _pick_grade(
            "Current grade",
            default=r.current_grade, allow_empty=True)
        on_track = _pick_from(
            "On track?", [""] + list(PROGRESS_TAGS),
            default=r.on_track or "")
        reviewer = _input("Reviewer", default=r.reviewer or "")
        comments = _input("Comments", default=r.comments or "")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_review(r.review_id, {
            "review_date": date_str,
            "current_grade": current,
            "on_track": on_track or None,
            "reviewer": reviewer or None,
            "comments": comments or None,
        })
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Updated #{r.review_id}")
    _pause()


def delete_review_flow() -> None:
    print("\n═══ Delete Review ═══")
    try:
        t = _pick_target()
        r = _pick_review(t.target_id)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if _input(f"Delete review #{r.review_id}? Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_review(r.review_id):
        print(f"\n  ✓ Deleted #{r.review_id}")
    _pause()


# ── Bulk seeding ──────────────────────────────────────────────────

def seed_flow() -> None:
    print("\n═══ Seed Targets from Baselines ═══")
    try:
        sid = _pick_student()
        plus = int(_input(
            "Aspirational = baseline +N grades", default="1"))
        set_by = _input("Set by")
        year = _pick_from("Year group", [""] + list(YEAR_GROUPS),
                            default="") or None
        next_due = _input("Next review due (optional)")
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    try:
        created = data.seed_from_baseline(
            sid, plus_grades=plus, set_by=set_by or None,
            year_group=year,
            next_review_due=next_due or None,
        )
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    if not created:
        print("\n  (no new targets — student may have no primary "
              "A-Level baselines, or targets already exist)")
    else:
        print(f"\n  ✓ Seeded {len(created)} target(s):")
        for t in created:
            print(f"    #{t.target_id}  {t.subject_name}  "
                  f"MTE={t.mte_grade}  asp={t.aspirational_grade}")
    _pause()


def summary_flow() -> None:
    print("\n═══ Target-Setting Summary ═══")
    try:
        win = int(_input("Upcoming review window (days)",
                            default="14"))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    summ = data.summary(upcoming_window_days=win)
    print(f"\n  Total targets       : {summ.total_targets}")
    print(f"  Distinct students   : {summ.distinct_students}")
    print(f"  On-track / Above / Met : {summ.on_track}")
    print(f"  At risk             : {summ.at_risk}")
    print(f"  Below target        : {summ.below_target}")
    print(f"  Reviews overdue     : {summ.overdue_review}")
    print(f"  Reviews due ({win}d)   : {summ.upcoming_review}")
    print("\n  By status:")
    for s in STATUSES:
        n = summ.by_status.get(s, 0)
        if n:
            print(f"    {s:<14} : {n}")
    if summ.by_subject:
        print("\n  Top subjects:")
        for sub, n in list(summ.by_subject.items())[:10]:
            print(f"    {sub:<22} : {n}")
    print("\n  By year:")
    for y in YEAR_GROUPS:
        n = summ.by_year.get(y, 0)
        if n:
            print(f"    {y:<10} : {n}")
    _pause()


# ── Submenu ───────────────────────────────────────────────────────

_MENU: list[tuple[str, Callable[[], None]]] = [
    ("List all",             list_all),
    ("At risk / Below",      list_at_risk),
    ("On track / Above / Met", list_on_track),
    ("Review overdue",       list_overdue_reviews),
    ("Filter",               filter_flow),
    ("Per-student",          per_student_flow),
    ("View target",          view_flow),
    ("New target",           new_target),
    ("Edit target",          edit_target),
    ("Set current grade",    set_current_flow),
    ("Change status",        set_status_flow),
    ("Delete target",        delete_target_flow),
    ("─" * 6,                lambda: None),
    ("Add review",           add_review_flow),
    ("List reviews",         list_reviews_flow),
    ("Edit review",          edit_review_flow),
    ("Delete review",        delete_review_flow),
    ("─" * 6,                lambda: None),
    ("Seed from baselines",  seed_flow),
    ("Summary",              summary_flow),
]


def run() -> None:
    while True:
        print("\n── Target Setting ──")
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
            logger.exception("Target-setting CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Target Setting":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Target-setting CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
