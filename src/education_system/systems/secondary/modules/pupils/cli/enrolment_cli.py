"""Enrolment & Leavers in the terminal. Rules live in :mod:`modules.pupils.domain.enrolment`.
When updating details, Enter keeps a value and ``-`` clears it."""

from __future__ import annotations

from education_system.systems.secondary.modules.pupils.cli.pupils_cli import choose_pupil
from education_system.systems.secondary.modules.admissions.domain import admissions as A
from education_system.systems.secondary.modules.pupils.domain import enrolment as EN
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.cli.prompts.prompts import ask as _ask
from education_system.systems.secondary.ui.cli.prompts.prompts import pause as _pause
from education_system.systems.secondary.ui.cli.prompts.prompts import prompt as _prompt
from education_system.systems.secondary.ui.cli.prompts.prompts import yes as _yes

_ERRORS = (EN.ValidationError, EN.PermissionDenied, EN.NotFound)


def _pick(options: list[str], label: str, *, allow_blank: bool = False) -> str | None:
    for i, opt in enumerate(options, 1):
        print(f"    {i}) {opt}")
    raw = _prompt(f"  {label}{'' if allow_blank else ' *'}: ")
    if not raw:
        return "" if allow_blank else None
    if raw.isdigit() and 1 <= int(raw) <= len(options):
        return options[int(raw) - 1]
    print("  Not one of the choices.")
    return None


def _print_problem(e: Exception) -> None:
    if isinstance(e, EN.ValidationError):
        print("\n  Please fix:")
        for p in e.problems:
            print(f"   • {p}")
    else:
        print(f"\n  Not done: {e}")


def _print_leavers(rows: list[EN.LeaverView]) -> None:
    if not rows:
        print("\n  None.")
        return
    print(f"\n  {'#':>3}  {'Adm. no':<9} {'Pupil':<24} {'Yr':>2}  {'Left':<10}  Reason")
    for i, v in enumerate(rows, 1):
        p = v.pupil
        print(f"  {i:>3}  {p.admission_no:<9} {p.display_name[:24]:<24} {p.year_group:>2}  "
              f"{p.leaving_date or '':<10}  {p.leaving_reason or ''}")
        for a in v.actions():
            print(f"{'':>8}→ {a}")


def _choose(rows: list[EN.LeaverView]) -> EN.LeaverView | None:
    raw = _prompt("\n  Number to open (Enter to go back): ")
    if raw.isdigit() and 1 <= int(raw) <= len(rows):
        return rows[int(raw) - 1]
    return None


# ── Menu ─────────────────────────────────────────────────────────────

def menu(principal: Principal) -> None:
    if not principal.can_open(EN.MENU_LABEL):
        print("\n  " + principal.denied_message(EN.MENU_LABEL).replace("\n\n", "\n  "))
        _pause()
        return
    year = A.current_academic_year()
    while True:
        due = len(EN.list_leavers(actions_only=True))
        print(f"\n── Enrolment & Leavers ── (year: {year})")
        print("  1) Roll summary")
        print(f"  2) Actions due ({due})")
        print("  3) Leavers")
        print("  4) Joiners")
        print("  5) Record a leaver")
        print("  6) Leaving details for a pupil")
        print("  7) Reinstate a pupil")
        print("  8) Change year")
        print("  0) Back")
        choice = _prompt("Select: ")
        if choice in {"0", "", "q"}:
            return
        if choice == "1":
            summary(year)
        elif choice == "2":
            leavers(principal, None, actions_only=True)
        elif choice == "3":
            leavers(principal, year)
        elif choice == "4":
            joiners(year)
        elif choice == "5":
            record(principal)
        elif choice == "6":
            pupil = choose_pupil()
            if pupil:
                show(principal, pupil.pupil_id)
        elif choice == "7":
            pupil = choose_pupil()
            if pupil:
                reinstate(principal, pupil.pupil_id)
        elif choice == "8":
            picked = _pick(A.academic_year_choices()[:3], "Academic year")
            year = picked or year


def summary(year: str) -> None:
    s = EN.roll_summary(year)
    activity_log.record("enrolment.overview", target=year)
    print(f"\n── Roll summary {year} ──")
    print(f"  On roll now: {s.on_roll}  ("
          + ", ".join(f"Y{y} {n}" for y, n in s.on_roll_by_year.items()) + ")")
    print(f"  Joined in {year}: {s.joiners}")
    print(f"  Left in {year}: {s.leavers}")
    for reason, n in sorted(s.leavers_by_reason.items(), key=lambda kv: -kv[1]):
        print(f"      {n:>4}  {reason}")
    print(f"  Leavers with actions due: {s.actions_due}")
    _pause()


def leavers(principal: Principal, year: str | None, *, actions_only: bool = False) -> None:
    reason = None
    search = None
    if not actions_only:
        print("\n  Filter by reason (Enter for all):")
        reason = _pick(list(EN.REASONS), "Reason", allow_blank=True) or None
        search = _prompt("  Search name / adm. no (Enter for all): ") or None
    rows = EN.list_leavers(academic_year=year, reason=reason, actions_only=actions_only,
                           search=search)
    activity_log.record("enrolment.leavers.list", results=len(rows),
                        target="actions" if actions_only else year)
    print(f"\n── {'Actions due' if actions_only else f'Leavers {year}'} ──")
    _print_leavers(rows)
    chosen = _choose(rows) if rows else None
    if chosen:
        show(principal, chosen.pupil.pupil_id)


def joiners(year: str) -> None:
    rows = EN.list_joiners(year)
    activity_log.record("enrolment.joiners.list", target=year, results=len(rows))
    print(f"\n── Joiners {year} ──")
    if not rows:
        print("\n  None.")
    for p in rows:
        print(f"  {p.admission_no:<9} {p.display_name[:26]:<26} Y{p.year_group:<3}"
              f"{p.form_group or '':<6} joined {p.admission_date}  {p.roll_status_label}")
    _pause()


def show(principal: Principal, pupil_id: int) -> None:
    while True:
        pupil = P.get_pupil(pupil_id)
        if pupil is None:
            return
        if pupil.roll_status != "left":
            print(f"\n  {pupil.display_name} is on roll ({pupil.roll_status_label}).")
            if _yes("  Record them as a leaver?"):
                record(principal, pupil)
                continue
            return
        current = EN.current_leaving(pupil_id)
        activity_log.record("enrolment.details.open", target=pupil.admission_no)
        print(f"\n── {pupil.display_name} ({pupil.admission_no}) ──")
        print(f"  Left on: {pupil.leaving_date or '—'}   Reason: {pupil.leaving_reason or '—'}")
        if current:
            for key in EN.DETAIL_FIELDS:
                value = getattr(current, key)
                if value:
                    print(f"  {EN.FIELD_LABELS[key]}: {value}")
        for a in EN.LeaverView(pupil, current).actions():
            print(f"  → {a}")
        print("\n  D) Update leaving details   R) Reinstate   0) Back")
        choice = _prompt("Select: ").lower()
        if choice == "d":
            update_details(principal, pupil, current)
        elif choice == "r":
            reinstate(principal, pupil_id)
        else:
            return


def _details(reason: str, current: EN.Leaving | None) -> dict:
    """Ask for the leaving details. Keys left out keep their current value."""
    out: dict = {}
    for key in ("destination_school", "destination_urn", "destination_la"):
        hint = "6 digits" if key == "destination_urn" else ""
        value = _ask(EN.FIELD_LABELS[key], getattr(current, key) if current else None,
                     hint=hint)
        if value is not None:
            out[key] = value
    if reason == EN.END_OF_Y11:
        now = current.post16_destination if current else None
        print(f"  Post-16 destination{f' [{now}]' if now else ''} (Enter to keep):")
        picked = _pick(list(EN.POST16_DESTINATIONS), "Choice", allow_blank=True)
        if picked:
            out["post16_destination"] = picked
    for key in ("ctf_sent_date", "la_notified_date"):
        value = _ask(EN.FIELD_LABELS[key], getattr(current, key) if current else None,
                     hint="YYYY-MM-DD")
        if value is not None:
            out[key] = value
    value = _ask("Notes", current.notes if current else None)
    if value is not None:
        out["notes"] = value
    return out


def record(principal: Principal, pupil: P.Pupil | None = None) -> None:
    if pupil is None:
        pupil = choose_pupil("Pupil who is leaving (adm. no, UPN or name)")
        if pupil is None:
            return
    if pupil.roll_status == "left":
        print(f"\n  {pupil.display_name} has already left.")
        return
    activity_log.record("enrolment.leave.open", target=pupil.admission_no)
    print(f"\n── Record leaver: {pupil.display_name} (Year {pupil.year_group}) ──")
    date = _prompt("  Last day on roll * (YYYY-MM-DD): ")
    print("  Reason:")
    reason = _pick(list(EN.REASONS), "Reason")
    if not reason:
        return
    details = _details(reason, None)
    if not _yes(f"\n  Take {pupil.display_name} off roll? Their login will be closed."):
        activity_log.record("enrolment.leave.cancel")
        return
    try:
        view = EN.record_leaver(pupil.pupil_id, leaving_date=date, reason=reason,
                                details=details, actor=principal)
    except _ERRORS as e:
        _print_problem(e)
        _pause()
        return
    print(f"\n  ✓ {pupil.display_name} is now off roll.")
    for a in view.actions():
        print(f"  Still to do: {a}")
    _pause()


def update_details(principal: Principal, pupil: P.Pupil, current: EN.Leaving | None) -> None:
    reason = current.reason if current else (pupil.leaving_reason or EN.OTHER)
    details = _details(reason, current)
    if not details and current is not None:
        print("  Nothing changed.")
        return
    try:
        EN.record_details(pupil.pupil_id, details, actor=principal)
    except _ERRORS as e:
        _print_problem(e)
        _pause()
        return
    print("  ✓ Leaving details saved.")


def reinstate(principal: Principal, pupil_id: int) -> None:
    pupil = P.get_pupil(pupil_id)
    if pupil is None:
        return
    if pupil.roll_status != "left":
        print(f"\n  {pupil.display_name} is already on roll.")
        return
    print(f"\n  Put {pupil.display_name} back on roll? Their login reopens with the same "
          "username and password.")
    raw = _prompt(f"  Year group [{pupil.year_group}]: ")
    note = _prompt("  Reason *: ")
    try:
        year = int(raw) if raw else pupil.year_group
        EN.reinstate(pupil_id, actor=principal, note=note, year_group=year)
    except ValueError:
        print("  Year group must be a number.")
        return
    except _ERRORS as e:
        _print_problem(e)
        _pause()
        return
    print(f"  ✓ {pupil.display_name} is back on roll.")
    _pause()
