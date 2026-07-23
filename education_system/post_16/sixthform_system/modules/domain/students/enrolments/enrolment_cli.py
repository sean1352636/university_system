"""CLI flows for Sixth Form Enrolment CRUD.

Mirrors `enrolment_views`: list/filter, create, view, edit, delete.
Wired in from `cli_main.py` via `dispatch("Enrolment")`, which opens a
small submenu since enrolment is itself a CRUD area.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import date
from typing import Any, Callable
from education_system.post_16.sixthform_system.core import paths
from education_system.post_16.sixthform_system.modules.domain.students.enrolments import enrolments
from education_system.post_16.sixthform_system.modules.domain.students.enrolments import enrolments as data
from education_system.post_16.sixthform_system.modules.domain.students.students import students as student_data
from education_system.post_16.sixthform_system.modules.domain.students.enrolments.enrolments import (
    DEFAULT_STATUS,
    Enrolment,
    STATUSES,
    ValidationError,
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
    today = date.today()
    start = today.year if today.month >= 8 else today.year - 1
    return f"{start}/{str(start + 1)[-2:]}"


def _pick_student() -> str:
    """Show the student roll and return the chosen student_id."""
    try:
        students = student_data.list_students()
    except Exception as e:
        logger.exception("Could not load student list")
        print(f"    Error loading students: {e}")
        raise _UserAbort
    if not students:
        print("    No students on roll — add a student first.")
        raise _UserAbort
    print("\n  Students on roll:")
    for i, s in enumerate(students, 1):
        print(f"    {i:>3}) {s.student_id}  {s.full_name}")
    while True:
        raw = _input(f"  Pick #1..{len(students)} (or type a student ID)",
                     allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(students):
                return students[n - 1].student_id
            print(f"    Out of range (1..{len(students)}).")
            continue
        # Allow typing the id directly
        match = next((s for s in students if s.student_id.lower() == raw.lower()), None)
        if match:
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
_PRESETS_PATH = paths.DATA_DIR / "enrolment_filter_presets.json"
_YEARS_PATH = paths.DATA_DIR / "enrolment_academic_years.json"


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
        paths.ensure_directories()
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


def _pick_students_multi() -> list[str]:
    """Feature #1 helper — choose several students from the roll."""
    try:
        students = student_data.list_students()
    except Exception as e:
        print(f"    Error loading students: {e}")
        raise _UserAbort
    if not students:
        print("    No students on roll — add a student first.")
        raise _UserAbort
    print("\n  Students on roll:")
    for i, s in enumerate(students, 1):
        print(f"    {i:>3}) {s.student_id}  {s.full_name}")
    raw = _input("  Pick numbers/IDs, comma-separated (or 'all')",
                 allow_empty=False)
    if raw.lower() == "all":
        return [s.student_id for s in students]
    chosen: list[str] = []
    for tok in raw.replace(",", " ").split():
        if tok.isdigit() and 1 <= int(tok) <= len(students):
            chosen.append(students[int(tok) - 1].student_id)
        else:
            match = next((s for s in students
                          if s.student_id.lower() == tok.lower()), None)
            if match:
                chosen.append(match.student_id)
            else:
                print(f"    Ignoring unknown '{tok}'.")
    # de-dupe, keep order
    seen: set[str] = set()
    return [c for c in chosen if not (c in seen or seen.add(c))]


# ── Form (add + edit) ───────────────────────────────────────────────

def _prompt_academic_year(default: str) -> str:
    """Feature #36 — prompt for an academic year, re-asking until valid."""
    while True:
        val = _input("Academic year (YYYY/YY)", default=default, allow_empty=False)
        if enrolments._ACADEMIC_YEAR_RE.match(val):
            return val
        print("    ✗ Must look like '2025/26'.")


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
    payload["tutor_group"] = _input("Tutor group (optional)", default=tutor_default)
    payload["start_date"] = _prompt_start_date(
        (existing.start_date or "") if is_edit else date.today().isoformat())
    payload["status"] = _pick_from(
        "Status",
        list(STATUSES),
        default=(existing.status if is_edit else DEFAULT_STATUS),
    )
    payload["notes"] = _input(
        "Notes (optional)",
        default=(existing.notes or "") if is_edit else "",
    )
    return payload


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


def list_all() -> None:
    print("\n═══ Enrolment Directory ═══")
    try:
        rows = data.list_enrolments()
    except Exception as e:
        logger.exception("CLI list_enrolments failed")
        print(f"  ✗ Error: {e}")
        _pause()
        return
    _print_table(rows)
    _row_action_loop(rows)


def filter_enrolments() -> None:
    print("\n═══ Filter Enrolments ═══")
    print("  (leave any field blank to skip; 'cancel' to abort)\n")
    try:
        year = _input("Academic year") or None
        yg_raw = _input("Year group (12 or 13)")
        status_raw = _input("Status (Enrolled / Pending / Withdrawn / Completed)")
    except _UserAbort:
        print("\n  Cancelled.")
        return

    yg: int | None = None
    if yg_raw:
        try:
            yg = int(yg_raw)
        except ValueError:
            print("  ✗ Year group must be a number.")
            _pause()
            return
    status = status_raw or None
    if status and status not in STATUSES:
        print(f"  ✗ Status must be one of: {', '.join(STATUSES)}")
        _pause()
        return

    try:
        rows = data.list_enrolments(
            academic_year=year, year_group=yg, status=status)
    except Exception as e:
        logger.exception("CLI filter_enrolments failed")
        print(f"  ✗ Error: {e}")
        _pause()
        return
    _print_table(rows)
    _row_action_loop(rows)


def new_enrolment() -> None:
    print("\n═══ New Enrolment ═══")
    print("  (type 'cancel' at any prompt to abort)")
    try:
        payload = _collect_form(None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        created = data.create_enrolment(payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    except Exception as e:
        logger.exception("CLI new_enrolment failed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
        return

    student = student_data.get_student(created.student_id)
    print()
    print(f"  ✓ Created enrolment #{created.enrolment_id}")
    print(f"      Student      : {created.student_id} "
          f"({student.full_name if student else '?'})")
    print(f"      Academic year: {created.academic_year}")
    print(f"      Year group   : {created.year_group}")
    print(f"      Tutor group  : {created.tutor_group or '—'}")
    print(f"      Status       : {created.status}")
    _pause()


def view_enrolment(enrolment_id: int | None = None) -> None:
    print("\n═══ View Enrolment ═══")
    try:
        eid = enrolment_id if enrolment_id is not None else int(
            _input("Enrolment ID", allow_empty=False))
    except ValueError:
        print("  ✗ Enrolment ID must be a whole number.")
        _pause()
        return
    except _UserAbort:
        print("\n  Cancelled.")
        return

    try:
        e = data.get_enrolment(eid)
    except Exception as exc:
        logger.exception("CLI get_enrolment(%d) failed", eid)
        print(f"  ✗ Error: {exc}")
        _pause()
        return
    if e is None:
        print(f"  ✗ No enrolment #{eid}")
        _pause()
        return

    student = student_data.get_student(e.student_id)
    print()
    print(f"    Enrolment ID  : #{e.enrolment_id}")
    print(f"    Student       : {e.student_id} "
          f"({student.full_name if student else '(deleted)'})")
    print(f"    Academic year : {e.academic_year}")
    print(f"    Year group    : Year {e.year_group}")
    print(f"    Tutor group   : {e.tutor_group or '—'}")
    print(f"    Start date    : {e.start_date or '—'}")
    print(f"    Status        : {e.status}")
    print(f"    Created       : {e.created_at}")
    if e.notes:
        print(f"    Notes         : {e.notes}")
    _pause()


def edit_enrolment(enrolment_id: int | None = None) -> None:
    print("\n═══ Edit Enrolment ═══")
    try:
        eid = enrolment_id if enrolment_id is not None else int(
            _input("Enrolment ID", allow_empty=False))
    except ValueError:
        print("  ✗ Enrolment ID must be a whole number.")
        _pause()
        return
    except _UserAbort:
        print("\n  Cancelled.")
        return

    try:
        existing = data.get_enrolment(eid)
    except Exception as exc:
        logger.exception("CLI get_enrolment(%d) failed", eid)
        print(f"  ✗ Error: {exc}")
        _pause()
        return
    if existing is None:
        print(f"  ✗ No enrolment #{eid}")
        _pause()
        return

    try:
        payload = _collect_form(existing)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        updated = data.update_enrolment(eid, payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    except Exception as e:
        logger.exception("CLI update_enrolment(%d) failed", eid)
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
        return
    print(f"\n  ✓ Updated enrolment #{updated.enrolment_id}")
    _pause()


def delete_enrolment_flow(enrolment_id: int | None = None) -> None:
    print("\n═══ Delete Enrolment ═══")
    try:
        eid = enrolment_id if enrolment_id is not None else int(
            _input("Enrolment ID", allow_empty=False))
    except ValueError:
        print("  ✗ Enrolment ID must be a whole number.")
        _pause()
        return
    except _UserAbort:
        print("\n  Cancelled.")
        return

    try:
        existing = data.get_enrolment(eid)
    except Exception as exc:
        logger.exception("CLI get_enrolment(%d) failed", eid)
        print(f"  ✗ Error: {exc}")
        _pause()
        return
    if existing is None:
        print(f"  ✗ No enrolment #{eid}")
        _pause()
        return

    confirm = _input(
        f"Delete enrolment #{existing.enrolment_id} "
        f"({existing.student_id}, {existing.academic_year})? "
        f"Type 'yes' to confirm",
        default="no",
    )
    if confirm.lower() != "yes":
        print("\n  Cancelled.")
        return
    try:
        if data.delete_enrolment(eid):
            # Feature #42 — allow undo by re-creating the deleted row.
            _record_undo(
                f"delete of #{eid} ({existing.student_id})",
                lambda e=existing: data.create_enrolment(
                    {"student_id": e.student_id, **_enrolment_to_payload(e)}))
            print(f"\n  ✓ Deleted enrolment #{eid}")
        else:
            print(f"\n  ✗ Could not delete enrolment #{eid}")
    except Exception as e:
        logger.exception("CLI delete_enrolment(%d) failed", eid)
        print(f"\n  ✗ Unexpected error: {e}")
    _pause()


# ── Row-action helper for list & filter results ─────────────────────

# Feature #43 — single-key shortcuts shared by the row-action loop and the
# per-record context menu (#44). Maps a key to (label, handler-taking-eid).
_ROW_SHORTCUTS: dict[str, tuple[str, Callable[[int], None]]] = {}


def _init_row_shortcuts() -> None:
    """Populated lazily once the target functions are defined at module load."""
    _ROW_SHORTCUTS.update({
        "v": ("View", view_enrolment),
        "e": ("Edit", edit_enrolment),
        "d": ("Delete", delete_enrolment_flow),
        "w": ("Withdraw", withdraw_enrolment),
        "x": ("Soft-delete toggle", soft_delete_toggle),
        "u": ("Duplicate", duplicate_enrolment),
        "t": ("Transfer", transfer_enrolment),
        "c": ("Copy details", copy_enrolment_details),
        "p": ("Print PDF", export_enrolment_pdf),
        "m": ("Context menu", context_menu),
    })


def _row_action_loop(rows: list[Enrolment]) -> None:
    if not rows:
        _pause()
        return
    if not _ROW_SHORTCUTS:
        _init_row_shortcuts()
    print()
    print("  Actions:  V) View  E) Edit  D) Delete  W) Withdraw  U) Duplicate")
    print("            T) Transfer  C) Copy  P) Print PDF  M) Menu  (Enter to go back)")
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


def keyboard_shortcuts_help() -> None:
    """Feature #43 — list the single-key row/record shortcuts."""
    if not _ROW_SHORTCUTS:
        _init_row_shortcuts()
    print("\n═══ Keyboard / Row Shortcuts ═══\n")
    for key, (label, _fn) in _ROW_SHORTCUTS.items():
        print(f"    {key.upper()}) {label}")
    print("\n  These work at the 'Action:' prompt after any listing,")
    print("  and inside the per-record context menu (M).")
    _pause()


def context_menu(enrolment_id: int | None = None) -> None:
    """Feature #44 — per-record action menu for one enrolment."""
    if not _ROW_SHORTCUTS:
        _init_row_shortcuts()
    e = _resolve_enrolment(enrolment_id)
    if e is None:
        return
    eid = e.enrolment_id
    # Exclude the context-menu entry itself to avoid recursion.
    items = [(label, fn) for key, (label, fn) in _ROW_SHORTCUTS.items() if key != "m"]
    while True:
        fresh = data.get_enrolment(eid)
        if fresh is None:
            print(f"  (enrolment #{eid} no longer exists)")
            return
        print(f"\n── Enrolment #{eid} · {fresh.student_id} "
              f"({fresh.academic_year}, {fresh.status}) ──")
        for i, (label, _fn) in enumerate(items, 1):
            print(f"  {i}) {label}")
        print("  0) Back")
        try:
            choice = input("  Select: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if choice == "0":
            return
        if not choice.isdigit() or not (1 <= int(choice) <= len(items)):
            print("  Invalid selection.")
            continue
        items[int(choice) - 1][1](eid)


# ════════════════════════════════════════════════════════════════════
# Undo stack (feature #42) + safety helpers (#39)
# ════════════════════════════════════════════════════════════════════

_UNDO_STACK: list[tuple[str, Callable[[], None]]] = []


def _record_undo(label: str, restore: Callable[[], None]) -> None:
    _UNDO_STACK.append((label, restore))
    if len(_UNDO_STACK) > 20:
        _UNDO_STACK.pop(0)


def undo_last_action() -> None:
    """Feature #42 — undo the most recent delete / status change this session."""
    print("\n═══ Undo ═══")
    if not _UNDO_STACK:
        print("  (nothing to undo)")
        _pause()
        return
    label, restore = _UNDO_STACK[-1]
    confirm = _input(f"Undo {label}? Type 'yes' to confirm", default="no")
    if confirm.lower() != "yes":
        print("\n  Cancelled.")
        return
    _UNDO_STACK.pop()
    try:
        restore()
    except Exception as exc:
        logger.exception("Undo failed for: %s", label)
        print(f"  ✗ Could not undo: {exc}")
        _pause()
        return
    print(f"  ✓ Undid {label}")
    _pause()


def _warn_on_unsaved_changes(dirty: bool) -> bool:
    """Feature #39 — returns True if it's safe to leave (no changes or user
    confirms discarding)."""
    if not dirty:
        return True
    return _input("Discard unsaved changes? Type 'yes' to confirm",
                  default="no").lower() == "yes"


# ════════════════════════════════════════════════════════════════════
# Record-level workflow actions (features 5, 6, 7, 41, 48)
# ════════════════════════════════════════════════════════════════════

def withdraw_enrolment(enrolment_id: int | None = None) -> None:
    """Feature #5 — set status to Withdrawn and record a reason in notes."""
    print("\n═══ Withdraw Enrolment ═══")
    e = _resolve_enrolment(enrolment_id)
    if e is None:
        return
    if e.status == "Withdrawn":
        print(f"  Enrolment #{e.enrolment_id} is already withdrawn.")
        _pause()
        return
    reason = _input("Reason for withdrawal (optional)")
    stamp = f"[Withdrawn {date.today().isoformat()}]"
    tail = f"{stamp} {reason}".strip()
    new_notes = f"{e.notes}\n{tail}".strip() if e.notes else tail
    try:
        data.update_enrolment(
            e.enrolment_id, _enrolment_to_payload(e, status="Withdrawn", notes=new_notes))
    except Exception as exc:
        logger.exception("CLI withdraw failed")
        print(f"  ✗ {exc}")
        _pause()
        return
    _record_undo(f"withdrawal of #{e.enrolment_id}",
                 lambda: data.update_enrolment(e.enrolment_id, _enrolment_to_payload(e)))
    print(f"  ✓ Withdrew enrolment #{e.enrolment_id}")
    _pause()


def soft_delete_toggle(enrolment_id: int | None = None) -> None:
    """Feature #41 — flip between Withdrawn and Enrolled instead of deleting."""
    print("\n═══ Soft-delete Toggle ═══")
    e = _resolve_enrolment(enrolment_id)
    if e is None:
        return
    new_status = "Enrolled" if e.status == "Withdrawn" else "Withdrawn"
    try:
        data.update_enrolment(e.enrolment_id, _enrolment_to_payload(e, status=new_status))
    except Exception as exc:
        print(f"  ✗ {exc}")
        _pause()
        return
    _record_undo(f"soft-delete toggle of #{e.enrolment_id}",
                 lambda: data.update_enrolment(e.enrolment_id, _enrolment_to_payload(e)))
    print(f"  ✓ #{e.enrolment_id} → {new_status}")
    _pause()


def duplicate_enrolment(enrolment_id: int | None = None) -> None:
    """Feature #7 — create a new enrolment pre-filled from an existing one,
    rolled forward one academic year (and Year 12 → 13)."""
    print("\n═══ Duplicate Enrolment ═══")
    e = _resolve_enrolment(enrolment_id)
    if e is None:
        return
    yg = 13 if e.year_group == 12 else e.year_group
    try:
        payload = _collect_form(None, preselect_student=e.student_id,
                                preset_year=_next_academic_year(e.academic_year),
                                preset_year_group=yg)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _create_and_report(payload)


def reenrol_student() -> None:
    """Feature #6 — quick re-enrol: pick a student, defaulting to their next
    academic year and year group."""
    print("\n═══ Re-enrol Student ═══")
    try:
        sid = _pick_student()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    latest = data.current_enrolment(sid)
    if latest is not None:
        year = _next_academic_year(latest.academic_year)
        yg = 13 if latest.year_group == 12 else latest.year_group
    else:
        year, yg = _default_academic_year(), YEAR_GROUPS[0]
    try:
        payload = _collect_form(None, preselect_student=sid,
                                preset_year=year, preset_year_group=yg)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _create_and_report(payload)


def enrol_from_student_profile(student_id: str | None = None) -> None:
    """Feature #46 — deep-link equivalent: enrol a chosen student directly."""
    print("\n═══ Enrol Student ═══")
    try:
        sid = student_id or _pick_student()
        payload = _collect_form(None, preselect_student=sid)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _create_and_report(payload)


def _create_and_report(payload: dict[str, Any]) -> None:
    try:
        created = data.create_enrolment(payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    except Exception as e:
        logger.exception("CLI create failed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
        return
    print(f"\n  ✓ Created enrolment #{created.enrolment_id} for "
          f"{created.student_id} ({created.academic_year}, Year {created.year_group})")
    _pause()


def transfer_enrolment(enrolment_id: int | None = None) -> None:
    """Feature #48 — move an enrolment to a different student (delete + recreate,
    since student_id is immutable)."""
    print("\n═══ Transfer Enrolment ═══")
    e = _resolve_enrolment(enrolment_id)
    if e is None:
        return
    print(f"  Transferring #{e.enrolment_id} ({e.academic_year}, Year {e.year_group}) "
          f"from {e.student_id}.")
    try:
        target = _pick_student()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if target == e.student_id:
        print("  Same student — nothing to do.")
        _pause()
        return
    note = f"{e.notes or ''}\n[Transferred from {e.student_id} " \
           f"{date.today().isoformat()}]".strip()
    try:
        data.delete_enrolment(e.enrolment_id)
        new = data.create_enrolment({"student_id": target,
                                     **_enrolment_to_payload(e, notes=note)})
    except Exception as exc:
        logger.exception("CLI transfer failed")
        print(f"  ✗ {exc}")
        _pause()
        return
    print(f"  ✓ Transferred to {target} as enrolment #{new.enrolment_id}")
    _pause()


# ════════════════════════════════════════════════════════════════════
# Bulk / cohort operations (features 1, 2, 3, 4, 8, 40)
# ════════════════════════════════════════════════════════════════════

def bulk_enrol() -> None:
    """Feature #1 — enrol several students into one shared year/status."""
    print("\n═══ Bulk Enrol ═══")
    try:
        sids = _pick_students_multi()
        if not sids:
            print("  No students selected.")
            _pause()
            return
        print(f"\n  {len(sids)} student(s) selected. Shared details:")
        year = _prompt_academic_year(_default_academic_year())
        yg = _pick_from("Year group", [str(y) for y in YEAR_GROUPS],
                        default=str(YEAR_GROUPS[0]))
        tutor = _input("Tutor group (optional)")
        start = _prompt_start_date(date.today().isoformat())
        status = _pick_from("Status", list(STATUSES), default=DEFAULT_STATUS)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    ok: list[str] = []
    fail: list[str] = []
    for sid in sids:
        try:
            data.create_enrolment({
                "student_id": sid, "academic_year": year, "year_group": yg,
                "tutor_group": tutor, "start_date": start, "status": status,
                "notes": None})
            ok.append(sid)
        except Exception as exc:
            fail.append(f"{sid}: {exc}")
    _report_bulk("Bulk enrol", ok, fail)


def progression_wizard() -> None:
    """Feature #2 — roll enrolled Year 12s forward into Year 13 next year."""
    print("\n═══ Year 12 → 13 Progression Wizard ═══")
    try:
        src = _prompt_academic_year(_default_academic_year())
    except _UserAbort:
        print("\n  Cancelled.")
        return
    tgt = _next_academic_year(src)
    try:
        y12 = data.list_enrolments(academic_year=src, year_group=12, status="Enrolled")
    except Exception as exc:
        print(f"  ✗ {exc}")
        _pause()
        return
    if not y12:
        print(f"  No enrolled Year 12 students in {src}.")
        _pause()
        return
    print(f"  {len(y12)} student(s) will roll into Year 13 for {tgt}.")
    if _input("Proceed? Type 'yes' to confirm", default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    ok: list[str] = []
    fail: list[str] = []
    for e in y12:
        new_tg = enrolments._bump_tutor_group(12, 13, e.tutor_group)
        try:
            data.create_enrolment({
                "student_id": e.student_id, "academic_year": tgt, "year_group": 13,
                "tutor_group": new_tg, "start_date": None, "status": "Enrolled",
                "notes": None})
            ok.append(e.student_id)
        except Exception as exc:
            fail.append(f"{e.student_id}: {exc}")
    _report_bulk("Progression", ok, fail)


def end_of_year_rollover() -> None:
    """Feature #8 — complete Year 13 leavers and progress Year 12 into 13."""
    print("\n═══ End-of-Year Rollover ═══")
    try:
        src = _prompt_academic_year(_default_academic_year())
    except _UserAbort:
        print("\n  Cancelled.")
        return
    tgt = _next_academic_year(src)
    try:
        y13 = data.list_enrolments(academic_year=src, year_group=13, status="Enrolled")
        y12 = data.list_enrolments(academic_year=src, year_group=12, status="Enrolled")
    except Exception as exc:
        print(f"  ✗ {exc}")
        _pause()
        return
    if not y13 and not y12:
        print(f"  No enrolled students in {src}.")
        _pause()
        return
    print(f"  {len(y13)} Year 13 leaver(s) → Completed.")
    print(f"  {len(y12)} Year 12 → Year 13 in {tgt}.")
    if _input("Proceed? Type 'yes' to confirm", default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    ok: list[str] = []
    fail: list[str] = []
    for e in y13:
        try:
            data.update_enrolment(e.enrolment_id, _enrolment_to_payload(e, status="Completed"))
            ok.append(f"{e.student_id} (completed)")
        except Exception as exc:
            fail.append(f"{e.student_id}: {exc}")
    for e in y12:
        new_tg = enrolments._bump_tutor_group(12, 13, e.tutor_group)
        try:
            data.create_enrolment({
                "student_id": e.student_id, "academic_year": tgt, "year_group": 13,
                "tutor_group": new_tg, "start_date": None, "status": "Enrolled",
                "notes": None})
            ok.append(f"{e.student_id} (progressed)")
        except Exception as exc:
            fail.append(f"{e.student_id}: {exc}")
    _report_bulk("Rollover", ok, fail)


def bulk_status_change() -> None:
    """Feature #3 — set one status on many enrolments by ID."""
    print("\n═══ Bulk Status Change ═══")
    try:
        ids = _prompt_ids("Enrolment IDs (comma/space separated)")
        if not ids:
            print("  No IDs given.")
            _pause()
            return
        new_status = _pick_from("New status", list(STATUSES), default=DEFAULT_STATUS)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    ok: list[str] = []
    fail: list[str] = []
    priors: list[Enrolment] = []
    for eid in ids:
        try:
            e = data.get_enrolment(eid)
            if e is None:
                fail.append(f"#{eid}: not found")
                continue
            priors.append(e)
            data.update_enrolment(eid, _enrolment_to_payload(e, status=new_status))
            ok.append(f"#{eid}")
        except Exception as exc:
            fail.append(f"#{eid}: {exc}")
    if priors:
        def _restore(snap: list[Enrolment] = priors) -> None:
            for e in snap:
                data.update_enrolment(e.enrolment_id, _enrolment_to_payload(e))
        _record_undo(f"status change of {len(priors)} enrolment(s)", _restore)
    _report_bulk("Bulk status change", ok, fail)


def bulk_tutor_reassign() -> None:
    """Feature #4 — move many enrolments to a new tutor group."""
    print("\n═══ Bulk Tutor Reassign ═══")
    try:
        ids = _prompt_ids("Enrolment IDs (comma/space separated)")
        if not ids:
            print("  No IDs given.")
            _pause()
            return
        tutor = _input("New tutor group (blank to clear)") or None
    except _UserAbort:
        print("\n  Cancelled.")
        return
    ok: list[str] = []
    fail: list[str] = []
    for eid in ids:
        try:
            e = data.get_enrolment(eid)
            if e is None:
                fail.append(f"#{eid}: not found")
                continue
            data.update_enrolment(eid, _enrolment_to_payload(e, tutor_group=tutor))
            ok.append(f"#{eid}")
        except Exception as exc:
            fail.append(f"#{eid}: {exc}")
    _report_bulk("Bulk tutor reassign", ok, fail)


def bulk_delete() -> None:
    """Feature #40 — guarded multi-delete requiring a typed confirmation."""
    print("\n═══ Bulk Delete ═══")
    try:
        ids = _prompt_ids("Enrolment IDs to delete (comma/space separated)")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if not ids:
        print("  No IDs given.")
        _pause()
        return
    typed = _input(f"This deletes {len(ids)} enrolment(s). Type DELETE to confirm")
    if typed.strip().upper() != "DELETE":
        print("\n  Cancelled.")
        return
    snapshots = [data.get_enrolment(eid) for eid in ids]
    ok: list[str] = []
    fail: list[str] = []
    for eid in ids:
        try:
            if data.delete_enrolment(eid):
                ok.append(f"#{eid}")
            else:
                fail.append(f"#{eid}: not found")
        except Exception as exc:
            fail.append(f"#{eid}: {exc}")
    restorable = [e for e in snapshots if e is not None]
    if restorable:
        def _restore(snap: list[Enrolment] = restorable) -> None:
            for e in snap:
                data.create_enrolment({"student_id": e.student_id,
                                       **_enrolment_to_payload(e)})
        _record_undo(f"bulk delete of {len(restorable)} enrolment(s)", _restore)
    _report_bulk("Bulk delete", ok, fail)


# ════════════════════════════════════════════════════════════════════
# Search / filter / sort (features 9, 10, 11, 12, 14, 15)
# ════════════════════════════════════════════════════════════════════

def _apply_filter_dict(preset: dict[str, str]) -> list[Enrolment]:
    """Run a saved-preset filter dict (same keys as the GUI directory)."""
    rows = data.list_enrolments(
        academic_year=(preset.get("academic_year") or "").strip() or None,
        year_group=int(preset["year_group"]) if preset.get("year_group") else None,
        status=(preset.get("status") or "").strip() or None,
    )
    names = _student_names()
    tg = (preset.get("tutor_group") or "").strip().lower()
    if tg:
        rows = [r for r in rows if tg in (r.tutor_group or "").lower()]
    q = (preset.get("search") or "").strip().lower()
    if q:
        rows = [r for r in rows if q in r.student_id.lower()
                or q in names.get(r.student_id, "").lower()]
    sf = (preset.get("start_from") or "").strip()
    if sf:
        rows = [r for r in rows if (r.start_date or "") >= sf]
    st = (preset.get("start_to") or "").strip()
    if st:
        rows = [r for r in rows if r.start_date and r.start_date <= st]
    return rows


def search_enrolments() -> None:
    """Feature #9 — free-text search by student ID or name."""
    print("\n═══ Search Enrolments ═══")
    try:
        q = _input("Search (student ID or name)", allow_empty=False).lower()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    names = _student_names()
    rows = [r for r in data.list_enrolments()
            if q in r.student_id.lower() or q in names.get(r.student_id, "").lower()]
    _print_table_paged(rows)
    _row_action_loop(rows)


def filter_by_tutor_group() -> None:
    """Feature #10 — filter enrolments by tutor group (substring match)."""
    print("\n═══ Filter by Tutor Group ═══")
    try:
        tg = _input("Tutor group contains", allow_empty=False).lower()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    rows = [r for r in data.list_enrolments() if tg in (r.tutor_group or "").lower()]
    _print_table_paged(rows)
    _row_action_loop(rows)


def filter_by_date_range() -> None:
    """Feature #11 — filter by a start-date window (inclusive)."""
    print("\n═══ Filter by Start-Date Range ═══")
    try:
        sf = _input("Start on/after (YYYY-MM-DD, blank = any)")
        st = _input("Start on/before (YYYY-MM-DD, blank = any)")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    rows = data.list_enrolments()
    if sf:
        rows = [r for r in rows if (r.start_date or "") >= sf]
    if st:
        rows = [r for r in rows if r.start_date and r.start_date <= st]
    _print_table_paged(rows)
    _row_action_loop(rows)


def quick_filter_current_year() -> None:
    """Feature #15 — list enrolments for the current academic year."""
    year = _default_academic_year()
    print(f"\n═══ Current Year Enrolments ({year}) ═══")
    rows = data.list_enrolments(academic_year=year)
    _print_table_paged(rows)
    _row_action_loop(rows)


def sort_enrolments() -> None:
    """Feature #12 — list all enrolments sorted by a chosen column."""
    print("\n═══ Sort Enrolments ═══")
    keys = {
        "Enrolment #": lambda e: e.enrolment_id,
        "Student ID": lambda e: e.student_id,
        "Academic year": lambda e: e.academic_year,
        "Year group": lambda e: e.year_group,
        "Tutor group": lambda e: (e.tutor_group or ""),
        "Start date": lambda e: (e.start_date or ""),
        "Status": lambda e: e.status,
    }
    try:
        col = _pick_from("Sort by", list(keys))
        direction = _pick_from("Direction", ["Ascending", "Descending"],
                               default="Ascending")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    rows = sorted(data.list_enrolments(), key=keys[col],
                  reverse=(direction == "Descending"))
    _print_table_paged(rows)
    _row_action_loop(rows)


def saved_filter_manager() -> None:
    """Feature #14 — apply / create / delete named filter presets (shared with
    the GUI via the same JSON file)."""
    while True:
        presets = _load_presets()
        print("\n═══ Saved Filter Presets ═══")
        names = sorted(presets)
        for i, name in enumerate(names, 1):
            print(f"  {i}) {name}   {presets[name]}")
        if not names:
            print("  (no presets yet)")
        print("\n  A) Apply   N) New   D) Delete   (Enter to go back)")
        try:
            choice = input("  Action: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not choice:
            return
        if choice == "a" and names:
            try:
                name = _pick_from("Apply which preset", names)
            except _UserAbort:
                continue
            rows = _apply_filter_dict(presets[name])
            _print_table_paged(rows)
            _row_action_loop(rows)
        elif choice == "n":
            try:
                name = _input("Preset name", allow_empty=False)
                preset = {
                    "academic_year": _input("Academic year (blank=any)"),
                    "year_group": _input("Year group (blank=any)"),
                    "status": _input("Status (blank=any)"),
                    "tutor_group": _input("Tutor contains (blank=any)"),
                    "search": _input("Search text (blank=any)"),
                    "start_from": _input("Start from (blank=any)"),
                    "start_to": _input("Start to (blank=any)"),
                }
            except _UserAbort:
                continue
            presets[name] = preset
            _save_json(_PRESETS_PATH, presets)
            print(f"  ✓ Saved preset '{name}'")
        elif choice == "d" and names:
            try:
                name = _pick_from("Delete which preset", names)
            except _UserAbort:
                continue
            presets.pop(name, None)
            _save_json(_PRESETS_PATH, presets)
            print(f"  ✓ Deleted preset '{name}'")


# ════════════════════════════════════════════════════════════════════
# Discovery / integrity / student views (features 16, 17, 18, 19, 20,
# 46, 47, 49)
# ════════════════════════════════════════════════════════════════════

def status_badges() -> None:
    """Feature #16 — counts per status across all enrolments."""
    print("\n═══ Status Summary ═══")
    rows = data.list_enrolments()
    counts = _status_counts(rows)
    print(f"\n  Total: {len(rows)}")
    for s in STATUSES:
        print(f"    {_colour(s, s):<20} {counts.get(s, 0)}")
    _pause()


def student_enrolment_history(student_id: str | None = None) -> None:
    """Feature #17 — every enrolment for one student, newest first."""
    print("\n═══ Student Enrolment History ═══")
    try:
        sid = student_id or _pick_student()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    student = student_data.get_student(sid)
    print(f"\n  {sid} — {student.full_name if student else '(unknown)'}")
    print(f"  Current: {show_current_year_group(sid, _return=True)}")
    rows = data.list_for_student(sid)
    _print_table(rows)
    _pause()


def show_current_year_group(student_id: str | None = None, *, _return: bool = False):
    """Feature #47 — surface the student's current year-group label."""
    if student_id is None:
        print("\n═══ Current Year Group ═══")
        try:
            student_id = _pick_student()
        except _UserAbort:
            print("\n  Cancelled.")
            return None
    label = data.current_year_group_label(student_id) or "Not currently enrolled"
    if _return:
        return label
    print(f"\n  {student_id}: {label}")
    _pause()
    return label


def sync_status_to_student_record(student_id: str | None = None) -> str | None:
    """Feature #49 — reconcile the student's displayed year group with their
    live enrolment. The enrolment is the source of truth (year group is never
    stored on the student row), so this is a non-destructive read."""
    if student_id is None:
        print("\n═══ Reconcile Year Group ═══")
        try:
            student_id = _pick_student()
        except _UserAbort:
            print("\n  Cancelled.")
            return None
    label = data.current_year_group_label(student_id)
    print(f"\n  Authoritative year group for {student_id}: "
          f"{label or 'none (not enrolled)'}")
    print("  (Year group lives only on the enrolment, so nothing can drift.)")
    _pause()
    return label


def students_without_enrolment() -> None:
    """Feature #18 — students on the roll with no enrolment record."""
    print("\n═══ Students Without an Enrolment ═══")
    try:
        students = student_data.list_students()
        enrolled = {e.student_id for e in data.list_enrolments()}
    except Exception as exc:
        print(f"  ✗ {exc}")
        _pause()
        return
    missing = [s for s in students if s.student_id not in enrolled]
    print(f"\n  {len(missing)} student(s) have no enrolment:\n")
    for s in missing:
        print(f"    {s.student_id:<10}  {s.full_name}")
    if missing and _input("\n  Enrol one now? Type 'yes' to confirm",
                          default="no").lower() == "yes":
        enrol_from_student_profile()
    else:
        _pause()


def duplicate_conflicts() -> None:
    """Feature #19 — (student, academic_year) pairs that appear more than once."""
    print("\n═══ Duplicate Enrolment Conflicts ═══")
    seen: dict[tuple[str, str], int] = {}
    dupes: list[Enrolment] = []
    for e in data.list_enrolments():
        key = (e.student_id, e.academic_year)
        seen[key] = seen.get(key, 0) + 1
        if seen[key] > 1:
            dupes.append(e)
    if not dupes:
        print("\n  ✓ No conflicts — every (student, year) pair is unique.")
    else:
        print(f"\n  ✗ {len(dupes)} conflicting row(s):")
        _print_table(dupes)
    _pause()


def advanced_query() -> None:
    """Feature #20 — combine several conditions with AND / OR."""
    print("\n═══ Advanced Query ═══")
    try:
        mode = _pick_from("Match", ["AND", "OR"], default="AND")
        year = _input("Academic year = (blank to skip)")
        yg = _input("Year group = (blank to skip)")
        status = _input("Status = (blank to skip)")
        tutor = _input("Tutor contains (blank to skip)")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    conds: list[Callable[[Enrolment], bool]] = []
    if year:
        conds.append(lambda e, v=year: e.academic_year == v)
    if yg:
        try:
            conds.append(lambda e, v=int(yg): e.year_group == v)
        except ValueError:
            print("  ✗ Year group must be a number.")
            _pause()
            return
    if status:
        conds.append(lambda e, v=status: e.status == v)
    if tutor:
        conds.append(lambda e, v=tutor.lower(): v in (e.tutor_group or "").lower())
    rows = data.list_enrolments()
    if conds:
        combine = all if mode == "AND" else any
        rows = [e for e in rows if combine(c(e) for c in conds)]
    _print_table_paged(rows)
    _row_action_loop(rows)


# ════════════════════════════════════════════════════════════════════
# Reports & analytics (features 21–28)
# ════════════════════════════════════════════════════════════════════

def enrolment_dashboard() -> None:
    """Feature #21 — headline totals, a status bar chart, and breakdowns."""
    print("\n═══ Enrolment Dashboard ═══")
    rows = data.list_enrolments()
    counts = _status_counts(rows)
    by_year: dict[str, int] = {}
    by_yg: dict[int, int] = {}
    for e in rows:
        by_year[e.academic_year] = by_year.get(e.academic_year, 0) + 1
        by_yg[e.year_group] = by_yg.get(e.year_group, 0) + 1
    print(f"\n  Total enrolments: {len(rows)}")
    print("\n  By status:")
    _render_status_bar_chart(counts)  # feature #25
    print("\n  By year group:  " +
          "   ".join(f"Year {yg}: {n}" for yg, n in sorted(by_yg.items())))
    print("  By academic year:  " +
          "   ".join(f"{y}: {n}" for y, n in sorted(by_year.items(), reverse=True)))
    _pause()


def cohort_report(academic_year: str | None = None) -> None:
    """Feature #22 — headcount breakdown for a single academic year."""
    print("\n═══ Cohort Report ═══")
    if academic_year is None:
        try:
            academic_year = _prompt_academic_year(_default_academic_year())
        except _UserAbort:
            print("\n  Cancelled.")
            return
    rows = data.list_enrolments(academic_year=academic_year)
    by_yg: dict[int, dict[str, int]] = {}
    for e in rows:
        by_yg.setdefault(e.year_group, {s: 0 for s in STATUSES})[e.status] += 1
    print(f"\n  {academic_year} — {len(rows)} enrolment(s)\n")
    header = f"  {'Year':<8}" + "".join(f"{s:<11}" for s in STATUSES) + "Total"
    print(header)
    print("  " + "-" * (len(header) - 2))
    for yg in sorted(by_yg):
        c = by_yg[yg]
        print(f"  Year {yg:<3}" + "".join(f"{c.get(s, 0):<11}" for s in STATUSES)
              + str(sum(c.values())))
    total = _status_counts(rows)
    print(f"  {'All':<8}" + "".join(f"{total.get(s, 0):<11}" for s in STATUSES)
          + str(len(rows)))
    _pause()


def retention_report() -> None:
    """Feature #23 — Year 12 → 13 progression rate per academic year."""
    print("\n═══ Retention (Year 12 → 13) ═══")
    rows = data.list_enrolments()
    by_student: dict[str, set[tuple[str, int]]] = {}
    y12_years: set[str] = set()
    for e in rows:
        by_student.setdefault(e.student_id, set()).add((e.academic_year, e.year_group))
        if e.year_group == 12:
            y12_years.add(e.academic_year)
    print(f"\n  {'Y12 year':<12}{'Y12':<8}{'→ Y13':<8}{'Rate':<8}")
    print("  " + "-" * 34)
    for y12_year in sorted(y12_years, reverse=True):
        nxt = _next_academic_year(y12_year)
        cohort = [sid for sid, pairs in by_student.items() if (y12_year, 12) in pairs]
        prog = [sid for sid in cohort if (nxt, 13) in by_student.get(sid, set())]
        rate = (100 * len(prog) / len(cohort)) if cohort else 0
        print(f"  {y12_year:<12}{len(cohort):<8}{len(prog):<8}{rate:.0f}%")
    _pause()


def tutor_group_roster(tutor_group: str | None = None) -> None:
    """Feature #24 — class list for one tutor group (offers PDF export)."""
    print("\n═══ Tutor Group Roster ═══")
    try:
        tg = tutor_group or _input("Tutor group", allow_empty=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    names = _student_names()
    rows = sorted(
        (e for e in data.list_enrolments()
         if (e.tutor_group or "").lower() == tg.lower()),
        key=lambda r: names.get(r.student_id, ""))
    print(f"\n  {tg} — {len(rows)} student(s)\n")
    for i, e in enumerate(rows, 1):
        print(f"    {i:>2}. {e.student_id:<10} {names.get(e.student_id, '—'):<26} "
              f"{e.academic_year}  {e.status}")
    if rows and _input("\n  Export PDF? Type 'yes' to confirm",
                      default="no").lower() == "yes":
        export_tutor_group_pdf(tg)
    else:
        _pause()


def withdrawal_analysis() -> None:
    """Feature #26 — all withdrawn enrolments with their captured reasons."""
    print("\n═══ Withdrawal Analysis ═══")
    names = _student_names()
    rows = data.list_enrolments(status="Withdrawn")
    print(f"\n  {len(rows)} withdrawn enrolment(s):\n")
    for e in rows:
        reason = (e.notes or "—").replace("\n", " ⏎ ")
        print(f"    {e.student_id:<10} {names.get(e.student_id, '—')[:20]:<20} "
              f"{e.academic_year}  {reason[:50]}")
    _pause()


def year_on_year_comparison() -> None:
    """Feature #27 — headcounts side by side across academic years."""
    print("\n═══ Year-on-Year Comparison ═══")
    per_year: dict[str, dict[str, int]] = {}
    for e in data.list_enrolments():
        per_year.setdefault(e.academic_year, {s: 0 for s in STATUSES})[e.status] += 1
    header = f"  {'Year':<10}" + "".join(f"{s:<11}" for s in STATUSES) + "Total"
    print("\n" + header)
    print("  " + "-" * (len(header) - 2))
    for year in sorted(per_year, reverse=True):
        c = per_year[year]
        print(f"  {year:<10}" + "".join(f"{c.get(s, 0):<11}" for s in STATUSES)
              + str(sum(c.values())))
    _pause()


def capacity_utilisation() -> None:
    """Feature #28 — active headcount vs a configured cohort capacity."""
    print("\n═══ Capacity Utilisation ═══")
    try:
        cap_raw = _input("Cohort capacity (number)", allow_empty=False)
        capacity = int(cap_raw)
    except ValueError:
        print("  ✗ Capacity must be a whole number.")
        _pause()
        return
    except _UserAbort:
        print("\n  Cancelled.")
        return
    stats = _compute_capacity_utilisation(data.list_enrolments(), capacity)
    print(f"\n  Active (Enrolled + Pending): {stats['active']}")
    print(f"  Capacity                   : {stats['capacity']}")
    print(f"  Free places                : {stats['free']}")
    print(f"  Utilisation                : {stats['utilisation_pct']}%")
    if stats["over_capacity"]:
        print("  ⚠  Over capacity!")
    _pause()


# ════════════════════════════════════════════════════════════════════
# Import / export / print (features 29–35)
# ════════════════════════════════════════════════════════════════════

_CSV_HEADERS = ("enrolment_id", "student_id", "name", "academic_year",
                "year_group", "tutor_group", "start_date", "status", "notes")


def export_directory_csv() -> None:
    """Feature #29 — export all enrolments to a CSV file."""
    import csv
    print("\n═══ Export Enrolments (CSV) ═══")
    try:
        path = _input("Output path", default="enrolments.csv", allow_empty=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    rows = data.list_enrolments()
    names = _student_names()
    try:
        with open(path, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(_CSV_HEADERS)
            for e in rows:
                w.writerow([
                    e.enrolment_id, e.student_id, names.get(e.student_id, ""),
                    e.academic_year, e.year_group, e.tutor_group or "",
                    e.start_date or "", e.status, (e.notes or "").replace("\n", " ")])
    except Exception as exc:
        logger.exception("CLI CSV export failed")
        print(f"  ✗ {exc}")
        _pause()
        return
    print(f"  ✓ Wrote {len(rows)} row(s) to {path}")
    _pause()


def export_progression_list() -> None:
    """Feature #35 — CSV of who is progressing vs leaving this year."""
    import csv
    print("\n═══ Export Progression List (CSV) ═══")
    year = _default_academic_year()
    try:
        path = _input("Output path",
                      default=f"progression_{year.replace('/', '-')}.csv",
                      allow_empty=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    rows = data.list_enrolments(academic_year=year, status="Enrolled")
    names = _student_names()
    try:
        with open(path, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(("student_id", "name", "year_group", "outcome"))
            for e in rows:
                outcome = ("Progressing to Y13" if e.year_group == 12 else
                           "Leaving (Y13)" if e.year_group == 13 else "—")
                w.writerow((e.student_id, names.get(e.student_id, ""),
                            e.year_group, outcome))
    except Exception as exc:
        logger.exception("CLI progression export failed")
        print(f"  ✗ {exc}")
        _pause()
        return
    print(f"  ✓ Wrote {len(rows)} row(s) to {path}")
    _pause()


def export_enrolment_pdf(enrolment_id: int | None = None) -> None:
    """Feature #30 — printable one-enrolment PDF summary."""
    print("\n═══ Export Enrolment PDF ═══")
    e = _resolve_enrolment(enrolment_id)
    if e is None:
        return
    try:
        path = _input("Output path",
                      default=f"enrolment_{e.enrolment_id}.pdf", allow_empty=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    student = student_data.get_student(e.student_id)
    lines = [
        f"Enrolment #{e.enrolment_id}", "",
        f"Student        : {e.student_id} — {student.full_name if student else '(deleted)'}",
        f"Academic year  : {e.academic_year}",
        f"Year group     : Year {e.year_group}",
        f"Tutor group    : {e.tutor_group or '-'}",
        f"Start date     : {e.start_date or '-'}",
        f"Status         : {e.status}",
        f"Created        : {e.created_at}",
        "", "Notes:", *(e.notes or "-").splitlines(),
    ]
    try:
        _write_simple_pdf(path, "Sixth Form Enrolment", lines)
    except Exception as exc:
        logger.exception("CLI PDF export failed")
        print(f"  ✗ {exc}")
        _pause()
        return
    print(f"  ✓ Saved PDF to {path}")
    _pause()


def export_tutor_group_pdf(tutor_group: str | None = None) -> None:
    """Feature #33 — printable tutor-group roster PDF."""
    print("\n═══ Export Roster PDF ═══")
    try:
        tg = tutor_group or _input("Tutor group", allow_empty=False)
        path = _input("Output path", default=f"roster_{tutor_group or 'group'}.pdf",
                      allow_empty=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    names = _student_names()
    rows = sorted(
        (e for e in data.list_enrolments()
         if (e.tutor_group or "").lower() == tg.lower()),
        key=lambda r: names.get(r.student_id, ""))
    lines = [f"Tutor group: {tg}    ({len(rows)} students)", ""]
    lines += [f"{i + 1:>2}. {e.student_id:<10} {names.get(e.student_id, '-'):<28} "
              f"{e.academic_year}  {e.status}" for i, e in enumerate(rows)]
    try:
        _write_simple_pdf(path, "Tutor Group Roster", lines)
    except Exception as exc:
        logger.exception("CLI roster PDF export failed")
        print(f"  ✗ {exc}")
        _pause()
        return
    print(f"  ✓ Saved roster to {path}")
    _pause()


def copy_enrolment_details(enrolment_id: int | None = None) -> None:
    """Feature #34 — print a formatted, copy-ready enrolment summary.

    (A terminal has no reliable clipboard, so the CLI analogue is to render
    the block for the user to copy.)"""
    print("\n═══ Copy Enrolment Details ═══")
    e = _resolve_enrolment(enrolment_id)
    if e is None:
        return
    student = student_data.get_student(e.student_id)
    print("\n  ----- copy below -----")
    print(f"  Enrolment #{e.enrolment_id}")
    print(f"  Student: {e.student_id} — {student.full_name if student else '(deleted)'}")
    print(f"  Year: {e.academic_year} · Year {e.year_group}")
    print(f"  Tutor: {e.tutor_group or '—'} · Start: {e.start_date or '—'}")
    print(f"  Status: {e.status}")
    print("  ----------------------")
    _pause()


def _preview_import_diff(records: list[dict[str, str]]) -> list[dict[str, str]]:
    """Feature #32 — classify parsed CSV rows as new / duplicate / invalid,
    print the verdicts, and return the importable (new) subset."""
    existing = {(e.student_id, e.academic_year) for e in data.list_enrolments()}
    valid_students = {s.student_id for s in student_data.list_students()}
    importable: list[dict[str, str]] = []
    print(f"\n  {'Student':<12}{'Year':<10}{'YG':<5}Verdict")
    print("  " + "-" * 56)
    for rec in records:
        sid = (rec.get("student_id") or "").strip()
        year = (rec.get("academic_year") or "").strip()
        yg = (rec.get("year_group") or "").strip()
        if sid not in valid_students:
            verdict = "unknown student — skipped"
        elif not enrolments._ACADEMIC_YEAR_RE.match(year):
            verdict = "bad academic year — skipped"
        elif (sid, year) in existing:
            verdict = "duplicate — skipped"
        else:
            verdict = "new — will import"
            importable.append(rec)
        print(f"  {sid:<12}{year:<10}{yg:<5}{verdict}")
    return importable


def import_enrolments_csv() -> None:
    """Feature #31 — bulk-import enrolments from CSV with a validated preview."""
    import csv
    print("\n═══ Import Enrolments (CSV) ═══")
    try:
        path = _input("Input CSV path", allow_empty=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        with open(path, newline="", encoding="utf-8") as fh:
            records = list(csv.DictReader(fh))
    except Exception as exc:
        logger.exception("CLI CSV import read failed")
        print(f"  ✗ Could not read file: {exc}")
        _pause()
        return
    print(f"\n  {len(records)} row(s) read.")
    importable = _preview_import_diff(records)
    if not importable:
        print("\n  Nothing importable.")
        _pause()
        return
    if _input(f"\n  Import {len(importable)} new row(s)? Type 'yes' to confirm",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    ok: list[str] = []
    fail: list[str] = []
    for rec in importable:
        try:
            data.create_enrolment({
                "student_id": rec.get("student_id", "").strip(),
                "academic_year": rec.get("academic_year", "").strip(),
                "year_group": rec.get("year_group", "").strip(),
                "tutor_group": (rec.get("tutor_group") or "").strip() or None,
                "start_date": (rec.get("start_date") or "").strip() or None,
                "status": (rec.get("status") or DEFAULT_STATUS).strip(),
                "notes": (rec.get("notes") or "").strip() or None,
            })
            ok.append(rec.get("student_id", "?"))
        except Exception as exc:
            fail.append(f"{rec.get('student_id', '?')}: {exc}")
    _report_bulk("CSV import", ok, fail)


# ════════════════════════════════════════════════════════════════════
# Academic-year list manager (feature 50)
# ════════════════════════════════════════════════════════════════════

def academic_year_manager() -> None:
    """Feature #50 — CRUD the list of academic years offered in prompts
    (shared with the GUI via the same JSON file)."""
    while True:
        years = _load_academic_years() or [_default_academic_year()]
        print("\n═══ Academic Years ═══")
        for i, y in enumerate(sorted(set(years), reverse=True), 1):
            print(f"  {i}) {y}")
        print("\n  A) Add   D) Delete   (Enter to go back)")
        try:
            choice = input("  Action: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not choice:
            return
        if choice == "a":
            try:
                val = _input("New academic year (YYYY/YY)", allow_empty=False)
            except _UserAbort:
                continue
            if not enrolments._ACADEMIC_YEAR_RE.match(val):
                print("  ✗ Must look like '2025/26'.")
                continue
            years.append(val)
            _save_json(_YEARS_PATH, sorted(set(years)))
            print(f"  ✓ Added {val}")
        elif choice == "d":
            uniq = sorted(set(years), reverse=True)
            try:
                val = _pick_from("Delete which year", uniq)
            except _UserAbort:
                continue
            years = [y for y in years if y != val]
            _save_json(_YEARS_PATH, sorted(set(years)))
            print(f"  ✓ Removed {val}")


# ── Submenu dispatcher ──────────────────────────────────────────────

# Grouped menus keep 50+ actions navigable. Each tuple is (label, handler).
_CRUD_MENU: list[tuple[str, Callable[[], None]]] = [
    ("List All Enrolments", list_all),
    ("Filter Enrolments",   filter_enrolments),
    ("New Enrolment",       new_enrolment),
    ("View Enrolment",      view_enrolment),
    ("Edit Enrolment",      edit_enrolment),
    ("Delete Enrolment",    delete_enrolment_flow),
    ("Enrol a Student",     enrol_from_student_profile),
]

_WORKFLOW_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Bulk Enrol",              bulk_enrol),
    ("Progression Wizard",      progression_wizard),
    ("End-of-Year Rollover",    end_of_year_rollover),
    ("Re-enrol Student",        reenrol_student),
    ("Duplicate Enrolment",     duplicate_enrolment),
    ("Withdraw Enrolment",      withdraw_enrolment),
    ("Soft-delete Toggle",      soft_delete_toggle),
    ("Transfer Enrolment",      transfer_enrolment),
    ("Undo Last Action",        undo_last_action),
]

_BULK_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Bulk Status Change",   bulk_status_change),
    ("Bulk Tutor Reassign",  bulk_tutor_reassign),
    ("Bulk Delete",          bulk_delete),
]

_SEARCH_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Search (ID / name)",       search_enrolments),
    ("Filter by Tutor Group",    filter_by_tutor_group),
    ("Filter by Date Range",     filter_by_date_range),
    ("Current Year",             quick_filter_current_year),
    ("Sort Enrolments",          sort_enrolments),
    ("Advanced Query",           advanced_query),
    ("Saved Filter Presets",     saved_filter_manager),
    ("Status Summary",           status_badges),
]

_REPORT_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Dashboard",                 enrolment_dashboard),
    ("Cohort Report",             cohort_report),
    ("Retention",                 retention_report),
    ("Tutor Group Roster",        tutor_group_roster),
    ("Withdrawal Analysis",       withdrawal_analysis),
    ("Year-on-Year Comparison",   year_on_year_comparison),
    ("Capacity Utilisation",      capacity_utilisation),
    ("Student Enrolment History", student_enrolment_history),
    ("Students Without Enrolment", students_without_enrolment),
    ("Duplicate Conflicts",       duplicate_conflicts),
]

_DATA_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Export CSV",           export_directory_csv),
    ("Export Progression",   export_progression_list),
    ("Export Enrolment PDF", export_enrolment_pdf),
    ("Export Roster PDF",    export_tutor_group_pdf),
    ("Import CSV",           import_enrolments_csv),
    ("Copy Enrolment",       copy_enrolment_details),
]

_ADMIN_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Academic Year Manager",     academic_year_manager),
    ("Current Year Group",        show_current_year_group),
    ("Reconcile Year Group",      sync_status_to_student_record),
    ("Per-record Context Menu",   context_menu),
    ("Keyboard Shortcuts",        keyboard_shortcuts_help),
]

_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Records (CRUD)",     lambda: _submenu("Records", _CRUD_MENU)),
    ("Workflows",          lambda: _submenu("Workflows", _WORKFLOW_MENU)),
    ("Bulk Operations",    lambda: _submenu("Bulk Operations", _BULK_MENU)),
    ("Search & Filter",    lambda: _submenu("Search & Filter", _SEARCH_MENU)),
    ("Reports & Analytics", lambda: _submenu("Reports & Analytics", _REPORT_MENU)),
    ("Import / Export",    lambda: _submenu("Import / Export", _DATA_MENU)),
    ("Admin & Tools",      lambda: _submenu("Admin & Tools", _ADMIN_MENU)),
]


def _submenu(title: str, entries: list[tuple[str, Callable[[], None]]]) -> None:
    """Render a categorised submenu and dispatch its handlers safely."""
    while True:
        print(f"\n── {title} ──")
        for i, (label, _) in enumerate(entries, 1):
            print(f"  {i}) {label}")
        print("  0) Back")
        try:
            choice = input("  Select: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if choice == "0":
            return
        if not choice.isdigit() or not (1 <= int(choice) <= len(entries)):
            print("  Invalid selection.")
            continue
        _, handler = entries[int(choice) - 1]
        try:
            handler()
        except _UserAbort:
            print("\n  Cancelled.")
        except Exception as e:
            logger.exception("Enrolment CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def run() -> None:
    """Show the Enrolment submenu until the user picks Back."""
    while True:
        print("\n── Enrolment ──")
        for i, (label, _) in enumerate(_MENU, 1):
            print(f"  {i}) {label}")
        print("  0) Back")
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
        _, handler = _MENU[int(choice) - 1]
        try:
            handler()
        except _UserAbort:
            print("\n  Cancelled.")
        except Exception as e:
            logger.exception("Enrolment CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    """Run the enrolment submenu when the parent CLI hits "Enrolment".

    Returns True so the caller skips its stub message.
    """
    if label != "Enrolment":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Enrolment CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
