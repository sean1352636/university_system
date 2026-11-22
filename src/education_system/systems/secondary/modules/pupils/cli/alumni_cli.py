"""Alumni in the terminal. Rules live in :mod:`modules.pupils.domain.alumni`.
When editing, Enter keeps a value and ``-`` clears it."""

from __future__ import annotations

from education_system.systems.secondary.modules.communication.domain import email_outbox as E
from education_system.systems.secondary.modules.pupils.domain import alumni as AL
from education_system.systems.secondary.modules.pupils.domain import enrolment as EN
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.cli.prompts import prompts
from education_system.systems.secondary.ui.cli.prompts.prompts import ask as _ask
from education_system.systems.secondary.ui.cli.prompts.prompts import pause as _pause
from education_system.systems.secondary.ui.cli.prompts.prompts import prompt as _prompt
from education_system.systems.secondary.ui.cli.prompts.prompts import yes as _yes

_ERRORS = (AL.ValidationError, AL.PermissionDenied, AL.NotFound)


def _problem(e: Exception) -> None:
    prompts.problem(e, "Please fix:")


def _pick(options: list[str], label: str, *, allow_blank: bool = True) -> str | None:
    """Numbered choice. '' = keep/skip, None = invalid."""
    for i, opt in enumerate(options, 1):
        print(f"    {i}) {opt}")
    raw = _prompt(f"  {label}: ")
    if not raw:
        return "" if allow_blank else None
    if raw == "-":
        return "-"
    if raw.isdigit() and 1 <= int(raw) <= len(options):
        return options[int(raw) - 1]
    print("  Not one of the choices.")
    return None


def _table(rows: list[AL.Alumnus]) -> None:
    if not rows:
        print("\n  None.")
        return
    print(f"\n  {'#':>3}  {'Ref':<8} {'Name':<24} {'Left':<8} {'Now doing':<22} "
          f"{'E-mail':<11} Status")
    for i, a in enumerate(rows, 1):
        print(f"  {i:>3}  {a.alumni_ref:<8} {a.display_name[:24]:<24} {a.leaving_year:<8} "
              f"{(a.current_activity or '')[:22]:<22} "
              f"{('Yes' if a.can_contact else a.contact_problem or '')[:11]:<11} "
              f"{a.status_label}")


def _choose(rows: list[AL.Alumnus]) -> AL.Alumnus | None:
    raw = _prompt("\n  Number to open (Enter to go back): ")
    if raw.isdigit() and 1 <= int(raw) <= len(rows):
        return rows[int(raw) - 1]
    return None


# ── Menu ─────────────────────────────────────────────────────────────

def menu(principal: Principal) -> None:
    if not principal.can_open(AL.MENU_LABEL):
        print("\n  " + principal.denied_message(AL.MENU_LABEL).replace("\n\n", "\n  "))
        _pause()
        return
    activity_log.record("alumni.open")
    while True:
        s = AL.summary()
        print(f"\n── Alumni ── {s.total} alumni · {s.contactable} can be e-mailed · "
              f"{s.can_help} happy to help")
        print("  1) List / search")
        print("  2) Open by ref or admission no.")
        print("  3) New (left before this system)")
        print("  4) Promote pupil (a leaver)")
        print("  5) Add Year 11 leavers for a year")
        print("  6) E-mail alumni")
        print("  7) Summary by year")
        print("  0) Back")
        choice = _prompt("Select: ")
        if choice in {"0", "", "q"}:
            return
        if choice == "1":
            browse(principal)
        elif choice == "2":
            a = AL.find_by_reference(_prompt("  Ref (AL000001) or admission no.: "))
            if a:
                show(principal, a.alumni_id)
            else:
                print("  Not found.")
        elif choice == "3":
            new(principal)
        elif choice == "4":
            promote(principal)
        elif choice == "5":
            add_leavers(principal)
        elif choice == "6":
            email(principal, _filtered(contactable=True))
        elif choice == "7":
            print()
            for year, n in s.by_year.items():
                print(f"  {year}: {n}")
            print("  By status: " + ", ".join(f"{AL.STATUS_LABELS[k]} {v}"
                                             for k, v in s.by_status.items()))
            _pause()


def _filtered(*, contactable: bool | None = None) -> list[AL.Alumnus]:
    print("\n  Filters (Enter to skip):")
    print("  Year left:")
    year = _pick(AL.leaving_year_choices(), "Year") or None
    print("  Status:")
    status = _pick(list(AL.STATUSES), "Status") or None
    search = _prompt("  Search (name, ref, e-mail, organisation): ") or None
    rows = AL.list_alumni(search=search, status=status, leaving_year=year,
                          contactable=contactable)
    activity_log.record("alumni.list", results=len(rows), year=year, status=status,
                        search=bool(search))
    return rows


def browse(principal: Principal) -> None:
    rows = _filtered()
    _table(rows)
    a = _choose(rows) if rows else None
    if a:
        show(principal, a.alumni_id)


def show(principal: Principal, alumni_id: int) -> None:
    while True:
        a = AL.get_alumnus(alumni_id)
        if a is None:
            return
        activity_log.record("alumni.view", target=f"alumni:{a.alumni_id}")
        link = AL.pupil_link(a)
        print(f"\n── {a.display_name} ({a.alumni_ref}) ──")
        print(f"  Legal name: {a.first_name} {a.last_name}   DOB: {a.date_of_birth or '—'}")
        print(f"  Left: {a.leaving_year}" + (f", Year {a.last_year_group}"
                                             if a.last_year_group else "")
              + (f" on {a.leaving_date}" if a.leaving_date else "")
              + (f"   Adm. no: {a.admission_no}" if a.admission_no else ""))
        if link.post16_destination:
            print(f"  Post-16 (leaving record): {link.post16_destination}")
        for key in ("email", "phone", "town", "current_activity", "organisation",
                    "course_or_role", "notes"):
            value = getattr(a, key)
            if value:
                print(f"  {AL.FIELD_LABELS[key]}: {value}")
        print(f"  Happy to help: {'Yes' if a.can_help else 'No'}")
        print("  Contact consent: " + (f"Yes, {a.consent_date} ({a.consent_source})"
                                       if a.contact_consent else "No"))
        print(f"  Status: {a.status_label}" + (f" - {a.status_reason}"
                                               if a.status_reason else ""))
        if link.note:
            print(f"  ! {link.note}")
        print("\n  E) Edit   S) Set status   M) E-mail   D) Delete   0) Back")
        choice = _prompt("Select: ").lower()
        if choice == "e":
            edit(principal, a)
        elif choice == "s":
            set_status(principal, a)
        elif choice == "m":
            email(principal, [a])
        elif choice == "d":
            if delete(principal, a):
                return
        else:
            return


def _contact_fields(current: AL.Alumnus | None) -> dict:
    out: dict = {}

    def ask(key: str, hint: str = "") -> None:
        value = _ask(AL.FIELD_LABELS[key], getattr(current, key) if current else None,
                     hint=hint)
        if value is not None:
            out[key] = value

    for key in ("email", "phone", "town"):
        ask(key)
    print(f"  {AL.FIELD_LABELS['current_activity']}"
          + (f" [{current.current_activity}]" if current and current.current_activity else "")
          + " (Enter keeps, - clears):")
    picked = _pick(list(AL.ACTIVITIES), "Choice")
    if picked == "-":
        out["current_activity"] = ""
    elif picked:
        out["current_activity"] = picked
    for key in ("organisation", "course_or_role"):
        ask(key)
    helps = _ask("Happy to help the school (y/n)",
                 ("y" if current.can_help else "n") if current else None)
    if helps is not None:
        out["can_help"] = helps
    had = bool(current and current.contact_consent)
    consent = _ask("Agreed to be contacted (y/n)", "y" if had else "n")
    if consent is not None:
        out["contact_consent"] = consent
    if (consent or ("y" if had else "n")).strip().lower() in {"y", "yes"}:
        ask("consent_date", "YYYY-MM-DD")
        if not (current and current.consent_source) or "consent_date" in out:
            print("  How did they agree?")
            src = _pick(list(AL.CONSENT_SOURCES), "Choice")
            if src and src != "-":
                out["consent_source"] = src
    ask("notes")
    return out


def new(principal: Principal, allow_duplicate: bool = False) -> None:
    print("\n── New alumnus (left before this system; * required, '-' clears) ──")
    data: dict = {}
    for key, req, hint in (("first_name", True, ""), ("last_name", True, ""),
                           ("preferred_name", False, ""), ("date_of_birth", False, "YYYY-MM-DD"),
                           ("leaving_year", True, "e.g. 2019/20"),
                           ("last_year_group", False, "7-11")):
        value = _ask(AL.FIELD_LABELS[key], required=req, hint=hint)
        if value is not None:
            data[key] = value
    data.update(_contact_fields(None))
    try:
        a = AL.create_alumnus(data, actor=principal, allow_duplicate=allow_duplicate)
    except AL.DuplicateAlumnus as e:
        print(f"\n  {e}")
        if _yes("  Add anyway?"):
            try:
                a = AL.create_alumnus(data, actor=principal, allow_duplicate=True)
            except _ERRORS as e2:
                _problem(e2)
                _pause()
                return
        else:
            return
    except _ERRORS as e:
        _problem(e)
        _pause()
        return
    print(f"\n  ✓ Added {a.display_name} as {a.alumni_ref}.")
    _pause()


def promote(principal: Principal) -> None:
    rows = AL.leavers_not_alumni(search=_prompt("\n  Search leavers (Enter for all): ") or None)
    if not rows:
        print("\n  No leavers waiting - record a leaver in Enrolment & Leavers first.")
        _pause()
        return
    for i, p in enumerate(rows, 1):
        print(f"  {i:>3}  {p.admission_no:<9} {p.display_name[:26]:<26} Y{p.year_group:<3}"
              f"left {p.leaving_date} ({p.leaving_reason})")
    raw = _prompt("\n  Number to add (Enter to go back): ")
    if not (raw.isdigit() and 1 <= int(raw) <= len(rows)):
        return
    pupil = rows[int(raw) - 1]
    print(f"\n  Contact details for {pupil.display_name} (Enter to skip):")
    extras = {k: v for k, v in _contact_fields(None).items() if v != ""}
    try:
        a = AL.add_from_pupil(pupil.pupil_id, extras, actor=principal)
    except _ERRORS as e:
        _problem(e)
        _pause()
        return
    print(f"\n  ✓ {a.display_name} added as {a.alumni_ref}. Their pupil record is kept.")
    _pause()


def add_leavers(principal: Principal) -> None:
    print("\n  Make alumni of the end of Year 11 leavers of:")
    year = _pick(AL.leaving_year_choices(), "Year", allow_blank=False)
    if not year or year == "-":
        return
    n = len(AL.leavers_not_alumni(academic_year=year, reasons=(EN.END_OF_Y11,)))
    if not n:
        print(f"  No Year 11 leavers from {year} waiting.")
        return
    if not _yes(f"  Add {n} leaver{'s' if n != 1 else ''}? (no one is e-mailed until they "
                "agree)"):
        return
    try:
        added = AL.add_leavers(year, actor=principal)
    except _ERRORS as e:
        _problem(e)
        _pause()
        return
    print(f"  ✓ {len(added)} added.")
    _pause()


def edit(principal: Principal, a: AL.Alumnus) -> None:
    data: dict = {}
    if a.pupil_id is None:
        for key, hint in (("first_name", ""), ("last_name", ""), ("date_of_birth", "YYYY-MM-DD"),
                          ("leaving_year", "e.g. 2019/20"), ("last_year_group", "7-11")):
            value = _ask(AL.FIELD_LABELS[key], str(getattr(a, key) or "") or None, hint=hint)
            if value is not None:
                data[key] = value
    else:
        print("  (Name, date of birth and year left come from the pupil record.)")
    value = _ask(AL.FIELD_LABELS["preferred_name"], a.preferred_name)
    if value is not None:
        data["preferred_name"] = value
    data.update(_contact_fields(a))
    try:
        _a, changed = AL.update_alumnus(a.alumni_id, data, actor=principal)
    except _ERRORS as e:
        _problem(e)
        _pause()
        return
    print("  ✓ Saved." if changed else "  Nothing changed.")


def set_status(principal: Principal, a: AL.Alumnus) -> None:
    print(f"\n  Now: {a.status_label}")
    status = _pick(list(AL.STATUSES), "New status", allow_blank=False)
    if not status or status == "-":
        return
    reason = _prompt("  Reason: ")
    try:
        AL.set_status(a.alumni_id, status, actor=principal, reason=reason)
    except _ERRORS as e:
        _problem(e)
        _pause()
        return
    print("  ✓ Status changed.")


def delete(principal: Principal, a: AL.Alumnus) -> bool:
    print(f"\n  Delete the alumni record for {a.display_name} ({a.alumni_ref})? Their pupil "
          "record, if any, is kept. Use for an erasure request or a record made in error.")
    reason = _prompt("  Reason * (Enter to cancel): ")
    if not reason:
        return False
    try:
        AL.delete_alumnus(a.alumni_id, actor=principal, reason=reason)
    except _ERRORS as e:
        _problem(e)
        _pause()
        return False
    print("  ✓ Deleted.")
    _pause()
    return True


def email(principal: Principal, rows: list[AL.Alumnus]) -> None:
    plan = AL.plan_email([a.alumni_id for a in rows])
    print(f"\n── E-mail alumni ── {len(plan.recipients)} will receive it, "
          f"{len(plan.skipped)} skipped (no consent, no e-mail or not active)")
    if not plan.recipients:
        _pause()
        return
    print("  Placeholders: " + ", ".join("{" + k + "}" for k in AL.PLACEHOLDERS)
          + ". A line saying how to stop these e-mails is added.")
    subject = _prompt("  Subject: ")
    print("  Message (finish with a line containing only '.'):")
    lines = []
    while True:
        line = input()
        if line.strip() == ".":
            break
        lines.append(line)
    if not _yes(f"  Send to {len(plan.recipients)}?"):
        return
    try:
        message_id, sent = AL.send_email(subject, "\n".join(lines),
                                         [a.alumni_id for a in plan.recipients],
                                         actor=principal)
    except _ERRORS as e:
        _problem(e)
        _pause()
        return
    try:
        report = E.deliver(message_id, principal=principal)
        print("  ✓ " + (", ".join(f"{n} {E.STATUS_LABELS[s].lower()}"
                                  for s, n in report.counts.items()) or "saved"))
    except Exception as e:  # noqa: BLE001 - message is saved; retry from Email
        print(f"  Saved, but delivery failed: {e}. Retry it from Email.")
    _pause()
