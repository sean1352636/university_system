"""Admissions in the terminal. Rules live in :mod:`modules.admissions.domain.admissions`.
When editing, Enter keeps a value and ``-`` clears an optional field."""

from __future__ import annotations

from education_system.systems.secondary.modules.communication.domain import email_outbox as E
from education_system.systems.secondary.modules.admissions.domain import admissions as A
from education_system.systems.secondary.modules.pupils.domain import contacts as C
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.cli.prompts.prompts import ask as _ask
from education_system.systems.secondary.ui.cli.prompts.prompts import pause as _pause
from education_system.systems.secondary.ui.cli.prompts.prompts import prompt as _prompt
from education_system.systems.secondary.ui.cli.prompts.prompts import yes as _yes


def _deliver(principal: Principal, notes: list[str], has_mail: bool) -> None:
    if has_mail:
        try:
            report = E.deliver(principal=principal)
            done = ", ".join(f"{n} {E.STATUS_LABELS[s].lower()}"
                             for s, n in report.counts.items()) or "nothing to deliver"
            print(f"  E-mail: {done}.")
        except Exception as e:  # noqa: BLE001
            print(f"  E-mail delivery failed: {e} (retry from Email)")
    for n in notes:
        if n and not n.startswith("e-mail to parent queued"):
            print(f"  Note: {n}")


def _run(principal: Principal, fn, done: str) -> bool:
    try:
        outcome = fn()
    except (A.ValidationError, A.PermissionDenied, A.NotFound) as e:
        print(f"\n  Not done: {e}")
        return False
    print(f"\n  ✓ {done}")
    _deliver(principal, outcome.notes, bool(outcome.message_ids))
    return True


# ── Menu ─────────────────────────────────────────────────────────────

def menu(principal: Principal) -> None:
    year = A.next_academic_year()
    while True:
        print(f"\n── Admissions ── (year: {year})")
        print("  1) Applications")
        print("  2) New application")
        print("  3) Open an application (by reference)")
        print("  4) Places (admission numbers)")
        print("  5) Allocate places")
        print("  6) Lapse expired offers")
        print("  7) Change year")
        print("  0) Back")
        choice = _prompt("Select: ")
        if choice in {"0", "", "q"}:
            return
        if choice == "1":
            applications(principal, year)
        elif choice == "2":
            new(principal, year)
        elif choice == "3":
            ref = _prompt("  Reference (e.g. APP00012): ")
            app = A.find_by_reference(ref) if ref else None
            if app:
                show(principal, app.application_id)
            elif ref:
                print("  No application with that reference.")
        elif choice == "4":
            places(principal, year)
        elif choice == "5":
            allocate(principal, year)
        elif choice == "6":
            try:
                lapsed = A.lapse_expired_offers(actor=principal)
                print(f"\n  {len(lapsed)} offer(s) lapsed: "
                      + (", ".join(a.reference for a in lapsed) or "none"))
            except A.PermissionDenied as e:
                print(f"\n  {e}")
            _pause()
        elif choice == "7":
            options = A.academic_year_choices()
            print("  " + "   ".join(f"{i}) {y}" for i, y in enumerate(options, 1)))
            pick = _prompt("  Year: ")
            if pick.isdigit() and 1 <= int(pick) <= len(options):
                year = options[int(pick) - 1]
        else:
            print("Invalid selection.")


def _print_table(rows: list[A.Application]) -> None:
    if not rows:
        print("\n  No applications.")
        return
    print(f"\n  {'#':>3}  {'Ref':<9} {'Child':<24} {'Yr':>2}  {'Priority':<32} {'km':>5}  "
          f"{'Received':<10}  Status")
    print("  " + "─" * 104)
    for i, a in enumerate(rows, 1):
        km = "" if a.distance_km is None else f"{a.distance_km:g}"
        pos = A.waiting_position(a)
        status = a.status_label + (f" #{pos}" if pos else "")
        print(f"  {i:>3}  {a.reference:<9} {a.child_name[:24]:<24} {a.year_group:>2}  "
              f"{a.criterion_label[:32]:<32} {km:>5}  {a.received_date:<10}  {status}")


def applications(principal: Principal, year: str) -> None:
    group = _prompt("  Year group (7-11, Enter for all): ")
    status = _prompt("  Status (Enter = open, 'all', or e.g. waiting_list): ").lower()
    search = _prompt("  Search (Enter for none): ")
    try:
        rows = A.list_applications(
            academic_year=year, year_group=int(group) if group.isdigit() else None,
            status=status if status in A.STATUS_LABELS else None, search=search or None,
            open_only=status == "")
    except Exception as e:  # noqa: BLE001
        print(f"  Couldn't load applications: {e}")
        return
    activity_log.record("admission.list", year=year, year_group=group or None,
                        status=status or "open", searched=bool(search) or None,
                        results=len(rows))
    if group.isdigit():
        _print_places(year, int(group))
    _print_table(rows)
    if rows:
        pick = _prompt("\n  Number to open (Enter to go back): ")
        if pick.isdigit() and 1 <= int(pick) <= len(rows):
            show(principal, rows[int(pick) - 1].application_id)


def _print_places(year: str, group: int) -> None:
    p = A.places(year, group)
    if p.pan is None:
        print(f"\n  Year {group} {year}: no admission number set (use Places)")
    else:
        print(f"\n  Year {group} {year}: admission number {p.pan} · {p.offered} offered · "
              f"{p.accepted} accepted · {p.on_roll} on roll · {p.available} available"
              + (f" · over by {p.over_by}" if p.over_by else ""))


# ── One application ──────────────────────────────────────────────────

def _print_app(a: A.Application) -> None:
    print(f"\n═══ {a.reference}: {a.child_name} ═══")
    status = a.status_label
    if a.status == "offered" and a.offer_expires:
        status += f" (reply by {a.offer_expires})"
    pos = A.waiting_position(a)
    if pos:
        status += f" (position {pos})"
    rows = [
        ("Status", status + (f" · {a.decision_note}" if a.decision_note else "")),
        ("Place", f"Year {a.year_group} {a.academic_year} · {a.route_label}"),
        ("Priority", a.criterion_label),
        ("Legal name", " ".join(x for x in (a.legal_first_name, a.middle_names,
                                             a.legal_last_name) if x)),
        ("Preferred name", a.preferred_name or "—"),
        ("Date of birth", a.date_of_birth), ("Gender", a.gender), ("UPN", a.upn or "—"),
        ("Current school", a.current_school or "—"),
        ("Address", ", ".join(x for x in (a.address_line1, a.address_line2, a.town,
                                          a.postcode) if x) or "—"),
        ("Distance", "—" if a.distance_km is None else f"{a.distance_km:g} km"),
        ("SEN", f"{a.sen_status} - {P.SEN_STATUSES.get(a.sen_status, '')}"),
        ("EHC plan names us", "Yes" if a.ehcp_names_school else "No"),
        ("Looked after", A.LOOKED_AFTER.get(a.looked_after, a.looked_after)),
        ("Sibling on roll", a.sibling_admission_no or "—"),
        ("Parent/carer", f"{a.parent_name} ({a.parent_relationship})"),
        ("Parent e-mail", a.parent_email or "—"), ("Parent phone", a.parent_phone or "—"),
        ("Received", a.received_date), ("Notes", a.notes or "—"),
    ]
    for k, v in rows:
        print(f"  {k + ':':<19} {v}")
    warning = A.year_group_warning(a)
    if warning:
        print(f"\n  ⚠ {warning}")


def _print_history(application_id: int) -> None:
    from education_system.systems.secondary.modules.admissions.gui.admissions_views import (
        describe_event,
    )
    print("\n  History:")
    for h in A.history(application_id):
        note = f" - {h['note']}" if h["note"] else ""
        print(f"   {h['at']}  {h['actor']:<12} {describe_event(h)}{note}")


def show(principal: Principal, application_id: int) -> None:
    while True:
        app = A.get_application(application_id)
        if app is None:
            print("\n  This application no longer exists.")
            return
        activity_log.record("admission.view", target=app.reference)
        _print_app(app)
        nxt = app.next_statuses()
        options: list[tuple[str, str]] = []
        if "offered" in nxt and app.status != "appeal_lodged":
            options.append(("o", "Offer place"))
        if "waiting_list" in nxt:
            options.append(("w", "Waiting list"))
        if "refused" in nxt:
            options.append(("r", "Refuse"))
        if "accepted" in nxt:
            options.append(("a", "Parent accepted"))
        if "declined" in nxt:
            options.append(("d", "Parent declined"))
        if "appeal_lodged" in nxt:
            options.append(("p", "Appeal lodged"))
        if app.status == "appeal_lodged":
            options += [("u", "Appeal upheld"), ("x", "Appeal dismissed")]
        if app.status == "accepted":
            options.append(("m", "Admit"))
        if app.is_open:
            options.append(("e", "Edit"))
        if "withdrawn" in nxt:
            options.append(("t", "Withdraw"))
        options.append(("h", "History"))
        print("\n  " + "   ".join(f"{k.upper()}) {label}" for k, label in options)
              + "   0) Back")
        choice = _prompt("  Select: ").lower()
        if choice in {"0", ""}:
            return
        if choice not in {k for k, _l in options}:
            print("  Invalid selection.")
            continue
        aid = app.application_id
        if choice == "o":
            _run(principal, lambda: A.offer(aid, actor=principal), "Place offered.")
        elif choice == "w":
            _run(principal, lambda: A.put_on_waiting_list(aid, actor=principal),
                 "Put on the waiting list.")
        elif choice == "r":
            reason = _prompt("  Reason (the parent is told this): ")
            if reason:
                _run(principal, lambda: A.refuse(aid, actor=principal, reason=reason),
                     "Place refused.")
        elif choice == "a":
            _run(principal, lambda: A.record_acceptance(aid, actor=principal),
                 "Acceptance recorded.")
        elif choice == "d" and _yes("  Record that the parent declined?"):
            _run(principal, lambda: A.record_decline(aid, actor=principal),
                 "Decline recorded.")
        elif choice == "p":
            note = _prompt("  Note (optional): ")
            _run(principal, lambda: A.lodge_appeal(aid, actor=principal, note=note),
                 "Appeal recorded.")
        elif choice in {"u", "x"}:
            upheld = choice == "u"
            if _yes(f"  Record that the appeal was {'upheld' if upheld else 'dismissed'}?"):
                _run(principal, lambda: A.decide_appeal(aid, upheld=upheld, actor=principal),
                     "Appeal outcome recorded.")
        elif choice == "m":
            admit(principal, app)
        elif choice == "e":
            edit(principal, app)
        elif choice == "t":
            reason = _prompt("  Reason for withdrawing: ")
            if reason:
                _run(principal, lambda: A.withdraw(aid, actor=principal, reason=reason),
                     "Application withdrawn.")
        elif choice == "h":
            _print_history(aid)
            _pause()


def admit(principal: Principal, app: A.Application) -> None:
    import datetime as _dt
    date = _prompt(f"  First day (YYYY-MM-DD, Enter = {_dt.date.today().isoformat()}): ")
    from education_system.systems.secondary.modules.curriculum.domain import form_groups as FG
    forms = FG.choices_for(app.year_group)
    form = ""
    if not forms:
        print(f"  No forms set up for Year {app.year_group} yet (see Form Groups) - "
              "admitted without a form.")
    else:
        print("  Form group:" + "".join(f"  {i}) {n}" for i, n in enumerate(forms, 1)))
        while True:
            raw = _prompt(f"  Choose 1-{len(forms)} (Enter to leave blank): ").upper()
            if not raw or raw in forms:
                form = raw
                break
            if raw.isdigit() and 1 <= int(raw) <= len(forms):
                form = forms[int(raw) - 1]
                break
            print("  Pick a number from the list.")
    allow = False
    while True:
        try:
            outcome = A.admit(app.application_id, actor=principal, admission_date=date or None,
                              form_group=form or None, allow_duplicate=allow)
            break
        except P.DuplicatePupil as dup:
            if allow or not _yes(f"\n  {dup}\n  Admit as a different pupil anyway?"):
                return
            allow = True
        except (A.ValidationError, A.PermissionDenied, A.NotFound) as e:
            print(f"\n  Not admitted: {e}")
            return
    pupil = outcome.pupil
    assert pupil is not None
    print(f"\n  ✓ {pupil.display_name} is now on roll as {pupil.admission_no}.")
    if outcome.login is not None:
        print("  Login created (note the password now - it won't be shown again):")
        print(f"    Username:      {outcome.login.account.username}")
        print(f"    Password:      {outcome.login.password}")
        print(f"    School e-mail: {outcome.login.account.school_email}")
    _deliver(principal, outcome.notes, bool(outcome.message_ids))
    _pause()


# ── Form ─────────────────────────────────────────────────────────────

_SPEC = (
    ("route", "Route", True, "normal_round / in_year"),
    ("academic_year", "Academic year", True, "e.g. 2027/28"),
    ("year_group", "Year group", True, "7-11"),
    ("legal_first_name", "Legal first name", True, ""),
    ("middle_names", "Middle names", False, ""),
    ("legal_last_name", "Legal last name", True, ""),
    ("preferred_name", "Preferred name", False, ""),
    ("date_of_birth", "Date of birth", True, "YYYY-MM-DD"),
    ("gender", "Gender", True, "/".join(P.GENDERS)),
    ("upn", "UPN", False, "13 characters"),
    ("current_school", "Current school", False, ""),
    ("address_line1", "Address line 1", False, ""),
    ("address_line2", "Address line 2", False, ""),
    ("town", "Town", False, ""),
    ("postcode", "Postcode", False, ""),
    ("distance_km", "Distance to school (km)", False, ""),
    ("sen_status", "SEN", False, "N none, K SEN support, E EHC plan"),
    ("ehcp_names_school", "EHC plan names this school", False, "y/n"),
    ("looked_after", "Looked after", False, "no / current / previous"),
    ("sibling_admission_no", "Sibling on roll (admission no.)", False, ""),
    ("parent_name", "Parent/carer name", True, ""),
    ("parent_relationship", "Relationship", True, "/".join(C.RELATIONSHIPS)),
    ("parent_email", "Parent e-mail", False, ""),
    ("parent_phone", "Parent phone", False, ""),
    ("received_date", "Date received", False, "YYYY-MM-DD, Enter = today"),
    ("notes", "Notes", False, ""),
)


def _collect(existing: A.Application | None, defaults: dict) -> dict:
    data: dict = {}
    for name, label, required, hint in _SPEC:
        if existing is not None:
            v = getattr(existing, name)
            current = ("y" if v else "n") if isinstance(v, bool) else \
                (None if v is None else str(v))
        else:
            current = None if defaults.get(name) is None else str(defaults[name])
        answer = _ask(label, current, required=required and existing is None, hint=hint)
        if answer is not None:
            data[name] = answer
        elif existing is None and current is not None:
            data[name] = current
    return data


def new(principal: Principal, year: str) -> None:
    if not principal.can_open(A.MENU_LABEL):
        print(f"\n  {principal.denied_message(A.MENU_LABEL)}")
        return
    print("\n═══ New application ═══  (* required)")
    activity_log.record("admission.form.open", target="new", mode="add")
    data = _collect(None, {"route": "normal_round", "academic_year": year, "year_group": 7})
    warn = A.year_group_warning(data) if data.get("date_of_birth") else None
    if warn and not _yes(f"\n  ⚠ {warn}\n  Save anyway?"):
        activity_log.record("admission.form.cancel", target="new")
        return
    allow = False
    while True:
        try:
            outcome = A.create_application(data, actor=principal, allow_duplicate=allow)
            break
        except A.DuplicateApplication as dup:
            if allow or not _yes(f"\n  {dup}\n  Record it as a separate application?"):
                return
            allow = True
        except A.ValidationError as e:
            print("\n  Not saved - please fix:")
            for problem in e.problems:
                print(f"   • {problem}")
            _pause()
            return
        except (A.PermissionDenied, A.NotFound) as e:
            print(f"\n  {e}")
            return
    print(f"\n  ✓ Application {outcome.application.reference} recorded.")
    _deliver(principal, outcome.notes, bool(outcome.message_ids))
    _pause()


def edit(principal: Principal, app: A.Application) -> None:
    print(f"\n═══ Edit {app.reference} ═══  (Enter keeps a value, '-' clears it)")
    activity_log.record("admission.form.open", target=app.reference, mode="edit")
    changes = _collect(app, {})
    if not changes:
        activity_log.record("admission.form.cancel", target=app.reference)
        print("  Nothing changed.")
        return
    try:
        _saved, changed = A.update_application(app.application_id, changes, actor=principal)
    except (A.ValidationError, A.PermissionDenied, A.NotFound) as e:
        print(f"\n  Not saved: {e}")
        _pause()
        return
    print("\n  ✓ Saved." if changed else "\n  Nothing changed.")


# ── Places and allocation ─────────────────────────────────────────────

def places(principal: Principal, year: str) -> None:
    activity_log.record("admission.places.open", target=year)
    print(f"\n  Admission numbers for {year}:")
    for yg in P.YEAR_GROUPS:
        p = A.places(year, yg)
        print(f"   Year {yg}: {'not set' if p.pan is None else p.pan}  "
              f"(used {p.used}, available {'—' if p.available is None else p.available})")
    if not _yes("\n  Change any?"):
        return
    for yg in P.YEAR_GROUPS:
        current = A.get_pan(year, yg)
        value = _prompt(f"   Year {yg} [{'' if current is None else current}]: ")
        if value:
            try:
                A.set_pan(year, yg, value, actor=principal)  # type: ignore[arg-type]
            except (A.ValidationError, A.PermissionDenied) as e:
                print(f"   Not saved: {e}")


def allocate(principal: Principal, year: str) -> None:
    group = _prompt("  Year group to allocate (7-11): ")
    if not group.isdigit() or int(group) not in P.YEAR_GROUPS:
        print("  Invalid year group.")
        return
    yg = int(group)
    _print_places(year, yg)
    if A.get_pan(year, yg) is None:
        return
    offer_list, wait_list = A.allocation_preview(year, yg)
    if not offer_list and not wait_list:
        print("  No received or waiting applications.")
        return
    print(f"\n  Would offer {len(offer_list)}:")
    for a in offer_list:
        print(f"    {a.reference}  {a.child_name} - {a.criterion_label}")
    print(f"  Waiting list: {len(wait_list)}")
    if not _yes("\n  Allocate now? Parents will be e-mailed."):
        activity_log.record("admission.allocate", target=f"{year} Y{yg}", outcome="cancelled")
        return
    try:
        result = A.allocate(year, yg, actor=principal)
    except (A.ValidationError, A.PermissionDenied) as e:
        print(f"\n  Not done: {e}")
        return
    print(f"\n  ✓ {len(result.offered)} offered, {len(result.waiting)} on the waiting list.")
    _deliver(principal, result.notes, bool(result.message_ids))
    _pause()
