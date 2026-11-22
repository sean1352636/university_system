"""Shared prompt, picker and print helpers for the admissions CLI."""

from __future__ import annotations

import json
import logging
import os
import subprocess
from datetime import date as _date
from typing import Any, Callable
from education_system.systems.sixth_form.domain.admissions import (
    admissions as data,
    status_rules,
)
from education_system.systems.sixth_form.domain.governance.user_management import (
    access,
)
from education_system.systems.sixth_form.domain.admissions.admissions import (
    Applicant,
    STATUSES,
    ValidationError,
)

logger = logging.getLogger(__name__)

_ERRORS = (access.AccessDenied, ValueError)



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


def _input_validated(prompt: str, validator: Callable[[Any], Any], *,
                     default: str = "") -> str:
    """Prompt, re-prompting until the domain validator accepts (item 19)."""
    while True:
        val = _input(prompt, default=default)
        try:
            validator(val)
            return val
        except ValidationError as e:
            print(f"    ✗ {e} — try again (or 'cancel').")


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


def _pick_subject(label: str, default: str | None = None) -> str | None:
    """Pick from the live subjects catalogue. Empty = skip."""
    try:
        from education_system.systems.sixth_form.domain.academics.subjects import (
            subjects as _subjects,
        )
        names = [s.name for s in _subjects.list_subjects()]
    except Exception:
        names = []
    if not names:
        return _input(label, default=default or "") or None
    return _pick_from(label, names, default=default)


def _pick_applicant() -> Applicant:
    rows = data.list_applicants()
    if not rows:
        print("    No applicants.")
        raise _UserAbort
    print("\n  Applicants:")
    for i, a in enumerate(rows, 1):
        print(f"    {i:>3}) {a.applicant_id}  {a.full_name[:24]:<24}  "
              f"[{a.status}]")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or applicant id)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1]
            continue
        match = next((a for a in rows
                       if a.applicant_id.lower() == raw.lower()), None)
        if match:
            return match
        print("    No matching applicant.")


def _yes(prompt: str, *, default: str = "no") -> bool:
    return _input(f"{prompt} (y/n)", default=default).lower() in (
        "y", "yes")


def _pick_many_applicants() -> list[Applicant]:
    """Pick several applicants by comma-separated indices and/or ids."""
    rows = data.list_applicants()
    if not rows:
        print("    No applicants.")
        raise _UserAbort
    print("\n  Applicants:")
    for i, a in enumerate(rows, 1):
        print(f"    {i:>3}) {a.applicant_id}  {a.full_name[:24]:<24}  "
              f"[{a.status}]")
    raw = _input("  Pick numbers/ids (comma-separated)", allow_empty=False)
    picked: dict[str, Applicant] = {}
    for tok in raw.replace(" ", "").split(","):
        if not tok:
            continue
        if tok.isdigit() and 1 <= int(tok) <= len(rows):
            a = rows[int(tok) - 1]
            picked[a.applicant_id] = a
        else:
            m = next((a for a in rows
                       if a.applicant_id.lower() == tok.lower()), None)
            if m:
                picked[m.applicant_id] = m
    if not picked:
        print("    Nothing matched.")
        raise _UserAbort
    return list(picked.values())


def _pick_grade(label: str) -> str:
    grades = ["A*", "A", "B", "C", "D", "E",
              "9", "8", "7", "6", "5", "4"]
    return _pick_from(label, grades)


def _age(dob: str | None) -> int | None:
    if not dob:
        return None
    try:
        d = _date.fromisoformat(dob[:10])
    except ValueError:
        return None
    t = _date.today()
    years = t.year - d.year - ((t.month, t.day) < (d.month, d.day))
    return years if 0 <= years < 130 else None


def _days_in_stage(a: Applicant) -> int | None:
    try:
        d = _date.fromisoformat((a.updated_at or "")[:10])
    except ValueError:
        return None
    return max(0, (_date.today() - d).days)


# ── Print helpers ──────────────────────────────────────────────────

def _print_applicants(rows: list[Applicant], *, sort_by: str = "") -> None:
    if not rows:
        print("\n  (no applicants)")
        return
    rows = _sort_rows(rows, sort_by) if sort_by else rows
    print()
    print(f"  {'ID':<10}  {'Name':<22}  {'Age':>3}  {'Submitted':<10}  "
          f"{'Days':>4}  {'Status':<20}  Subjects")
    print("  " + "-" * 108)
    for a in rows:
        subj = ", ".join(a.subjects)[:28]
        age = _age(a.dob)
        days = _days_in_stage(a)
        flag = "!" if (a.is_open and days is not None and days >= 14) else " "
        print(f"  {a.applicant_id:<10}  {a.full_name[:22]:<22}  "
              f"{(str(age) if age is not None else '—'):>3}  "
              f"{a.submitted_at:<10}  "
              f"{(str(days) if days is not None else '—'):>3}{flag}  "
              f"{a.status:<20}  {subj}")
    # Status-count footer (item 10).
    counts: dict[str, int] = {}
    for a in rows:
        counts[a.status] = counts.get(a.status, 0) + 1
    tally = " · ".join(f"{counts[s]} {s}" for s in STATUSES if s in counts)
    print(f"\n  {len(rows)} shown  —  {tally}")


_SORT_KEYS: dict[str, Callable[[Applicant], Any]] = {
    "id": lambda a: a.applicant_id,
    "name": lambda a: a.full_name.lower(),
    "age": lambda a: _age(a.dob) if _age(a.dob) is not None else -1,
    "submitted": lambda a: a.submitted_at or "",
    "days": lambda a: _days_in_stage(a) if _days_in_stage(a)
    is not None else -1,
    "status": lambda a: a.status,
}


def _sort_rows(rows: list[Applicant], key: str) -> list[Applicant]:
    reverse = key.startswith("-")
    name = key.lstrip("-")
    fn = _SORT_KEYS.get(name)
    if fn is None:
        return rows
    return sorted(rows, key=fn, reverse=reverse)


# ── Sidecar JSON + shared helpers ──────────────────────────────────
# Small bits of GUI/CLI-only state (interview rooms, slot caps, saved
# views) live next to the admissions DB rather than in the schema.

ROOMS_FILE = "admissions_interview_rooms.json"


CONFIG_FILE = "admissions_config.json"


VIEWS_FILE = "admissions_saved_views.json"


DEFAULT_SLOT_CAP = 8


REQUIRED_DOCS = ("Personal Statement", "Reference Letter", "Transcript")

# Rough probability an applicant in a given open stage eventually enrols.
_ENROL_PROB = {
    "Submitted": 0.15, "Under Review": 0.25, "Interview Scheduled": 0.40,
    "Interviewed": 0.55, "Offer Made": 0.70, "Waitlisted": 0.20,
    "Offer Accepted": 0.95,
}


def _sidecar_path(name: str):
    from pathlib import Path
    return Path(data.DB_PATH).parent / name


def _load_json(name: str, default):
    p = _sidecar_path(name)
    if not p.exists():
        return default
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 — a corrupt sidecar shouldn't break the CLI
        return default


def _store_json(name: str, obj) -> None:
    _sidecar_path(name).write_text(json.dumps(obj, indent=2), encoding="utf-8")


def _forecast_enrolment(applicants: list[Applicant]) -> dict:
    """Projected enrolments = already enrolled + expected from the pipeline."""
    enrolled = sum(1 for a in applicants if a.status == "Enrolled")
    expected = 0.0
    contributing = 0
    for a in applicants:
        p = _ENROL_PROB.get(a.status)
        if p:
            expected += p
            contributing += 1
    return {"enrolled": enrolled, "expected_additional": round(expected, 1),
            "projected_total": round(enrolled + expected),
            "in_pipeline": contributing}


def _merge_ics(applicant_ids: list[str]) -> tuple[str, int]:
    """Combine each applicant's single-event calendar into one VCALENDAR."""
    events: list[str] = []
    for aid in applicant_ids:
        try:
            cal = data.interview_to_ics(aid)
        except Exception:  # noqa: BLE001 — skip applicants without an interview
            continue
        start = cal.find("BEGIN:VEVENT")
        end = cal.find("END:VEVENT")
        if start != -1 and end != -1:
            events.append(cal[start:end + len("END:VEVENT")])
    body = "\r\n".join(["BEGIN:VCALENDAR", "VERSION:2.0",
                        "PRODID:-//SixthForm//Admissions//EN",
                        *events, "END:VCALENDAR"])
    return body + "\r\n", len(events)


def _send_to_printer(text: str) -> None:
    """Send plain text to the default printer (lpr / Windows print)."""
    if os.name == "nt":
        import tempfile
        fd, path = tempfile.mkstemp(suffix=".txt", text=True)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.startfile(path, "print")  # type: ignore[attr-defined]
        return
    proc = subprocess.run(["lpr"], input=text.encode("utf-8"),
                          stderr=subprocess.PIPE, check=False)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode("utf-8", "replace").strip()
                           or f"lpr exited with status {proc.returncode}")


def _open_path(path: str) -> None:
    """Open a file with the OS default handler."""
    import sys
    if sys.platform.startswith("darwin"):
        subprocess.run(["open", path], check=False)
    elif os.name == "nt":
        os.startfile(path)  # type: ignore[attr-defined]
    else:
        subprocess.run(["xdg-open", path], check=False)


def _fresh(a: Applicant) -> Applicant:
    """Re-read the applicant so each action sees the latest state."""
    return data.get_applicant(a.applicant_id) or a


# ── Menus ─────────────────────────────────────────────────────────

def _run_submenu(title: str,
                 items: list[tuple[str, Callable[[], None]]]) -> None:
    while True:
        print(f"\n── {title} ──")
        for i, (label, _) in enumerate(items, 1):
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
        if not choice.isdigit() or not (1 <= int(choice) <= len(items)):
            print("  Invalid selection.")
            continue
        label, handler = items[int(choice) - 1]
        if label.startswith("─"):
            continue
        try:
            handler()
        except _UserAbort:
            print("\n  Cancelled.")
        except _ERRORS as e:
            # Refusals (no permission, a rule broken) are shown, never
            # swallowed: the domain explains what to do instead.
            print(f"\n  ✗ {e}")
            _pause()
        except Exception as e:  # noqa: BLE001
            logger.exception("Admissions CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def _cli_user() -> str | None:
    """Username of whoever is signed in (stamped on records)."""
    try:
        return access.current().username or None
    except Exception:  # noqa: BLE001 — no session means no stamp
        return None


def _can(capability: str) -> bool:
    """Whether the signed-in user holds *capability* (hide what they can't do)."""
    try:
        return access.current().can(capability)
    except Exception:  # noqa: BLE001
        return False


def _fail(e: BaseException) -> None:
    print(f"  ✗ {e}")


def _attempt(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> tuple[bool, Any]:
    """Run a domain call; on a refusal print it and return (False, None)."""
    try:
        return True, fn(*args, **kwargs)
    except _ERRORS as e:
        _fail(e)
        return False, None


def _show_messages(msgs: Any) -> None:
    """Print queued e-mails with their honest delivery label."""
    rows = msgs if isinstance(msgs, (list, tuple)) else [msgs]
    if not rows:
        print("  (nothing was queued — no address on file?)")
    for m in rows:
        print(f"    {m.recipient_role:<9} {m.to_name or ''} <{m.to_address}>"
              f"  — {m.label}")


def _pick_reason(label: str, reasons: Any, *, optional: bool = True
                 ) -> str | None:
    """Pick one of *reasons*; with *optional* '(none)' returns None."""
    opts = (["(none)"] if optional else []) + list(reasons)
    got = _pick_from(label, opts, default="(none)" if optional else None)
    return None if got == "(none)" else got


def _pick_status(a: Applicant, label: str = "New status") -> str:
    """Only the statuses this applicant may move to next."""
    allowed = list(data.allowed_statuses(a.applicant_id))
    if not allowed:
        print(f"    {a.applicant_id} is {a.status}: no status change is "
              "possible from here"
              + (" (reopen it first)." if a.status in status_rules.REOPENABLE
                 else "."))
        raise _UserAbort
    return _pick_from(label, allowed)


def _sub(module: str, attr: str = "run") -> Callable[[], None]:
    """Menu handler that imports a sibling CLI module only when chosen."""
    def handler() -> None:
        import importlib
        getattr(importlib.import_module(
            f"education_system.systems.sixth_form.interfaces.cli.admissions."
            f"{module}"), attr)()
    return handler
