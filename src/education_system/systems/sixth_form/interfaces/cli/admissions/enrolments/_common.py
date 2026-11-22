"""Shared prompt, picker, form and table helpers for the enrolment CLI."""

from __future__ import annotations

import json
import logging
import sys
from datetime import date
from typing import Any, Callable
from education_system import paths
from education_system.systems.sixth_form.domain.admissions.enrolments import enrolments
from education_system.systems.sixth_form.domain.admissions.enrolments import enrolments as data
from education_system.systems.sixth_form.domain.learners.students import students as student_data
from education_system.systems.sixth_form.domain.admissions.enrolments.enrolments import (
    DEFAULT_STATUS,
    Enrolment,
    STATUSES,
    YEAR_GROUPS,
)

logger = logging.getLogger(__name__)



class _UserAbort(Exception):
    """Raised when the user hits Ctrl-C / EOF or types ``cancel``."""


# ── Prompt helpers ──────────────────────────────────────────────────

def _input(prompt: str, *, default: str = "", allow_empty: bool = True) -> str:
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


def _pick_from(label: str, options: list[str], default: str | None = None) -> str:
    print(f"\n  {label}:")
    for i, opt in enumerate(options, 1):
        marker = " *" if opt == default else "  "
        print(f"    {marker}{i:>2}) {opt}")
    while True:
        raw = _input(f"  Pick #1..{len(options)}", default=default or "")
        if default and raw == default:
            return default
        if not raw.isdigit():
            print("    Enter a number (or 'cancel' to abort).")
            continue
        n = int(raw)
        if not (1 <= n <= len(options)):
            print(f"    Out of range (1..{len(options)}).")
            continue
        return options[n - 1]


def _default_academic_year() -> str:
    """The register's current academic year (1 August rule as fallback)."""
    try:
        return data.current_academic_year()
    except Exception:  # noqa: BLE001 — the date rule always works
        logger.exception("current_academic_year failed")
        return data.academic_year_for_date()


# ── Write gate ──────────────────────────────────────────────────────

_REFUSED = ("✗ Your account can view enrolments but not change them "
            "(needs the admissions or students.manage permission).")


def _writes_ok() -> bool:
    """True when the signed-in user may change enrolments; otherwise
    print the refusal and pause."""
    try:
        if data.can_write():
            return True
    except Exception as exc:  # noqa: BLE001 — shown, treated as refused
        logger.exception("can_write failed")
        print(f"\n  ✗ Could not check your permissions: {exc}")
        _pause()
        return False
    print(f"\n  {_REFUSED}")
    _pause()
    return False


def requires_write(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Wrap a menu handler that changes enrolments: refused up front (with
    the reason) for a read-only user, and marked in the menus."""
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        if not _writes_ok():
            return None
        return fn(*args, **kwargs)
    wrapper.__name__ = getattr(fn, "__name__", "handler")
    wrapper.__doc__ = fn.__doc__
    wrapper._writes = True  # type: ignore[attr-defined]
    return wrapper


def _menu_label(label: str, handler: Callable[..., Any]) -> str:
    """Menu text, flagged when the handler writes and the user can't."""
    if getattr(handler, "_writes", False):
        try:
            if not data.can_write():
                return f"{label}  (view only — refused)"
        except Exception:  # noqa: BLE001
            logger.debug("can_write failed", exc_info=True)
    return label


# ── Student pickers (on roll, leavers on request) ───────────────────

def _roll(include_leavers: bool) -> list[Any]:
    students = student_data.list_students()
    return students if include_leavers else [s for s in students if s.on_roll]


def _pick_student(*, include_leavers: bool = False) -> str:
    """Show the students on roll and return the chosen student_id. ``L``
    adds the learners who have left; a typed ID always works."""
    try:
        everyone = student_data.list_students()
    except Exception as e:
        logger.exception("Could not load student list")
        print(f"    Error loading students: {e}")
        raise _UserAbort
    while True:
        students = everyone if include_leavers else [s for s in everyone if s.on_roll]
        if not students and not include_leavers and everyone:
            print("    Nobody is on roll — showing leavers too.")
            include_leavers = True
            continue
        if not students:
            print("    No students on roll — add a student first.")
            raise _UserAbort
        print("\n  Students " + ("(including leavers):" if include_leavers
                                 else "on roll:"))
        for i, s in enumerate(students, 1):
            left = "  (left)" if not s.on_roll else ""
            print(f"    {i:>3}) {s.student_id}  {s.full_name}{left}")
        hint = "" if include_leavers else ", L to include leavers"
        raw = _input(f"  Pick #1..{len(students)} (or type a student ID{hint})",
                     allow_empty=False)
        if raw.lower() == "l" and not include_leavers:
            include_leavers = True
            continue
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(students):
                return students[n - 1].student_id
            print(f"    Out of range (1..{len(students)}).")
            continue
        # Allow typing the id directly (a leaver's id too)
        match = next((s for s in everyone if s.student_id.lower() == raw.lower()), None)
        if match:
            if not match.on_roll:
                print(f"    Note: {match.full_name} has left.")
            return match.student_id
        print(f"    No student with id {raw}.")


# ── Shared helpers (year math, payloads, persistence, formatting) ───

def _next_academic_year(academic_year: str) -> str:
    """'2025/26' -> '2026/27'; falls back to next-after-current on bad input."""
    try:
        start = int((academic_year or "").split("/")[0]) + 1
    except (ValueError, IndexError):
        start = int(_default_academic_year().split("/")[0]) + 1
    return f"{start}/{str(start + 1)[-2:]}"


def _enrolment_to_payload(e: Enrolment, **overrides: Any) -> dict[str, Any]:
    """Build an ``update_enrolment`` payload from an existing record."""
    payload: dict[str, Any] = {
        "academic_year": e.academic_year,
        "year_group": e.year_group,
        "tutor_group": e.tutor_group,
        "start_date": e.start_date,
        "status": e.status,
        "notes": e.notes,
    }
    payload.update(overrides)
    return payload


def _autofill_tutor_group(old_year: int, new_year: int, tg: str | None) -> str | None:
    """Feature #38 — bump the tutor-group prefix to follow a year change."""
    return enrolments._bump_tutor_group(old_year, new_year, tg)


# Saved filter presets + academic-year list share the GUI's JSON files so
# the two front-ends stay in sync.
_PRESETS_PATH = paths.SIXTH_FORM_DATA_DIR / "enrolment_filter_presets.json"


_YEARS_PATH = paths.SIXTH_FORM_DATA_DIR / "enrolment_academic_years.json"


def _load_json(path, default):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        return default
    except Exception:
        logger.exception("Could not read %s", path)
        return default


def _save_json(path, value) -> None:
    try:
        paths.ensure_sixth_form_directories()
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(value, fh, indent=2)
    except Exception:
        logger.exception("Could not write %s", path)


def _load_presets() -> dict[str, dict[str, str]]:
    data_ = _load_json(_PRESETS_PATH, {})
    return data_ if isinstance(data_, dict) else {}


def _load_academic_years() -> list[str]:
    data_ = _load_json(_YEARS_PATH, [])
    return [str(y) for y in data_] if isinstance(data_, list) else []


def _write_simple_pdf(path: str, title: str, lines: list[str]) -> None:
    """Render a plain one-column text PDF via reportlab."""
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas as _canvas
    c = _canvas.Canvas(path, pagesize=A4)
    width, height = A4
    y = height - 60
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, y, title)
    y -= 30
    c.setFont("Helvetica", 10)
    for line in lines:
        if y < 50:
            c.showPage()
            c.setFont("Helvetica", 10)
            y = height - 50
        c.drawString(50, y, line[:110])
        y -= 16
    c.save()


# ── Terminal colour helpers (feature #13) ───────────────────────────

_STATUS_ANSI = {
    "Enrolled":  "32",   # green
    "Pending":   "33",   # yellow
    "Withdrawn": "90",   # grey
    "Completed": "36",   # cyan
}


def _colour(text: str, status: str) -> str:
    """Wrap ``text`` in an ANSI colour for its status, only on a TTY."""
    code = _STATUS_ANSI.get(status)
    if not code or not sys.stdout.isatty():
        return text
    return f"\033[{code}m{text}\033[0m"


# ── Aggregation helpers ─────────────────────────────────────────────

def _status_counts(rows: list[Enrolment]) -> dict[str, int]:
    counts = {s: 0 for s in STATUSES}
    for e in rows:
        counts[e.status] = counts.get(e.status, 0) + 1
    return counts


def _render_status_bar_chart(counts: dict[str, int]) -> None:
    """Feature #25 — an ASCII horizontal bar chart of the status split."""
    peak = max(counts.values()) if counts and max(counts.values()) else 1
    for status in STATUSES:
        n = counts.get(status, 0)
        bar = "█" * int(30 * n / peak)
        print(f"    {status:<10} {_colour(bar, status)} {n}")


def _compute_capacity_utilisation(rows: list[Enrolment], capacity: int) -> dict[str, Any]:
    """Feature #28 — active headcount vs a configured cohort capacity."""
    active = sum(1 for e in rows if e.status in ("Enrolled", "Pending"))
    pct = (100 * active / capacity) if capacity else 0.0
    return {
        "active": active,
        "capacity": capacity,
        "free": max(0, capacity - active),
        "utilisation_pct": round(pct, 1),
        "over_capacity": active > capacity,
    }


def _student_names() -> dict[str, str]:
    try:
        return {s.student_id: s.full_name for s in student_data.list_students()}
    except Exception:
        logger.exception("Could not build student name map")
        return {}


# ── Bulk / resolution helpers ───────────────────────────────────────

def _report_bulk(title: str, ok: list[str], fail: list[str]) -> None:
    print(f"\n  {title}: {len(ok)} succeeded, {len(fail)} failed.")
    for f in fail[:20]:
        print(f"    ✗ {f}")
    if len(fail) > 20:
        print(f"    …and {len(fail) - 20} more.")
    _pause()


def _resolve_enrolment(enrolment_id: int | None) -> Enrolment | None:
    """Prompt for an ID when not given, load it, and print/pause on error.
    Returns the Enrolment or None (caller should just return on None)."""
    try:
        eid = enrolment_id if enrolment_id is not None else int(
            _input("Enrolment ID", allow_empty=False))
    except ValueError:
        print("  ✗ Enrolment ID must be a whole number.")
        _pause()
        return None
    try:
        e = data.get_enrolment(eid)
    except Exception as exc:
        logger.exception("CLI get_enrolment(%s) failed", enrolment_id)
        print(f"  ✗ Error: {exc}")
        _pause()
        return None
    if e is None:
        print(f"  ✗ No enrolment #{eid}")
        _pause()
        return None
    return e


def _prompt_ids(prompt: str) -> list[int]:
    """Parse a comma/space separated list of enrolment IDs."""
    raw = _input(prompt, allow_empty=False)
    ids: list[int] = []
    for tok in raw.replace(",", " ").split():
        try:
            ids.append(int(tok))
        except ValueError:
            print(f"    Skipping non-numeric '{tok}'.")
    return ids


def _pick_students_multi(*, include_leavers: bool = False) -> list[str]:
    """Feature #1 helper — choose several students from the roll (``L``
    adds the learners who have left)."""
    try:
        everyone = student_data.list_students()
    except Exception as e:
        print(f"    Error loading students: {e}")
        raise _UserAbort
    while True:
        students = everyone if include_leavers else [s for s in everyone if s.on_roll]
        if not students:
            print("    No students on roll — add a student first.")
            raise _UserAbort
        print("\n  Students " + ("(including leavers):" if include_leavers
                                 else "on roll:"))
        for i, s in enumerate(students, 1):
            left = "  (left)" if not s.on_roll else ""
            print(f"    {i:>3}) {s.student_id}  {s.full_name}{left}")
        hint = "" if include_leavers else "; L to include leavers"
        raw = _input(f"  Pick numbers/IDs, comma-separated (or 'all'{hint})",
                     allow_empty=False)
        if raw.lower() == "l" and not include_leavers:
            include_leavers = True
            continue
        break
    if raw.lower() == "all":
        return [s.student_id for s in students]
    chosen: list[str] = []
    for tok in raw.replace(",", " ").split():
        if tok.isdigit() and 1 <= int(tok) <= len(students):
            chosen.append(students[int(tok) - 1].student_id)
        else:
            match = next((s for s in everyone
                          if s.student_id.lower() == tok.lower()), None)
            if match:
                chosen.append(match.student_id)
            else:
                print(f"    Ignoring unknown '{tok}'.")
    # de-dupe, keep order
    seen: set[str] = set()
    return [c for c in chosen if not (c in seen or seen.add(c))]


# ── Form (add + edit) ───────────────────────────────────────────────

def _known_years() -> list[str]:
    try:
        return data.known_academic_years()
    except Exception:  # noqa: BLE001 — typing a year still works
        logger.exception("known_academic_years failed")
        return []


def _prompt_academic_year(default: str, *, label: str = "Academic year") -> str:
    """Feature #36 — pick an academic year from the register (and the
    years already in use), or type one; re-asks until valid."""
    years = _known_years()
    if years:
        current = _default_academic_year()
        print(f"\n  {label}s known: " + "  ".join(
            f"{i}) {y}{'*' if y == current else ''}"
            for i, y in enumerate(years, 1)) + "   (* current)")
    while True:
        val = _input(f"{label} (# or YYYY/YY)", default=default, allow_empty=False)
        if val.isdigit() and years and 1 <= int(val) <= len(years):
            return years[int(val) - 1]
        if enrolments._ACADEMIC_YEAR_RE.match(val):
            if years and val not in years:
                print(f"    Note: {val} is not in the academic-year register.")
            return val
        print("    ✗ Must look like '2025/26' (or a number from the list).")


def _tutor_groups_for(year_group: int | None) -> list[Any]:
    try:
        from education_system.systems.sixth_form.domain.pastoral.tutor_groups import (
            tutor_groups,
        )
        return tutor_groups.list_groups(year_group=year_group)
    except Exception:  # noqa: BLE001 — free text is still accepted
        logger.exception("Could not list tutor groups")
        return []


def _prompt_tutor_group(year_group: int | None, default: str = "") -> str:
    """Pick one of the real tutor groups for the year group (number or
    name), ``-`` for none. Free text only while no groups are set up."""
    groups = _tutor_groups_for(year_group)
    if not groups:
        return _input("Tutor group (optional)", default=default)
    print(f"\n  Tutor groups{f' for Year {year_group}' if year_group else ''}:")
    for i, g in enumerate(groups, 1):
        extra = ", ".join(x for x in (
            f"Year {g.year_group}" if year_group is None else "",
            f"tutor {g.tutor}" if g.tutor else "",
            f"room {g.room}" if g.room else "") if x)
        print(f"    {i:>3}) {g.name}" + (f"  ({extra})" if extra else ""))
    names = {g.name.lower(): g.name for g in groups}
    while True:
        raw = _input("Tutor group (# or name, '-' for none)", default=default)
        if raw in ("", "-"):
            return ""
        if raw.isdigit() and 1 <= int(raw) <= len(groups):
            return groups[int(raw) - 1].name
        if raw.lower() in names:
            return names[raw.lower()]
        print("    ✗ Not one of the tutor groups listed.")


def _prompt_start_date(default: str) -> str:
    """Feature #37 — prompt for a start date, re-asking until valid/blank."""
    while True:
        val = _input("Start date (YYYY-MM-DD, optional)", default=default)
        if not val or enrolments._DATE_RE.match(val):
            return val
        print("    ✗ Must be YYYY-MM-DD.")


def _collect_form(
    existing: Enrolment | None,
    *,
    preselect_student: str | None = None,
    preset_year: str | None = None,
    preset_year_group: int | None = None,
) -> dict[str, Any]:
    is_edit = existing is not None
    payload: dict[str, Any] = {}

    if is_edit:
        print(f"\n  Editing enrolment #{existing.enrolment_id} "
              f"for {existing.student_id}")
        payload["student_id"] = existing.student_id  # immutable
    elif preselect_student is not None:
        payload["student_id"] = preselect_student
    else:
        print("\n  ── Student ──")
        payload["student_id"] = _pick_student()

    print("\n  ── Enrolment details ──")
    payload["academic_year"] = _prompt_academic_year(
        existing.academic_year if is_edit
        else (preset_year or _default_academic_year()))
    payload["year_group"] = _pick_from(
        "Year group",
        [str(y) for y in YEAR_GROUPS],
        default=(str(existing.year_group) if is_edit
                 else str(preset_year_group or YEAR_GROUPS[0])),
    )
    # Feature #38 — when the year group changed on an edit, suggest a
    # bumped tutor group (e.g. 12A → 13A) as the default.
    tutor_default = (existing.tutor_group or "") if is_edit else ""
    if is_edit and str(existing.year_group) != payload["year_group"]:
        bumped = _autofill_tutor_group(
            existing.year_group, int(payload["year_group"]), existing.tutor_group)
        if bumped:
            tutor_default = bumped
    payload["tutor_group"] = _prompt_tutor_group(int(payload["year_group"]),
                                                 tutor_default)
    payload["start_date"] = _prompt_start_date(
        (existing.start_date or "") if is_edit else date.today().isoformat())
    if is_edit:
        _form_status_edit(existing, payload)
    else:
        payload["status"] = _pick_from(
            "Status", list(enrolments.CREATE_STATUSES), default=DEFAULT_STATUS)
    payload["notes"] = _input(
        "Notes (optional)",
        default=(existing.notes or "") if is_edit else "",
    )
    return payload


_WITHDRAW_CHOICE = "Withdrawn — withdraw with an ILR reason (ends aims)"
_COMPLETE_CHOICE = "Completed — complete the course (completes aims)"


def _form_status_edit(existing: Enrolment, payload: dict[str, Any]) -> None:
    """The edit form's status: only the moves an edit may make
    (``allowed_statuses``); withdrawing / completing are offered as the
    proper actions (``payload["_then"]``) and run after the save.
    A withdrawn row's date, reason and detail can be corrected."""
    options = list(enrolments.allowed_statuses(existing))
    if existing.is_live:
        options.append(_WITHDRAW_CHOICE)
        if existing.status == "Enrolled":
            options.append(_COMPLETE_CHOICE)
    if existing.status == "Withdrawn":
        print("\n  Withdrawn — to undo, use Reinstate (reopens the aims it ended).")
    elif existing.status == "Completed":
        print("\n  Completed — to undo, use Reopen a completed enrolment.")
    choice = _pick_from("Status", options, default=existing.status)
    payload["status"] = existing.status if choice in (
        _WITHDRAW_CHOICE, _COMPLETE_CHOICE) else choice
    if choice == _WITHDRAW_CHOICE:
        payload["_then"] = "withdraw"
    elif choice == _COMPLETE_CHOICE:
        payload["_then"] = "complete"
    if existing.status == "Withdrawn":
        if _input("Correct the withdrawal date / reason / detail? (y/n)",
                  default="n").lower().startswith("y"):
            code, wd, detail = _prompt_withdrawal(
                default_code=existing.withdrawal_reason,
                default_date=existing.withdrawal_date,
                default_detail=(existing.withdrawal_detail
                                if existing.withdrawal_detail != data.RESTRICTED
                                else None),
                ask_approval=False)[:3]
            payload.update(withdrawal_reason=code, withdrawal_date=wd)
            if existing.withdrawal_detail == data.RESTRICTED and not detail:
                payload["withdrawal_detail"] = data.RESTRICTED  # keep as is
            else:
                payload["withdrawal_detail"] = detail


# ── Withdrawal / reinstatement prompts and results ──────────────────

def _prompt_withdrawal(*, default_code: str | None = None,
                       default_date: str | None = None,
                       default_detail: str | None = None,
                       ask_approval: bool = True,
                       ) -> tuple[str, str, str | None, str | None]:
    """ILR reason code, last day in learning, detail and approver."""
    labels = [f"{code} — {label}" for code, label in data.WITHDRAWAL_REASONS]
    default_label = next((lb for lb in labels
                          if lb.split(" — ")[0] == default_code), None)
    code = _pick_from("ILR withdrawal reason", labels,
                      default=default_label).split(" — ")[0]
    while True:
        wd = _input("Last day in learning (YYYY-MM-DD)",
                    default=default_date or date.today().isoformat())
        if enrolments._DATE_RE.match(wd):
            break
        print("    ✗ Must be YYYY-MM-DD.")
    detail = _input("Detail (optional)", default=default_detail or "") or None
    approved = (_input("Approved by (optional)") or None) if ask_approval else None
    return code, wd, detail, approved


def _print_withdrawal(res: Any) -> None:
    """Show a ``WithdrawalResult``."""
    e = res.enrolment
    print(f"  ✓ Withdrew enrolment #{e.enrolment_id} ({e.student_id}, "
          f"{e.academic_year}): {e.withdrawal_reason_label}, last day "
          f"{e.withdrawal_date}")
    print(f"    Learning aims ended: {len(res.aims_ended)}"
          + (f" — {', '.join(res.aims_ended)}" if res.aims_ended else ""))
    for p in res.aim_problems:
        print(f"    ✗ aim not ended: {p}")
    if res.student_left:
        print("    That was their last live enrolment: the student record is "
              "now marked Left.")
    for n in res.student_notes:
        print(f"    • {n}")


def _print_reinstate(res: Any) -> None:
    """Show a ``ReinstateResult``."""
    e = res.enrolment
    print(f"  ✓ Reinstated enrolment #{e.enrolment_id} ({e.student_id}, "
          f"{e.academic_year}) — now {e.status}")
    print(f"    Learning aims reopened: {len(res.aims_reopened)}"
          + (f" — {', '.join(res.aims_reopened)}" if res.aims_reopened else ""))
    for p in res.aim_problems:
        print(f"    ✗ aim not reopened: {p}")
    if res.student_reinstated:
        print("    The student record is back on roll.")
    for n in res.student_notes:
        print(f"    • {n}")


def _undo_withdrawal(eid: int, reason: str) -> None:
    """Undo-stack action for a withdrawal: reinstate (reopens the aims)."""
    _print_reinstate(data.reinstate_enrolment(eid, reason=reason))


# ── CRUD entry points ───────────────────────────────────────────────

def _print_table(rows: list[Enrolment], *, names: dict[str, str] | None = None) -> None:
    if not rows:
        print("\n  (no enrolments)")
        return
    if names is None:
        names = _student_names()
    print()
    print(f"  {'#':>4}  {'Student':<10}  {'Name':<24}  {'Year':<8}  "
          f"{'YG':<3}  {'Tutor':<6}  {'Status':<10}")
    print("  " + "-" * 78)
    for e in rows:
        # Feature #13 — colour the row by status (ANSI, TTY only).
        print(_colour(
            f"  {e.enrolment_id:>4}  {e.student_id:<10}  "
            f"{names.get(e.student_id, '—')[:24]:<24}  "
            f"{e.academic_year:<8}  {e.year_group:<3}  "
            f"{(e.tutor_group or '—'):<6}  {e.status:<10}",
            e.status,
        ))
    print(f"\n  {len(rows)} enrolment(s).")


def _print_table_paged(rows: list[Enrolment], page_size: int = 20) -> None:
    """Feature #45 — page through a long result set, Enter for the next page."""
    if len(rows) <= page_size:
        _print_table(rows)
        return
    names = _student_names()
    total = len(rows)
    pages = (total + page_size - 1) // page_size
    for p in range(pages):
        chunk = rows[p * page_size:(p + 1) * page_size]
        _print_table(chunk, names=names)
        print(f"  Page {p + 1}/{pages} — showing {len(chunk)} of {total}.")
        if p < pages - 1:
            try:
                if input("  Enter for next page, 'q' to stop: ").strip().lower() == "q":
                    break
            except (EOFError, KeyboardInterrupt):
                print()
                break


# ── Row-action helper for list & filter results ─────────────────────

# Feature #43 — single-key shortcuts shared by the row-action loop and the
# per-record context menu (#44). Maps a key to (label, handler-taking-eid).
_ROW_SHORTCUTS: dict[str, tuple[str, Callable[[int], None]]] = {}


def _row_action_loop(rows: list[Enrolment]) -> None:
    if not rows:
        _pause()
        return
    if not _ROW_SHORTCUTS:
        # The shortcut targets live in the menu module (lazy: it imports us).
        from education_system.systems.sixth_form.interfaces.cli.admissions.enrolments.enrolment_cli import (
            _init_row_shortcuts,
        )
        _init_row_shortcuts()
    print()
    items = [f"{k.upper()}) {label}" for k, (label, _fn) in _ROW_SHORTCUTS.items()]
    print("  Actions:  " + "  ".join(items[:5]))
    for n in range(5, len(items), 4):
        print("            " + "  ".join(items[n:n + 4]))
    print("            (Enter to go back)")
    while True:
        try:
            choice = input("  Action: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not choice:
            return
        if choice not in _ROW_SHORTCUTS:
            print(f"    Pick one of: {', '.join(k.upper() for k in _ROW_SHORTCUTS)}.")
            continue
        try:
            eid = int(_input("Enrolment ID", allow_empty=False))
        except ValueError:
            print("    Enrolment ID must be a whole number.")
            continue
        except _UserAbort:
            print("  Cancelled.")
            return
        _ROW_SHORTCUTS[choice][1](eid)
        return


# ════════════════════════════════════════════════════════════════════
# Undo stack (feature #42) + safety helpers (#39)
# ════════════════════════════════════════════════════════════════════

_UNDO_STACK: list[tuple[str, Callable[[], None]]] = []


def _record_undo(label: str, restore: Callable[[], None]) -> None:
    _UNDO_STACK.append((label, restore))
    if len(_UNDO_STACK) > 20:
        _UNDO_STACK.pop(0)


def _warn_on_unsaved_changes(dirty: bool) -> bool:
    """Feature #39 — returns True if it's safe to leave (no changes or user
    confirms discarding)."""
    if not dirty:
        return True
    return _input("Discard unsaved changes? Type 'yes' to confirm",
                  default="no").lower() == "yes"


# ── Wave-2 shared helpers: CSV output, enrolment checks ─────────────

def _offer_csv(rows: list[Any], default_name: str) -> None:
    """Optionally write report rows to a CSV file (blank path = skip)."""
    if not rows:
        return
    from education_system.systems.sixth_form.domain.admissions.enrolments import (
        enrolment_reports,
    )
    try:
        path = _input(f"Save as CSV? Path (blank = no; e.g. {default_name})")
    except _UserAbort:
        return
    if not path:
        return
    try:
        text = enrolment_reports.to_csv(rows)
        with open(path, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
    except Exception as exc:  # noqa: BLE001 — file errors shown
        logger.exception("CSV write to %s failed", path)
        print(f"  ✗ Could not write {path}: {exc}")
        return
    print(f"  ✓ {len(rows)} row(s) written to {path}")


def _show_checks(student_id: str, academic_year: str | None = None) -> None:
    """Print ``check_enrolment`` warnings (after a create / edit / open)."""
    try:
        from education_system.systems.sixth_form.domain.admissions.enrolments import (
            enrolment_checks,
        )
        warnings = enrolment_checks.check_enrolment(student_id, academic_year)
    except Exception as exc:  # noqa: BLE001 — checks never block, but show
        logger.exception("check_enrolment(%s) failed", student_id)
        print(f"    (enrolment checks not run: {exc})")
        return
    if not warnings:
        print("    ✓ Enrolment checks: nothing to flag")
        return
    print(f"    ⚠ {len(warnings)} enrolment check warning(s):")
    for w in warnings:
        print(f"      • [{w.kind}] {w.message}")


def _print_leaver_effects(student_id: str, *, indent: str = "    ") -> None:
    """What leaving did to the learner's other records (and what was put
    back when they returned)."""
    try:
        from education_system.systems.sixth_form.domain.admissions.enrolments import (
            leaver_effects,
        )
        rows = leaver_effects.effects_for(student_id)
    except Exception as exc:  # noqa: BLE001 — shown
        logger.exception("effects_for(%s) failed", student_id)
        print(f"{indent}Leaver effects: ✗ {exc}")
        return
    if not rows:
        return
    print(f"{indent}Leaver effects (newest first):")
    for r in rows[:20]:
        back = f"  — returned {r['returned_at'][:10]}" if r.get("returned_at") else ""
        print(f"{indent}  {r['left_on']}  {r['area']:<12} {r.get('label') or r.get('ref') or ''}"
              f": {r['action']}{back}")
    if len(rows) > 20:
        print(f"{indent}  … {len(rows) - 20} more")


def _pick_enrolment_for(prompt: str = "Enrolment ID") -> Enrolment | None:
    """An enrolment by ID, or by picking a learner (their current one)."""
    raw = _input(f"{prompt} (or blank to pick a learner)")
    if raw:
        try:
            return _resolve_enrolment(int(raw.lstrip("#")))
        except ValueError:
            print("  ✗ Enrolment ID must be a whole number.")
            _pause()
            return None
    sid = _pick_student(include_leavers=True)
    rows = data.list_for_student(sid)
    if not rows:
        print(f"  ✗ {sid} has no enrolments.")
        _pause()
        return None
    if len(rows) == 1:
        return rows[0]
    labels = [f"#{e.enrolment_id} {e.academic_year} Year {e.year_group} [{e.status}]"
              for e in rows]
    pick = _pick_from("Which enrolment", labels, default=labels[0])
    return data.get_enrolment(int(pick.split()[0].lstrip("#")))
