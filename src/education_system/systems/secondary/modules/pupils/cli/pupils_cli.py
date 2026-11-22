"""Pupil menus for the terminal: directory, search, profile, add, edit, delete.

Same rules as the GUI - they live in :mod:`modules.pupils.domain.pupils`. When editing,
Enter keeps the current value and ``-`` clears an optional field.
"""

from __future__ import annotations

import json
import logging

from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.cli.prompts.prompts import ask as _ask
from education_system.systems.secondary.ui.cli.prompts.prompts import pause as _pause
from education_system.systems.secondary.ui.cli.prompts.prompts import pick as _pick
from education_system.systems.secondary.ui.cli.prompts.prompts import prompt as _prompt
from education_system.systems.secondary.ui.cli.prompts.prompts import yes as _yes

logger = logging.getLogger(__name__)


# ── Listing ──────────────────────────────────────────────────────────

def _print_table(rows: list[P.Pupil]) -> None:
    if not rows:
        print("\n  No pupils found.")
        return
    print(f"\n  {'#':>3}  {'Adm. no':<10} {'Name':<28} {'Yr':>2}  {'Form':<6} "
          f"{'Born':<10}  {'UPN':<13}  Status")
    print("  " + "─" * 92)
    for i, p in enumerate(rows, 1):
        print(f"  {i:>3}  {p.admission_no:<10} {p.display_name[:28]:<28} {p.year_group:>2}  "
              f"{(p.form_group or ''):<6} {p.date_of_birth:<10}  {(p.upn or ''):<13}  "
              f"{p.roll_status_label}")
    print(f"\n  {len(rows)} pupil{'s' if len(rows) != 1 else ''}")


def _choose_from(rows: list[P.Pupil]) -> P.Pupil | None:
    if not rows:
        return None
    choice = _prompt("\n  Number to open (Enter to go back): ")
    if not choice:
        return None
    if choice.isdigit() and 1 <= int(choice) <= len(rows):
        return rows[int(choice) - 1]
    print("  Invalid selection.")
    return None


def directory(principal: Principal) -> None:
    """List pupils, with optional year / form / status filters."""
    print("\n═══ Pupil Directory ═══")
    year = _prompt("  Year group 7-11 (Enter for all): ")
    form = _prompt("  Form group (Enter for all): ")
    status = _prompt("  Status - [o]n roll, [l]eft, [a]ll (Enter = on roll): ").lower()
    roll = {"": "on_roll", "o": "on_roll", "l": "left", "a": None}.get(status[:1], "on_roll")
    try:
        rows = P.list_pupils(year_group=int(year) if year.isdigit() else None,
                             form_group=form or None, roll_status=roll)
    except Exception as e:  # noqa: BLE001
        logger.exception("Pupil list failed")
        activity_log.record("pupil.list", outcome="error", error=type(e).__name__)
        print(f"\n  Could not load pupils: {e}")
        _pause()
        return
    activity_log.record("pupil.list", year=year or "All", form=form or "All",
                        status=roll or "all", results=len(rows))
    _print_table(rows)
    picked = _choose_from(rows)
    if picked:
        profile(principal, picked.pupil_id)


def search(principal: Principal) -> None:
    """Find pupils by name, admission number or UPN (leavers included)."""
    print("\n═══ Search Pupils ═══")
    term = _prompt("  Name, admission no. or UPN: ")
    if not term:
        return
    rows = P.list_pupils(search=term, roll_status=None)
    # Result count only - never the text typed (see activity_log).
    activity_log.record("pupil.search", status="all", results=len(rows))
    _print_table(rows)
    picked = _choose_from(rows)
    if picked:
        profile(principal, picked.pupil_id)


# ── Profile ──────────────────────────────────────────────────────────

def _print_profile(p: P.Pupil, principal: Principal | None = None) -> None:
    legal = " ".join(x for x in (p.legal_first_name, p.middle_names, p.legal_last_name) if x)
    address = ", ".join(x for x in (p.address_line1, p.address_line2, p.town, p.postcode) if x)
    print(f"\n═══ {p.display_name} ({p.admission_no}) ═══")
    rows = [
        ("Legal name", legal),
        ("Preferred name", p.preferred_name or "—"),
        ("Date of birth", p.date_of_birth),
        ("Gender", p.gender),
        ("UPN", p.upn or "Not recorded"),
        ("Year / form", f"Year {p.year_group}" + (f" · {p.form_group}" if p.form_group else "")),
        ("Admission date", p.admission_date),
        ("Status", p.roll_status_label
         + (f" on {p.leaving_date} ({p.leaving_reason})" if p.roll_status == "left" else "")),
        ("Address", address or "—"),
        ("SEN", f"{p.sen_status} – {p.sen_label}"),
        ("Free school meals", "Eligible" if p.fsm_eligible else "Not eligible"),
        ("EAL", "Yes" if p.eal else "No"),
        ("Notes", p.notes or "—"),
        ("Last changed", f"{p.updated_at} by {p.updated_by or '—'}"),
    ]
    for k, v in rows:
        print(f"  {k + ':':<19} {v}")
    warning = P.year_group_warning(p.date_of_birth, p.year_group)
    if warning and p.roll_status == "on_roll":
        print(f"\n  ⚠ {warning}")
    if p.roll_status == "on_roll":
        try:
            from education_system.systems.secondary.modules.curriculum.domain import (
                teaching_groups as TG,
            )
            groups = TG.groups_for_pupil(p.pupil_id)
        except Exception:  # noqa: BLE001 - the profile still shows
            groups = []
        print("\n  Teaching groups:    " + ("; ".join(
            f"{i.subject.code} {i.group.code}" for i in groups) or "none yet"))
    print("  Attendance:         " + _attendance_line(p.pupil_id))
    print("  Homework:           " + _homework_line(p.pupil_id))
    options = _options_line(p.pupil_id)
    if options:
        print("  Options:            " + options)
    clubs = _clubs_line(p.pupil_id)
    if clubs:
        print("  Clubs:              " + clubs)
    library = _library_line(p.pupil_id)
    if library:
        print("  Library:            " + library)
    grades = _gradebook_line(p.pupil_id)
    if grades:
        print("  Gradebook:          " + grades)
    points = _assessment_points_line(p.pupil_id)
    if points:
        print("  Assessment point:   " + points)
    targets = _targets_line(p.pupil_id)
    if targets:
        print("  Targets:            " + targets)
    mocks = _mocks_line(p.pupil_id)
    if mocks:
        print("  Mock exams:         " + mocks)
    entries = _entries_line(p.pupil_id)
    if entries:
        print("  Exam entries:       " + entries)
    results = _results_line(p.pupil_id, principal)
    if results:
        print("  Exam results:       " + results)
    sen = _sen_line(p)
    if sen:
        print("  SEN details:        " + sen)
    gcses = _gcse_line(p.pupil_id)
    if gcses:
        print("  GCSE results:       " + gcses)
    if principal is not None:
        from education_system.systems.secondary.modules.pupils.domain import profile_linked as PL
        flag = PL.safeguarding_flag(p, principal=principal)
        if flag:
            print(f"\n  !! {flag}")
        marks = {"": "", "warn": "! ", "bad": "!! "}
        for title, lines in PL.sections(p, principal=principal):
            print(f"\n  {title}:")
            for text, level in lines:
                print(f"    {marks.get(level, '')}{text}")
    from education_system.systems.secondary.modules.pupils.domain import pupil_accounts
    account = pupil_accounts.get_for_pupil(p.pupil_id)
    if account is None:
        print("\n  School login:       none yet")
    else:
        removed = "" if account.status == "active" else " (removed)"
        print(f"\n  {'Username:':<19} {account.username}{removed}")
        print(f"  {'School e-mail:':<19} {account.school_email}")


def _print_history(pupil_id: int) -> None:
    entries = P.history(pupil_id)
    print("\n  Change history (newest first):")
    if not entries:
        print("   (none)")
    for h in entries:
        try:
            detail = json.loads(h["detail"] or "{}")
        except ValueError:
            detail = {}
        if h["action"] == "create":
            what = "Record created"
        elif h["action"] == "delete":
            what = f"Record deleted: {detail.get('reason', '')}"
        else:
            what = "; ".join(f"{k.replace('_', ' ')}: {c.get('from') or '—'} → "
                             f"{c.get('to') or '—'}" for k, c in sorted(detail.items())
                             if isinstance(c, dict))
            if detail.get("_year_end_rollover"):
                what = f"Year-end rollover to {detail['_year_end_rollover']}: {what}"
        print(f"   {h['at']}  {h['actor']:<12} {what}")


def choose_pupil(prompt: str = "Admission no., UPN or name") -> P.Pupil | None:
    """Ask for a reference and return one pupil (listing matches to pick from)."""
    ref = _prompt(f"\n  {prompt}: ")
    if not ref:
        return None
    pupil = P.find_by_reference(ref)
    if pupil is None:
        rows = P.list_pupils(search=ref, roll_status=None)
        activity_log.record("pupil.search", status="all", results=len(rows))
        if len(rows) == 1:
            pupil = rows[0]
        else:
            _print_table(rows)
            pupil = _choose_from(rows)
    return pupil


def profile(principal: Principal, pupil_id: int | None = None) -> None:
    """Show one pupil, with edit / delete / history actions."""
    if pupil_id is None:
        pupil = choose_pupil()
        if pupil is None:
            return
        pupil_id = pupil.pupil_id
    while True:
        pupil = P.get_pupil(pupil_id)
        if pupil is None:
            activity_log.record("pupil.view", target=f"id:{pupil_id}", outcome="not_found")
            print("\n  This pupil record no longer exists.")
            return
        activity_log.record("pupil.view", target=pupil.admission_no)
        _print_profile(pupil, principal)
        options = ["C) Contacts", "H) Change history"]
        from education_system.systems.secondary.modules.pupils.domain import pupil_accounts
        can_create_login = (principal.can_edit_pupils
                            and pupil_accounts.get_for_pupil(pupil_id) is None)
        if can_create_login:
            options = ["L) Create login"] + options
        if principal.can_edit_pupils:
            options = ["E) Edit", "D) Delete"] + options
        print("\n  " + "   ".join(options) + "   0) Back")
        choice = _prompt("  Select: ").lower()
        if choice in {"0", ""}:
            return
        if choice == "l" and can_create_login:
            create_login(principal, pupil)
            _pause()
        elif choice == "c":
            from education_system.systems.secondary.modules.communication.cli import contacts_cli
            contacts_cli.manage(principal, pupil_id)
        elif choice == "h":
            activity_log.record("pupil.history", target=pupil.admission_no)
            _print_history(pupil_id)
            _pause()
        elif choice == "e" and principal.can_edit_pupils:
            edit(principal, pupil)
        elif choice == "d" and principal.can_edit_pupils:
            if delete(principal, pupil):
                return
        else:
            print("  Invalid selection.")


# ── Add / edit ───────────────────────────────────────────────────────


def _collect(existing: P.Pupil | None) -> dict:
    def cur(name):
        if existing is None:
            return None
        v = getattr(existing, name)
        if isinstance(v, bool):
            return "y" if v else "n"
        return None if v is None else str(v)

    spec = [
        ("legal_first_name", "Legal first name", True, ""),
        ("middle_names", "Middle names", False, ""),
        ("legal_last_name", "Legal last name", True, ""),
        ("preferred_name", "Preferred name", False, ""),
        ("date_of_birth", "Date of birth", True, "YYYY-MM-DD"),
        ("gender", "Gender", True, "/".join(P.GENDERS)),
        ("upn", "UPN", False, "13 characters"),
        ("year_group", "Year group", True, "7-11"),
        ("form_group", "Form group", False, "e.g. 7K"),
        ("admission_date", "Admission date", False, "YYYY-MM-DD, Enter = today"
         if existing is None else "YYYY-MM-DD"),
        ("roll_status", "Status", False, "on_roll/left"),
        ("address_line1", "Address line 1", False, ""),
        ("address_line2", "Address line 2", False, ""),
        ("town", "Town", False, ""),
        ("postcode", "Postcode", False, ""),
        ("sen_status", "SEN", False, "N none, K SEN support, E EHC plan"),
        ("fsm_eligible", "Free school meals eligible", False, "y/n"),
        ("eal", "English as an additional language", False, "y/n"),
        ("notes", "Notes", False, ""),
    ]
    data: dict = {}
    for name, label, required, hint in spec:
        if name == "form_group":
            answer = _ask_form(data, existing)
            if answer is not None:
                data[name] = answer
            continue
        answer = _ask(label, cur(name), required=required and existing is None, hint=hint)
        if answer is not None:
            data[name] = answer
        if name == "roll_status":
            status = data.get("roll_status") or (existing.roll_status if existing else "on_roll")
            if status == "left":
                for lname, llabel, lhint in (
                        ("leaving_date", "Leaving date", "YYYY-MM-DD"),
                        ("leaving_reason", "Leaving reason",
                         " / ".join(P.LEAVING_REASONS))):
                    ans = _ask(llabel, cur(lname), hint=lhint)
                    if ans is not None:
                        data[lname] = ans
    return data


def _attendance_line(pupil_id: int) -> str:
    """This year's attendance for the profile (never stops the profile showing)."""
    try:
        from education_system.systems.secondary.modules.attendance.domain import attendance as AT
        s = AT.pupil_summary(pupil_id)
    except Exception:  # noqa: BLE001
        return "couldn't read"
    if s.attendance_pct is None:
        return "no marks this year"
    return (f"{s.attendance_pct}% this year ({s.possible} sessions; authorised "
            f"{s.authorised}, unauthorised {s.unauthorised}, late {s.late})"
            + (f" - {s.band} absence" if s.band else ""))


def _homework_line(pupil_id: int) -> str:
    """This year's homework for the profile (never stops the profile showing)."""
    try:
        from education_system.systems.secondary.modules.curriculum.domain import homework as HW
        s = HW.pupil_summary(pupil_id)
    except Exception:  # noqa: BLE001
        return "couldn't read"
    if not s.set:
        return "none due yet this year"
    return (f"{s.handed_in} of {s.set} handed in this year"
            + (f" ({s.completion_pct}%)" if s.completion_pct is not None else "")
            + f"; late {s.late}, missing {s.missing}"
            + (f"; average mark {s.average_pct}%" if s.average_pct is not None else ""))


def _options_line(pupil_id: int) -> str | None:
    """The pupil's latest options round, if they've chosen (never stops the profile)."""
    try:
        from education_system.systems.secondary.modules.curriculum.domain import options as OP
        rows = OP.for_pupil(pupil_id)
    except Exception:  # noqa: BLE001
        return "couldn't read"
    if not rows:
        return None
    r, x, alloc = rows[0]
    if alloc:
        return f"{r.name}: " + ", ".join(f"{a.block} {a.code}" for a in alloc)
    return f"{r.name}: chose {x.label}"


def _clubs_line(pupil_id: int) -> str | None:
    """The clubs the pupil is in or waiting for (never stops the profile)."""
    try:
        from education_system.systems.secondary.modules.curriculum.domain import enrichment as EN
        rows = [m for m in EN.for_pupil(pupil_id) if m.status in ("Active", "Waitlisted")]
    except Exception:  # noqa: BLE001
        return "couldn't read"
    return "; ".join(m.club_name + (" (waiting)" if m.status == "Waitlisted" else "")
                     for m in rows) or None


def _library_line(pupil_id: int) -> str | None:
    """Library books out now and reservations (never stops the profile)."""
    try:
        from education_system.systems.secondary.modules.library.domain import library as LB
        info = LB.for_pupil(pupil_id)
    except Exception:  # noqa: BLE001
        return "couldn't read"
    if not info["out"] and not info["holds"]:
        return None
    bits = [x.book_title + (f" (OVERDUE {x.days_overdue}d)" if x.days_overdue
                            else f" (due {x.due_date})") for x in info["out"]]
    bits += [f"reserved {h.book_title}" + (" - ready" if h.status == "Ready" else "")
             for h in info["holds"]]
    return "; ".join(bits)


def _gradebook_line(pupil_id: int) -> str | None:
    """This year's average and latest grade per subject (never stops the profile)."""
    try:
        from education_system.systems.secondary.modules.assessment.domain import gradebook as GB
        rows = GB.pupil_overview(pupil_id)
    except Exception:  # noqa: BLE001
        return "couldn't read"
    return "; ".join(f"{r['subject_code']} "
                     + (f"{r['avg_pct']:g}%" if r["avg_pct"] is not None else "-")
                     + (f" ({r['latest_grade']})" if r["latest_grade"] else "")
                     for r in rows) or None


def _assessment_points_line(pupil_id: int) -> str | None:
    """The latest assessment point's working-at grades (never stops the profile)."""
    try:
        from education_system.systems.secondary.modules.assessment.domain import (
            assessment_points as AP,
        )
        found = AP.for_pupil(pupil_id)
    except Exception:  # noqa: BLE001
        return "couldn't read"
    if not found:
        return None
    pt, rows = found
    return f"{pt.name} ({pt.status.lower()}): " + "; ".join(
        f"{x.subject_code} {x.working_at or '-'}"
        + (f" (att {x.attitude})" if x.attitude else "") for x in rows)


def _targets_line(pupil_id: int) -> str | None:
    """Target grade per subject, with how they're doing (never stops the profile)."""
    try:
        from education_system.systems.secondary.modules.assessment.domain import (
            target_grades as TGR,
        )
        rows = TGR.progress(pupil_id=pupil_id)
    except Exception:  # noqa: BLE001
        return "couldn't read"
    return "; ".join(f"{r['target'].subject_code} {r['target'].target_grade}"
                     + (f" (now {r['current']}, {r['status'].lower()})" if r["current"] else "")
                     for r in rows) or None


def _mocks_line(pupil_id: int) -> str | None:
    """Grades from the pupil's latest mock series (never stops the profile)."""
    try:
        from education_system.systems.secondary.modules.examinations.domain import mock_exams as MX
        rows = MX.results_for_pupil(pupil_id)
        if not rows:
            return None
        s = rows[0][0]
        grades = MX.subject_results(s.series_id, pupil_id=pupil_id)
    except Exception:  # noqa: BLE001
        return "couldn't read"
    return f"{s.name}: " + ", ".join(f"{r['subject_code']} {r['grade'] or '-'}"
                                     for r in grades) + ("" if s.released else " (not released)")


def _entries_line(pupil_id: int) -> str | None:
    """Candidate number and live exam entries (never stops the profile)."""
    try:
        from education_system.systems.secondary.modules.examinations.domain import (
            exam_entries as EE,
        )
        rows = [e for e in EE.entries_for_pupil(pupil_id)
                if e.entry_status in ("Provisional", "Final")]
        c = EE.candidate(pupil_id)
    except Exception:  # noqa: BLE001
        return "couldn't read"
    if not rows and not c:
        return None
    return ((f"candidate {c.candidate_number}; " if c else "")
            + (", ".join(f"{e.subject_code} {e.entry_code}"
                         + ("" if e.entry_status == "Final" else " (prov.)") for e in rows)
               or "no live entries"))


def _results_line(pupil_id: int, principal) -> str | None:
    """Exam results the viewer may see (never stops the profile)."""
    try:
        from education_system.systems.secondary.modules.examinations.domain import (
            exam_results as ER,
        )
        rows = ER.list_results(pupil_id=pupil_id, actor=principal)
    except Exception:  # noqa: BLE001
        return "couldn't read"
    if not rows:
        return None
    return ", ".join(f"{r.subject_code} {r.final_grade or r.status.lower()}"
                     + ("" if ER.released(r.series_id) else " (embargo)") for r in rows)


def _sen_line(pupil: P.Pupil) -> str | None:
    """Needs, plan and exam access (never stops the profile)."""
    if pupil.sen_status == "N":
        return None
    try:
        from education_system.systems.secondary.modules.pupils.domain import sen_details as SEN
        return SEN.summary_line(pupil)
    except Exception:  # noqa: BLE001
        return "couldn't read"


def _gcse_line(pupil_id: int) -> str | None:
    """GCSE grades and the sixth form application stage (never stops the profile)."""
    try:
        from education_system.systems.secondary.modules.examinations.domain import gcse_results as G
        from education_system.systems.secondary.modules.progression.domain import (
            sixth_form_progression as SFP,
        )
        line = G.summary_line(pupil_id)
        app = SFP.application_for(pupil_id)
    except Exception:  # noqa: BLE001
        return "couldn't read"
    if app:
        line = (line + " · " if line else "") + f"sixth form: {app['stage']}"
    return line


def _ask_form(data: dict, existing: P.Pupil | None) -> str | None:
    """Pick the form from those set up for the year (Form Groups). Returns None to keep
    the current form, "" for no form, or the chosen name."""
    from education_system.systems.secondary.modules.curriculum.domain import form_groups as FG
    year = data.get("year_group") or (existing.year_group if existing else None)
    same_year = existing is not None and str(year) == str(existing.year_group)
    current = existing.form_group if existing and same_year else None
    names = FG.choices_for(year, current)
    if not names:
        print(f"  Form group: no forms set up for Year {year or '?'} - set them up in "
              "Form Groups. Left without a form." if year else
              "  Form group: choose the year group first.")
        return "" if existing and existing.form_group and not same_year else None
    print("  Form group:" + "".join(f"  {i}) {n}" for i, n in enumerate(names, 1)))
    while True:
        shown = f" [{current}]" if current else ""
        raw = _prompt(f"  Choose 1-{len(names)}, '-' for no form{shown}: ").upper()
        if raw == "":
            # Moving year: an old form doesn't come with them.
            return None if same_year or existing is None else ""
        if raw == "-":
            return ""
        if raw.isdigit() and 1 <= int(raw) <= len(names):
            return names[int(raw) - 1]
        if raw in names:
            return raw
        print("  Pick a number from the list.")


def _confirm_year_group(data: dict, existing: P.Pupil | None) -> bool:
    dob = data.get("date_of_birth") or (existing.date_of_birth if existing else None)
    year = data.get("year_group") or (existing.year_group if existing else None)
    if not dob or not year or not str(year).isdigit():
        return True
    if existing and "date_of_birth" not in data and "year_group" not in data:
        return True
    warning = P.year_group_warning(dob, int(year))
    return not warning or _yes(f"\n  ⚠ {warning} Save anyway?")


def _collect_family() -> tuple[dict, str]:
    """Add Pupil's parent/carer and medical/care notes (asked the same as in
    the primary school). The contact becomes the pupil's priority-1 contact;
    the notes go on the medical register."""
    from education_system.systems.secondary.modules.pupils.domain import contacts as C
    print("  Parent / carer")
    contact: dict = {}
    contact["full_name"] = _ask("Name", None) or ""
    if contact["full_name"]:
        contact["relationship"] = _pick("Relationship", C.RELATIONSHIPS) or ""
        contact["phone"] = _ask("Phone", None) or ""
        contact["email"] = _ask("E-mail", None, hint="phone or e-mail needed") or ""
    print("  Medical")
    care = _ask("Medical / care notes", None) or ""
    return contact, care


def add(principal: Principal) -> None:
    """Create a pupil record."""
    if not principal.can_edit_pupils:
        print("\n  Your account can view pupils but not change them.")
        return
    print("\n═══ Add Pupil ═══  (* required, '-' leaves a field blank)")
    activity_log.record("pupil.form.open", target="new", mode="add")
    data = _collect(None)
    contact, care = _collect_family()
    if not _confirm_year_group(data, None):
        activity_log.record("pupil.save", target="new", outcome="cancelled_year_group_check")
        print("\n  Not saved.")
        return
    try:
        try:
            pupil, warnings = P.create_pupil_with_family(
                data, actor=principal, contact=contact, medical_notes=care)
        except P.DuplicatePupil as dup:
            if not _yes(f"\n  {dup}\n  Add this as a different pupil anyway?"):
                activity_log.record("pupil.create", target=dup.existing.admission_no,
                                    outcome="cancelled_duplicate")
                print("\n  Not saved.")
                return
            pupil, warnings = P.create_pupil_with_family(
                data, actor=principal, contact=contact, medical_notes=care,
                allow_duplicate=True)
    except P.ValidationError as e:
        print("\n  Not saved - please fix:")
        for problem in e.problems:
            print(f"   • {problem}")
        _pause()
        return
    print(f"\n  ✓ {pupil.display_name} added as {pupil.admission_no}.")
    for warning in warnings:
        print(f"  ⚠ {warning}")
    create_login(principal, pupil)
    _pause()


def create_login(principal: Principal, pupil: P.Pupil) -> None:
    """Create the pupil's login + school e-mail and deliver the welcome e-mail."""
    from education_system.systems.secondary.modules.communication.domain import email_outbox
    from education_system.systems.secondary.modules.pupils.domain import pupil_accounts
    try:
        new = pupil_accounts.create_for_pupil(pupil.pupil_id, actor=principal)
    except Exception as e:  # noqa: BLE001
        print(f"\n  The login could not be created: {e}")
        print("  Open the pupil's profile and choose L) Create login to try again.")
        return
    print("\n  Login created (note the password now - it won't be shown again):")
    print(f"    Username:      {new.account.username}")
    print(f"    Password:      {new.password}")
    print(f"    School e-mail: {new.account.school_email}")
    if new.welcome_error:
        print(f"  The welcome e-mail could not be prepared: {new.welcome_error}")
        return
    try:
        report = email_outbox.deliver(new.welcome_message_id, principal=principal)
        done = ", ".join(f"{n} {email_outbox.STATUS_LABELS[s].lower()}"
                         for s, n in report.counts.items()) or "nothing to deliver"
        print(f"  Welcome e-mail: {done}.")
    except Exception as e:  # noqa: BLE001
        print(f"  The welcome e-mail was saved but delivery failed: {e}")


def edit(principal: Principal, pupil: P.Pupil) -> None:
    print(f"\n═══ Edit {pupil.display_name} ═══  (Enter keeps a value, '-' clears it)")
    activity_log.record("pupil.form.open", target=pupil.admission_no, mode="edit")
    changes = _collect(pupil)
    if not changes:
        activity_log.record("pupil.form.cancel", target=pupil.admission_no)
        print("\n  Nothing changed.")
        return
    if not _confirm_year_group(changes, pupil):
        activity_log.record("pupil.save", target=pupil.admission_no,
                            outcome="cancelled_year_group_check")
        print("\n  Not saved.")
        return
    try:
        _saved, changed = P.update_pupil_detailed(pupil.pupil_id, changes, actor=principal)
    except P.ValidationError as e:
        print("\n  Not saved - please fix:")
        for problem in e.problems:
            print(f"   • {problem}")
        _pause()
        return
    except (P.PermissionDenied, P.NotFound) as e:
        print(f"\n  {e}")
        _pause()
        return
    print("\n  ✓ Saved.")
    if changed:
        _notify_updated(principal, pupil.pupil_id, changed)


def _notify_updated(principal: Principal, pupil_id: int, changed: list[str]) -> None:
    from education_system.systems.secondary.modules.communication.domain import email_outbox
    from education_system.systems.secondary.modules.pupils.domain import pupil_accounts
    message_id, note = pupil_accounts.notify_record_updated(pupil_id, changed,
                                                            actor=principal)
    if message_id is None:
        if note.startswith("the e-mail could not"):
            print(f"  Update e-mail to the pupil: {note}")
        return
    try:
        report = email_outbox.deliver(message_id, principal=principal)
        done = ", ".join(f"{n} {email_outbox.STATUS_LABELS[s].lower()}"
                         for s, n in report.counts.items()) or "nothing to deliver"
        print(f"  Update e-mail to the pupil: {done}.")
    except Exception as e:  # noqa: BLE001
        print(f"  The update e-mail was saved but delivery failed: {e}")


def delete(principal: Principal, pupil: P.Pupil) -> bool:
    """Delete after confirmation and a reason. True if deleted."""
    print(f"\n  Delete the record for {pupil.full_name} ({pupil.admission_no})?")
    print("  Delete is only for records created in error. If the pupil has left,")
    print("  edit the record and set the status to 'left' instead - that keeps their history.")
    if not _yes("  Delete this record?"):
        activity_log.record("pupil.delete", target=pupil.admission_no, outcome="cancelled")
        return False
    reason = _prompt("  Reason for deleting: ")
    try:
        P.delete_pupil(pupil.pupil_id, actor=principal, reason=reason)
    except P.ValidationError as e:
        print(f"\n  Not deleted: {e}")
        return False
    print(f"\n  ✓ The record for {pupil.full_name} was deleted.")
    _pause()
    return True
