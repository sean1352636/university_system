"""CLI flows for Sixth Form Student CRUD.

Mirrors the GUI panels in `student_views`: add, directory list, search,
view profile, edit, delete. Each prompt swallows EOF / Ctrl-C and
returns the user to the calling submenu — never crashes the launcher.

Wired in from `cli_main.py` under the "Student Management" category.
"""

from __future__ import annotations

import datetime as _dt
import logging
from typing import Any, Callable
from education_system.systems.sixth_form.domain.learners.students import students as data
from education_system.systems.sixth_form.domain.learners.students import directory
from education_system.systems.sixth_form.domain.learners.students import student_profile
from education_system.systems.sixth_form.domain.learners.students import new_learner
from education_system.systems.sixth_form.domain.governance.user_management import access
from education_system.systems.sixth_form.domain.admissions.enrolments import enrolments as enrolments_data
from education_system.systems.sixth_form.domain.academics.subjects import subjects as subjects_data
from education_system.systems.sixth_form.domain.learners.students.students import (
    A_LEVEL_SUBJECTS,
    Student,
    ValidationError,
)


def _active_subjects() -> list[str]:
    try:
        names = subjects_data.get_active_names()
        return names or list(A_LEVEL_SUBJECTS)
    except Exception:
        logger.exception("Falling back to seed subject list")
        return list(A_LEVEL_SUBJECTS)

logger = logging.getLogger(__name__)


# ── Prompt helpers ───────────────────────────────────────────────────

class _UserAbort(Exception):
    """Raised when the user hits Ctrl-C or types ``cancel`` at a prompt."""


def _input(prompt: str, *, default: str = "", allow_empty: bool = True) -> str:
    """Prompt with a default value and graceful EOF / Ctrl-C handling.

    Typing ``cancel`` at any prompt raises `_UserAbort` so callers can
    bail out of the whole flow cleanly.
    """
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


def _input_date(prompt: str, *, default: str = "") -> str:
    """Prompt for an optional ``YYYY-MM-DD`` date, re-asking on a typo.

    Validated here rather than left to `students._validate_payload`
    because `add_student` discards the whole form when the domain layer
    rejects it — a mistyped date would cost the user every other answer
    they had just given.
    """
    import datetime as _dt

    while True:
        raw = _input(prompt, default=default)
        if not raw:
            return ""
        try:
            _dt.date.fromisoformat(raw)
        except ValueError:
            print("    Enter the date as YYYY-MM-DD (e.g. 2008-03-14).")
            continue
        return raw


def _input_choice(prompt: str, choices: tuple[str, ...], *,
                  default: str = "") -> str:
    """Optional value from a fixed list, re-asked on a typo (the domain
    layer would otherwise reject the whole form). ``-`` clears it."""
    while True:
        raw = _input(f"{prompt} ({'/'.join(choices)}; - to clear)",
                     default=default)
        if raw in ("", "-"):
            return ""
        match = next((c for c in choices if c.lower() == raw.lower()), None)
        if match:
            return match
        print(f"    Choose one of: {', '.join(choices)}")


def _pause() -> None:
    try:
        input("\n  Press Enter to continue...")
    except (EOFError, KeyboardInterrupt):
        pass


def _may_manage() -> bool:
    return access.current().can(access.STUDENTS_MANAGE)


def _manage_ok() -> bool:
    """Add / edit / delete / status need ``students.manage``; the directory
    itself only ``students.view``, so a teacher can reach these actions."""
    if _may_manage():
        return True
    print("\n  ✗ Your account can view students but not change their records.")
    _pause()
    return False


def _pick(prompt: str, options: list[str], default: str = "") -> str:
    """Pick one of *options* by number; blank keeps *default*."""
    for i, o in enumerate(options, 1):
        print(f"    {'*' if o == default else ' '}{i:>2}) {o}")
    while True:
        raw = _input(f"{prompt} (#1..{len(options)})", default=default)
        if raw == default or raw in options:
            return raw
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return options[int(raw) - 1]
        print("    Enter one of the numbers shown.")


#: Suggested ILR withdrawal reason for a leaving reason (still asked).
_ILR_FOR_LEAVING = {"Excluded": "46", "Health / Personal": "3", "Other": "97"}


def _pick_ilr_reason(leaving_reason: str | None = None) -> str:
    """The ILR withdrawal-reason code used for any enrolment this leaving
    withdraws (required; a Year 13 leaving in the summer term is completed
    instead)."""
    labels = [f"{code} — {label}" for code, label in enrolments_data.WITHDRAWAL_REASONS]
    want = _ILR_FOR_LEAVING.get(leaving_reason or "")
    default = next((lb for lb in labels if lb.split(" — ")[0] == want), "")
    print("  ILR withdrawal reason (for the enrolments this closes):")
    for i, o in enumerate(labels, 1):
        print(f"    {'*' if o == default else ' '}{i:>2}) {o}")
    while True:
        raw = _input(f"ILR reason (#1..{len(labels)})", default=default)
        if raw == default and raw:
            return raw.split(" — ")[0]
        if raw.isdigit() and 1 <= int(raw) <= len(labels):
            return labels[int(raw) - 1].split(" — ")[0]
        print("    An ILR withdrawal reason is required — enter one of the "
              "numbers shown.")


def _print_enrolments(student_id: str) -> None:
    """The learner's enrolments, newest first (read-only)."""
    try:
        rows = enrolments_data.list_for_student(student_id)
    except Exception as e:  # noqa: BLE001 — shown, the profile still opens
        logger.exception("Could not list enrolments for %s", student_id)
        print(f"    Enrolments: ✗ {e}")
        return
    print("    Enrolments:")
    for e in rows:
        extra = ""
        if e.status == "Withdrawn":
            extra = (f" — withdrawn {e.withdrawal_date or '?'}, "
                     f"{e.withdrawal_reason_label or 'no reason'}")
        elif e.status == "Completed" and e.completed_at:
            extra = f" — completed {e.completed_at}"
        print(f"      #{e.enrolment_id:<5} {e.academic_year} Year {e.year_group}"
              f"  {e.tutor_group or '—':<6} {e.status}{extra}")
    if not rows:
        print("      (none)")
    try:
        from education_system.systems.sixth_form.domain.admissions.enrolments import (
            leaver_effects,
        )
        effects = leaver_effects.effects_for(student_id)
    except Exception as e:  # noqa: BLE001 — shown, the profile still opens
        logger.exception("Could not read leaver effects for %s", student_id)
        print(f"    Leaver effects: ✗ {e}")
        return
    if effects:
        print("    Leaver effects (what leaving changed; newest first):")
        for r in effects[:10]:
            back = (f"  — returned {r['returned_at'][:10]}"
                    if r.get("returned_at") else "")
            print(f"      {r['left_on']}  {r['area']:<12} "
                  f"{r.get('label') or r.get('ref') or ''}: {r['action']}{back}")
        if len(effects) > 10:
            print(f"      … {len(effects) - 10} more")


def _offer_enrolment_reinstate(student_ids: list[str]) -> None:
    """After putting Left learners back on roll: offer to reinstate this
    year's withdrawn enrolment too (reopens the aims the withdrawal ended)."""
    if not enrolments_data.can_write():
        return
    year = enrolments_data.current_academic_year()
    found = [e for sid in student_ids for e in enrolments_data.list_for_student(sid)
             if e.academic_year == year and e.status == "Withdrawn"]
    if not found:
        return
    print(f"\n  Withdrawn {year} enrolment(s):")
    for e in found:
        print(f"    #{e.enrolment_id} {e.student_id} Year {e.year_group} — "
              f"withdrawn {e.withdrawal_date or '?'}, "
              f"{e.withdrawal_reason_label or 'no reason'}")
    try:
        if not _input("Reinstate " + ("it" if len(found) == 1 else "them")
                      + " too? (y/n)", default="y").lower().startswith("y"):
            return
        reason = _input("Reason (required)", default="Learner back on roll",
                        allow_empty=False)
    except _UserAbort:
        print("  Cancelled.")
        return
    for e in found:
        try:
            res = enrolments_data.reinstate_enrolment(e.enrolment_id, reason=reason,
                                                      reinstate_student=False)
        except (enrolments_data.ValidationError, access.AccessDenied) as exc:
            print(f"  ✗ #{e.enrolment_id}: {exc}")
            continue
        print(f"  ✓ #{e.enrolment_id} reinstated — {len(res.aims_reopened)} "
              "learning aim(s) reopened")
        for p in res.aim_problems:
            print(f"    ✗ aim not reopened: {p}")
        for n in res.student_notes:
            print(f"    • {n}")


def _enrol_flow(student_id: str) -> None:
    from education_system.systems.sixth_form.interfaces.cli.admissions.enrolments import (
        enrolment_workflows_cli,
    )
    enrolment_workflows_cli.enrol_from_student_profile(student_id)


def _pick_subject(slot: int, existing: str | None = None) -> str:
    """Render the A-Level subject list and let the user pick one by number."""
    choices = _active_subjects()
    print(f"\n  A-Level subject {slot}:")
    for i, subj in enumerate(choices, 1):
        marker = " *" if subj == existing else "  "
        print(f"    {marker}{i:>2}) {subj}")
    while True:
        raw = _input(f"  Pick #1..{len(choices)} (0 = none)",
                     default=existing or "")
        if existing and raw == existing:
            return existing
        if raw == "0":
            # Slots mirror the first three active A-level aims; a learner
            # on a BTEC / T Level programme may have fewer than three.
            return ""
        if not raw.isdigit():
            print("    Enter a number (or 'cancel' to abort).")
            continue
        n = int(raw)
        if not (1 <= n <= len(choices)):
            print(f"    Out of range (1..{len(choices)}).")
            continue
        return choices[n - 1]


# ── Form (add + edit) ────────────────────────────────────────────────

def _collect_form(existing: Student | None) -> dict[str, Any]:
    """Prompt for every field, pre-filling from `existing` if provided."""
    is_edit = existing is not None
    print()
    print("  ── Identity ──")
    payload: dict[str, Any] = {
        "first_name":  _input("First name", default=(existing.first_name if is_edit else ""), allow_empty=False),
        "middle_name": _input("Middle name (optional)",
                              default=(existing.middle_name if is_edit else "")),
        "last_name":   _input("Last name", default=(existing.last_name if is_edit else ""), allow_empty=False),
    }
    # Title and gender: the GUI asks for both (the university's UCAS import
    # pre-fills from them); the terminal never did. Optional — "-" clears.
    payload["title"] = _input_choice(
        "Title", data.TITLES, default=(existing.title or "" if is_edit else ""))
    payload["gender"] = _input_choice(
        "Gender", student_profile.GENDER_OPTIONS,
        default=(student_profile.gender_label(existing.gender) if is_edit else ""))
    # Date of birth. The GUI form has had this since the handover gate
    # landed; the CLI did not, so every student added from the terminal
    # arrived without one and could never be handed over to a university
    # — the cross-system identity service anchors a person on name + date
    # of birth. Optional at this prompt because the column is nullable and
    # a member of staff enrolling from a paper form may not have it yet.
    payload["date_of_birth"] = _input_date(
        "Date of birth (YYYY-MM-DD)",
        default=(existing.date_of_birth or "" if is_edit else ""))

    print("\n  ── Contact ──")
    payload["phone"] = _input("Phone number",
                              default=(existing.phone if is_edit else ""))
    payload["personal_email"] = _input(
        "Personal email (optional)",
        default=(existing.personal_email or "" if is_edit else ""))

    print("\n  ── Emergency contact (name and phone, or leave all blank) ──")
    try:
        relation = student_profile.normalise_relationship(
            existing.emergency_contact_relation if is_edit else "") or ""
    except ValidationError:
        relation = ""
    if relation not in student_profile.EMERGENCY_RELATIONSHIPS:
        relation = ""  # legacy free text: pick again from the list
    contact = {
        "emergency_contact_name": (existing.emergency_contact_name or "") if is_edit else "",
        "emergency_contact_phone": (existing.emergency_contact_phone or "") if is_edit else "",
        "emergency_contact_relation": relation,
    }
    while True:
        contact["emergency_contact_name"] = _input(
            "Name", default=contact["emergency_contact_name"])
        contact["emergency_contact_phone"] = _input(
            "Phone", default=contact["emergency_contact_phone"])
        contact["emergency_contact_relation"] = _input_choice(
            "Relationship", student_profile.EMERGENCY_RELATIONSHIPS,
            default=contact["emergency_contact_relation"])
        try:
            student_profile.check_emergency_contact(contact)
            break
        except ValidationError as e:
            print(f"    {e}")
    payload.update(contact)

    print("\n  ── A-Level subjects (up to three; other qualifications under "
          "Study Programme) ──")
    payload["subject_1"] = _pick_subject(1, existing.subject_1 if is_edit else None)
    payload["subject_2"] = _pick_subject(2, existing.subject_2 if is_edit else None)
    payload["subject_3"] = _pick_subject(3, existing.subject_3 if is_edit else None)

    def cur(key: str) -> str:
        return (getattr(existing, key, None) or "") if is_edit else ""

    print("\n  ── Personal details (optional; - clears) ──")
    for key, label in (("preferred_name", "Preferred name"),
                       ("pronouns", "Pronouns"),
                       ("nationality", "Nationality"),
                       ("first_language", "First language")):
        value = _input(label, default=cur(key))
        payload[key] = "" if value == "-" else value
    print("  Ethnicity:")
    labels = ["(not recorded)", *(label for _c, label in student_profile.ETHNICITIES)]
    picked = _pick("Ethnicity", labels,
                   default=(existing.ethnicity_label or "(not recorded)")
                   if is_edit else "(not recorded)")
    payload["ethnicity"] = "" if picked == "(not recorded)" else picked

    print("\n  ── Home address (- clears) ──")
    lines = (student_profile.address_parts(existing) if is_edit else ("", "", ""))
    for key, label, current in zip(student_profile.ADDRESS_LINE_FIELDS,
                                   ("Address line 1", "Address line 2", "Town"), lines):
        value = _input(label, default=current)
        payload[key] = "" if value == "-" else value
    postcode = _input("Postcode", default=cur("postcode"))
    payload["postcode"] = "" if postcode == "-" else postcode

    print("\n  ── Previous education & identifiers (- clears) ──")
    school = _input("Previous school", default=cur("previous_school"))
    payload["previous_school"] = "" if school == "-" else school
    upn = _input("UPN", default=(data.get_upn(existing.student_id) or "")
                 if is_edit else "")
    payload["upn"] = "" if upn == "-" else upn
    for key, label in (("uln", "ULN"), ("uci", "UCI"),
                       ("candidate_number", "Candidate number")):
        value = _input(label, default=cur(key))
        payload[key] = "" if value == "-" else value
    payload["start_date"] = _input_date(
        "Start date (YYYY-MM-DD)",
        default=cur("start_date") or ("" if is_edit else _dt.date.today().isoformat()))

    print("\n  ── Needs, medical & notes ──")
    if is_edit:
        print("    (SEND and medical details are kept under SEND and Medical Records)")
    else:
        # Sent to the SEND register and the medical profile (new_learner).
        payload["has_lldd"] = _input(
            "Learning difficulty or disability (LLDD)? (y/n)", default="n"
        ).lower().startswith("y")
        payload["has_ehcp"] = _input("Has an EHC Plan? (y/n)", default="n").lower().startswith("y")
        payload["send_details"] = _input("SEND details (optional)")
        payload["medical_notes"] = _input("Medical notes (optional)")
    notes = _input("Notes (- clears)", default=cur("notes").replace("\n", " "))
    payload["notes"] = "" if notes == "-" else notes
    return payload


_IDENTIFIER_KEYS = ("uln", "uci", "candidate_number")


def _split_identifiers(payload: dict[str, Any],
                       existing: Student | None) -> dict[str, str]:
    """Take the ULN / UCI / candidate number out of *payload* (they are
    saved with set_identifiers) and check them before anything is written."""
    from education_system.systems.sixth_form.domain.academics.qualifications import (
        identifiers,
    )
    checks = {"uln": identifiers.validate_uln, "uci": identifiers.validate_uci,
              "candidate_number": identifiers.validate_candidate_number}
    out: dict[str, str] = {}
    for key in _IDENTIFIER_KEYS:
        value = (payload.pop(key, "") or "").strip()
        if value == ((getattr(existing, key, None) or "") if existing else ""):
            continue
        if value:
            try:
                checks[key](value)
            except ValueError as e:
                raise ValidationError(str(e)) from None
        out[key] = value
    return out


def _save_identifiers(student_id: str, ids: dict[str, str]) -> None:
    if not ids:
        return
    try:
        data.set_identifiers(student_id, **ids)
    except ValidationError as e:
        print(f"  ✗ Record saved, but not the identifiers: {e}")


def add_student() -> None:
    print("\n═══ Add Student ═══")
    if not _manage_ok():
        return
    print("  (type 'cancel' at any prompt to abort)\n")
    try:
        payload = _collect_form(None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        ids = _split_identifiers(payload, None)
        try:
            added = new_learner.add_learner(payload)
        except data.PossibleDuplicate as dup:
            print("\n  ! These students already on file look like the same person:")
            for m in dup.matches[:8]:
                print(f"      {m.student_id}  {m.full_name}  born "
                      f"{m.date_of_birth or '?'}  ({m.status})")
            try:
                yes = _input("Create a new record anyway? (y/n)", default="n")
            except _UserAbort:
                yes = "n"
            if not yes.lower().startswith("y"):
                print("\n  Not created. Open the existing record instead.")
                _pause()
                return
            added = new_learner.add_learner(payload, allow_duplicate=True)
        student = added.student
        _save_identifiers(student.student_id, ids)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    except Exception as e:
        logger.exception("CLI create_student failed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
        return

    print()
    print("  ✓ Student created")
    print(f"      Student ID : {student.student_id}")
    print(f"      Name       : {student.full_name}")
    print(f"      Email      : {student.email}")
    print()
    print("  Login credentials (shared auth):")
    print(f"      Username   : {student.student_id}")
    print(f"      Temporary password : {added.password}")
    print("  Note the password now; it won't be shown again. It is also in the")
    print(f"  welcome e-mail to {student.personal_email or student.email}.")
    for line in added.needs:
        print(f"  {line}")
    _pause()


def edit_student(student_id: str | None = None) -> None:
    print("\n═══ Edit Student ═══")
    if not _manage_ok():
        return
    try:
        sid = student_id or _input("Student ID", allow_empty=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    existing = data.get_student(sid)
    if existing is None:
        print(f"\n  ✗ No student with id {sid}")
        _pause()
        return
    print(f"\n  Editing {existing.student_id} — {existing.full_name}")
    print("  (Enter to keep the current value; 'cancel' to abort)\n")
    try:
        payload = _collect_form(existing)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        ids = _split_identifiers(payload, existing)
        updated = data.update_student(sid, payload)
        _save_identifiers(sid, ids)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    except Exception as e:
        logger.exception("CLI update_student(%s) failed", sid)
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
        return
    print(f"\n  ✓ Updated {updated.student_id} ({updated.full_name})")
    _pause()


# ── Read (list / search / profile) ──────────────────────────────────

def _print_table(rows: list[directory.DirectoryRow]) -> None:
    if not rows:
        print("\n  (no students)")
        return
    vis = directory.Visibility.of(access.current())
    show_flags = vis.send or vis.medical or vis.safeguarding
    print()
    head = f"  {'ID':<9}  {'Name':<24}  {'Year':<19}  {'Tutor':<7}  {'Status':<9}"
    if vis.attendance:
        head += f"  {'Attend':>6}"
    head += "  A-Levels"
    if show_flags:
        head += "  │ Flags"
    print(head)
    print("  " + "-" * (len(head) + 18))
    for r in rows:
        s = r.student
        line = (f"  {s.student_id:<9}  {s.full_name[:24]:<24}  "
                f"{(r.year_label or '—')[:19]:<19}  {(r.tutor_group or '—')[:7]:<7}  "
                f"{s.status:<9}")
        if vis.attendance:
            line += ("  " + ("—" if r.attendance_pct is None
                             else f"{r.attendance_pct:.0f}%").rjust(6))
        line += "  " + (", ".join(s.subjects) or "—")
        if show_flags and r.flags():
            line += "  │ " + ", ".join(r.flags())
        print(line)
    print(f"\n  {len(rows)} student(s).")


def _describe_filters(f: dict[str, Any]) -> str:
    bits = [f.get("status") or directory.DEFAULT_STATUS_FILTER]
    for key, label in (("year_group", "Year"), ("tutor_group", "Tutor group"),
                       ("subject", "Subject"), ("query", "Search")):
        if f.get(key):
            bits.append(f"{label}: {f[key]}")
    return " · ".join(bits)


def _load(f: dict[str, Any]) -> list[directory.DirectoryRow]:
    return directory.list_directory(
        status=f.get("status") or directory.DEFAULT_STATUS_FILTER,
        year_group=f.get("year_group"), tutor_group=f.get("tutor_group"),
        subject=f.get("subject"), query=f.get("query"))


def _edit_filters(f: dict[str, Any]) -> None:
    opts = directory.filter_options()
    print("\n  ── Filters (Enter keeps the current value) ──")
    print("  Status:")
    f["status"] = _pick("Status", opts["statuses"],
                        default=f.get("status") or directory.DEFAULT_STATUS_FILTER)
    years = ["All"] + [str(y) for y in opts["years"]]
    print("  Year group:")
    y = _pick("Year", years, default=str(f.get("year_group") or "All"))
    f["year_group"] = None if y == "All" else int(y)
    groups = ["All"] + opts["tutor_groups"]
    print("  Tutor group:")
    g = _pick("Tutor group", groups, default=f.get("tutor_group") or "All")
    f["tutor_group"] = None if g == "All" else g
    q = _input("Subject (blank = any, - to clear)", default=f.get("subject") or "")
    f["subject"] = None if q in ("", "-") else q
    if q not in ("", "-") and q not in opts["subjects"]:
        print(f"    (no subject called {q!r} — nothing will match)")


def _list_screen(title: str, f: dict[str, Any]) -> None:
    while True:
        print(f"\n═══ {title} ═══")
        print(f"  Showing: {_describe_filters(f)}")
        try:
            rows = _load(f)
        except Exception as e:
            logger.exception("CLI directory load failed")
            print(f"\n  ✗ Error loading directory: {e}")
            _pause()
            return
        _print_table(rows)
        if not _row_action_loop(rows, f):
            return


def student_directory() -> None:
    _list_screen("Student Directory", {"status": directory.DEFAULT_STATUS_FILTER})


def search_students() -> None:
    print("\n═══ Search Students ═══")
    print("  (matches ID, name, preferred name, either email, phone, ULN, UCI, "
          "UPN, candidate\n   number, postcode, previous school or tutor group)")
    try:
        q = _input("Search", allow_empty=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    # Leavers included: someone searching for a name wants to find them.
    _list_screen("Search Students", {"status": "All", "query": q})


def view_profile(student_id: str | None = None) -> None:
    print("\n═══ Student Profile ═══")
    try:
        sid = student_id or _input("Student ID", allow_empty=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    prof = directory.student_profile(sid)
    if prof is None:
        print(f"\n  ✗ No student with id {sid}")
        _pause()
        return
    student = prof.student
    tutor = prof.tutor_group or "—"
    if prof.tutor:
        tutor += f" (tutor {prof.tutor}" + (f", room {prof.tutor_room}"
                                            if prof.tutor_room else "") + ")"
    print()
    for label, value in (
            ("Student ID", student.student_id), ("Name", student.full_name),
            ("Preferred name", student.preferred_name),
            ("Pronouns", student.pronouns),
            ("Status", student.status), ("Title", student.title),
            ("Gender", student_profile.gender_label(student.gender)), ("Date of birth", student.date_of_birth),
            ("Current year", prof.year_label or "Not enrolled"),
            ("Tutor group", tutor), ("Sixth-form email", student.email),
            ("Personal email", student.personal_email), ("Phone", student.phone),
            ("Photo", "On file" if prof.photo_path else "None"),
            ("Ethnicity", student.ethnicity_label),
            ("Nationality", student.nationality),
            ("First language", student.first_language),
            ("Home address", (student.address or "").replace("\n", ", ")),
            ("Postcode", student.postcode),
            ("Previous school", student.previous_school),
            ("Notes", (student.notes or "").replace("\n", " ")),
            ("UPN", data.get_upn(student.student_id)),
            ("Started", student.start_date),
            ("Left", (student.leaving_date or "")
             + (f" ({student.leaving_reason})" if student.leaving_reason else ""))):
        print(f"    {label:<17}: {value or '—'}")
    print()
    print("    Emergency contact:")
    print(f"      Name        : {student.emergency_contact_name or '—'}")
    print(f"      Phone       : {student.emergency_contact_phone or '—'}")
    print(f"      Relation    : {student.emergency_contact_relation or '—'}")
    if access.current().can_open("Parent Contacts"):
        print("\n    Parents & guardians:")
        for c in prof.contacts:
            marks = [m for m, on in (("primary", c.is_primary),
                                     ("emergency", c.is_emergency_contact),
                                     ("PR", c.has_parental_responsibility)) if on]
            print(f"      - {c.first_name} {c.last_name} ({c.relationship})"
                  f"  {c.primary_phone or ''}  {c.email or ''}"
                  + (f"  [{', '.join(marks)}]" if marks else ""))
        if not prof.contacts:
            print("      (none recorded)")
    print()
    _print_enrolments(sid)
    print()
    print("    A-Level subjects:")
    for i, subj in enumerate(student.subjects, 1):
        print(f"      {i}) {subj}")
    print()
    print(f"    ULN / UCI / candidate no.: {student.uln or '—'} / "
          f"{student.uci or '—'} / {student.candidate_number or '—'}")
    try:
        from education_system.systems.sixth_form.domain.academics.qualifications import (
            learning_aims,
        )
        aims = learning_aims.active_aims(sid)
        print("    Learning aims:")
        for a in aims:
            print(f"      - {a.label} (from {a.start_date})")
        if not aims:
            print("      (none)")
    except Exception:
        logger.exception("Could not list learning aims for %s", sid)
    if prof.records:
        print("\n    Records:")
        for r in prof.records:
            print(f"      {r.area:<14}: {r.summary}")
    if prof.account is not None:
        a = prof.account
        print(f"\n    Login: {a['state']} (username {a['username']}, "
              f"last sign-in {a['last_login'] or 'never'})")
    elif _may_manage():
        print("\n    Login: no login account")
    if prof.contact_log:
        print("\n    Contact log (newest first):")
        for c in prof.contact_log[:5]:
            print(f"      {c.contact_date}  {c.method:<9} {c.contact_with[:16]:<17}"
                  f"{c.reason[:18]:<19}{c.summary.splitlines()[0][:40] if c.summary else ''}")
        if len(prof.contact_log) > 5:
            print(f"      … {len(prof.contact_log) - 5} more in Pastoral > Contact Log")
    if prof.history:
        print("\n    Record history (newest first):")
        for h in prof.history[:10]:
            what = "Record" if h["field"] == "record" else h["field"]
            change = (f"{h['old_value'] or '—'} → {h['new_value'] or '—'}"
                      if h["field"] != "record" else "")
            print(f"      #{h['history_id']:<6} {h['at']}  {h['changed_by'] or '—':<10}  "
                  f"{what}: {change}{'  (' + h['note'] + ')' if h['note'] else ''}")
        if len(prof.history) > 10:
            print(f"      … {len(prof.history) - 10} older change(s)")
    try:
        choice = input("\n  P) Study programme   S) Change status   H) Photo   "
                       "C) Add contact   R) Revert a change\n"
                       "  N) Enrol (new enrolment)   (Enter to go back): "
                       ).strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return
    if choice == "p":
        _study_programme(sid)
    elif choice == "s":
        change_status_flow(sid)
    elif choice == "h":
        _photo_flow(sid, has_photo=bool(prof.photo_path))
    elif choice == "c":
        _add_contact_flow(sid)
    elif choice == "r":
        _revert_flow(sid, prof.history)
    elif choice == "n":
        _enrol_flow(sid)


def _photo_flow(student_id: str, *, has_photo: bool) -> None:
    if not _manage_ok():
        return
    from education_system.systems.sixth_form.domain.admissions.enrolments import (
        identity_checks,
    )
    by = access.current().username or None
    try:
        path = _input("Path to the new photo"
                      + (" (or 'remove' to take the photo off)" if has_photo else ""))
    except _UserAbort:
        print("  Cancelled.")
        return
    if not path:
        return
    if path.lower() == "remove":
        if identity_checks.remove_photo(student_id):
            data.record_history(student_id, "Photo", note="Photo removed",
                                changed_by=by)
            print("  ✓ Photo removed")
        _pause()
        return
    try:
        identity_checks.set_photo(student_id, path, by=by)
    except Exception as e:  # ValidationError and file errors alike
        print(f"  ✗ {e}")
        _pause()
        return
    data.record_history(student_id, "Photo", note="Photo changed", changed_by=by)
    print("  ✓ Photo saved")
    _pause()


def _add_contact_flow(student_id: str) -> None:
    """A parent or guardian for this student (the Parent Contacts fields)."""
    if not _manage_ok():
        return
    from education_system.systems.sixth_form.domains.communications.domain.parent_contacts import (
        parent_contacts,
    )
    print("\n  ── New parent / guardian contact ──")
    try:
        print("  Relationship:")
        rel = _pick("Relationship", list(parent_contacts.RELATIONSHIPS),
                    default=parent_contacts.DEFAULT_RELATIONSHIP)
        payload = {
            "student_id": student_id, "relationship": rel,
            "first_name": _input("First name", allow_empty=False),
            "last_name": _input("Last name", allow_empty=False),
            "primary_phone": _input("Phone"),
            "email": _input("Email"),
            "address": _input("Address (optional)"),
            "is_primary": _input("Primary contact? (y/n)", default="n")
            .lower().startswith("y"),
        }
    except _UserAbort:
        print("  Cancelled.")
        return
    try:
        c = parent_contacts.create_contact(payload)
    except parent_contacts.ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    print(f"  ✓ Added {c.first_name} {c.last_name} ({c.relationship})")
    _pause()


def _revert_flow(student_id: str, history: list[dict[str, Any]]) -> None:
    if not _manage_ok():
        return
    try:
        raw = _input("History # to revert (shown as #nnn above)")
    except _UserAbort:
        print("  Cancelled.")
        return
    entry = next((h for h in history if str(h["history_id"]) == raw.lstrip("#")), None)
    if entry is None:
        print("  ✗ No such entry on this record")
        _pause()
        return
    if not data.can_revert(entry):
        print(f"  ✗ {entry['field']} entries cannot be reverted here")
        _pause()
        return
    try:
        yes = _input(f"Put {entry['field']} back to "
                     f"{entry['old_value'] or '(empty)'!r}? (y/n)", default="n")
    except _UserAbort:
        return
    if not yes.lower().startswith("y"):
        return
    try:
        data.revert_history(entry["history_id"], by=access.current().username or None)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    print(f"  ✓ {entry['field']} reverted")
    _pause()


# ── Status, leaving and delete ──────────────────────────────────────

def change_status_flow(student_id: str | None = None) -> None:
    print("\n═══ Change Student Status ═══")
    if not _manage_ok():
        return
    try:
        sid = student_id or _input("Student ID", allow_empty=False)
        student = data.get_student(sid)
        if student is None:
            print(f"\n  ✗ No student with id {sid}")
            _pause()
            return
        print(f"  {student.full_name} is currently {student.status}.")
        new = _pick("New status", list(data.STATUSES), default=student.status)
        if new == student.status:
            print("\n  No change.")
            return
        if new == "Left":
            mark_left_flow(sid)
            return
        reason = _input("Reason (optional)")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.set_status(sid, new, reason=reason or None,
                        by=access.current().username or None)
    except (ValidationError, access.AccessDenied) as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ {sid} is now {new}")
    if student.status == "Left":
        print("    Login and tutor group restored where possible.")
        _offer_enrolment_reinstate([sid])
    _pause()


def mark_left_flow(student_id: str | None = None) -> None:
    print("\n═══ Mark Student as Left ═══")
    if not _manage_ok():
        return
    from education_system.systems.sixth_form.domain.learners.alumni.models import (
        LEAVING_REASONS,
    )
    try:
        sid = student_id or _input("Student ID", allow_empty=False)
        student = data.get_student(sid)
        if student is None:
            print(f"\n  ✗ No student with id {sid}")
            _pause()
            return
        print(f"  {student.full_name} ({student.student_id})")
        print("  Every record is kept. Open enrolments become Withdrawn, they "
              "leave their tutor group\n  and their login is closed. Learners "
              "moving to the university or an FE college\n  go through "
              "Promote to Next System instead.\n")
        reasons = [r for r in LEAVING_REASONS if r != "Transferred Out"]
        reason = _pick("Reason", reasons, default="Withdrew")
        ilr_code = _pick_ilr_reason(reason)
        detail = _input("Details (optional)")
        leaving_date = _input_date("Leaving date (YYYY-MM-DD)",
                                   default=_dt.date.today().isoformat())
        to_alumni = (access.current().can_open("Alumni") and
                     _input("Also add them to Alumni? (y/n)", default="y")
                     .lower().startswith("y"))
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.withdraw_student(sid, reason=f"{reason}: {detail}" if detail else reason,
                              leaving_date=leaving_date or None,
                              by=access.current().username or None,
                              withdrawal_reason=ilr_code,
                              withdrawal_detail=detail or reason)
    except (ValidationError, enrolments_data.ValidationError,
            access.AccessDenied) as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ {student.full_name} is now recorded as Left")
    _print_enrolments(sid)
    if to_alumni:
        try:
            from education_system.systems.sixth_form.domain.learners.alumni import (
                linking as alumni_linking,
            )
            alumni_linking.archive_student_enriched(
                sid, leaving_date=leaving_date or None, leaving_reason=reason)
            print("  ✓ Added to Alumni")
        except Exception as e:
            logger.exception("Alumni archive failed for %s", sid)
            print(f"  ✗ Could not add them to Alumni: {e}")
    _pause()


def delete_student_flow(student_id: str | None = None) -> None:
    print("\n═══ Delete Student ═══")
    if not _manage_ok():
        return
    try:
        sid = student_id or _input("Student ID", allow_empty=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    student = data.get_student(sid)
    if student is None:
        print(f"\n  ✗ No student with id {sid}")
        _pause()
        return
    counts = data.linked_record_counts(sid)
    if counts:
        print(f"\n  ✗ {student.full_name} ({sid}) has records that deleting "
              "would destroy:")
        for line in data.describe_linked_records(counts)[:12]:
            print(f"      • {line}")
        if student.status == "Left":
            print("\n  They are already recorded as Left, which keeps their history.")
            _pause()
            return
        try:
            yes = _input("Delete is only for a record entered by mistake. "
                         "Mark them as left instead? (y/n)", default="n")
        except _UserAbort:
            print("\n  Cancelled.")
            return
        if yes.lower().startswith("y"):
            mark_left_flow(sid)
        return
    try:
        confirm = _input(
            f"Permanently delete {student.full_name} ({student.student_id})? "
            "They have no other records. Type 'yes' to confirm",
            default="no",
        )
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if confirm.lower() != "yes":
        print("\n  Cancelled.")
        return
    try:
        if data.delete_student(sid):
            print(f"\n  ✓ Deleted {sid}")
        else:
            print(f"\n  ✗ Could not delete {sid}")
    except Exception as e:
        logger.exception("CLI delete_student(%s) failed", sid)
        print(f"\n  ✗ {e}")
    _pause()


def _export_flow(rows: list[directory.DirectoryRow]) -> None:
    try:
        path = _input("Save CSV to", default="student_directory.csv")
    except _UserAbort:
        print("  Cancelled.")
        return
    try:
        n = directory.export_csv(rows, path)
    except Exception as e:
        logger.exception("CLI directory export failed")
        print(f"  ✗ Export failed: {e}")
        _pause()
        return
    print(f"  ✓ {n} student(s) written to {path}")
    _pause()


# ── Row-action helper for list & search results ─────────────────────

def _row_action_loop(rows: list[directory.DirectoryRow],
                     filters: dict[str, Any]) -> bool:
    """After printing a list, let the user act on a row, filter or export.
    Returns True when the list should be shown again."""
    print()
    print("  Actions:  V) View   E) Edit   D) Delete   S) Change status   "
          "P) Study programme")
    print("            B) Change status of several   Y) Export some")
    print("            F) Filter   X) Export CSV   (Enter to go back)")
    while True:
        try:
            choice = input("  Action: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return False
        if not choice:
            return False
        if choice not in ("v", "e", "d", "s", "p", "f", "x", "b", "y"):
            print("    Pick V, E, D, S, P, B, Y, F, X, or Enter.")
            continue
        try:
            if choice in ("b", "y"):
                ids = _pick_many(rows)
                if not ids:
                    return True
                if choice == "b":
                    _bulk_status_flow(ids)
                else:
                    _export_flow([r for r in rows if r.student.student_id in ids])
                return True
            if choice == "f":
                _edit_filters(filters)
                return True
            if choice == "x":
                _export_flow(rows)
                return True
            sid = _input("Student ID", allow_empty=False)
        except _UserAbort:
            print("  Cancelled.")
            return False
        if choice == "v":
            view_profile(sid)
        elif choice == "e":
            edit_student(sid)
        elif choice == "d":
            delete_student_flow(sid)
        elif choice == "s":
            change_status_flow(sid)
        elif choice == "p":
            _study_programme(sid)
        return True


def _pick_many(rows: list[directory.DirectoryRow]) -> list[str]:
    """Student IDs typed with commas or spaces; 'all' takes the list shown."""
    raw = _input("Student IDs (comma-separated, or 'all' for the list shown)")
    listed = [r.student.student_id for r in rows]
    if raw.lower() == "all":
        return listed
    ids = [x for x in raw.replace(",", " ").split() if x]
    unknown = [x for x in ids if x not in listed]
    if unknown:
        print(f"    Not in the list shown (ignored): {', '.join(unknown)}")
    return [x for x in ids if x in listed]


def _bulk_status_flow(student_ids: list[str]) -> None:
    """Same route as one change per learner; failures are listed."""
    if not _manage_ok():
        return
    print(f"\n  {len(student_ids)} student(s) selected.")
    try:
        new = _pick("New status", list(data.STATUSES), default=data.DEFAULT_STATUS)
        reason = _input("Reason" + (" (required)" if new == "Left" else " (optional)"),
                        allow_empty=new != "Left")
        leaving = (_input_date("Leaving date (YYYY-MM-DD)",
                               default=_dt.date.today().isoformat())
                   if new == "Left" else "")
        ilr_code = _pick_ilr_reason() if new == "Left" else None
    except _UserAbort:
        print("  Cancelled.")
        return
    by = access.current().username or None
    done, failed = 0, []
    back_on_roll: list[str] = []
    for sid in student_ids:
        try:
            st = data.get_student(sid)
            if st is None or st.status == new:
                continue
            if new == "Left":
                data.withdraw_student(sid, reason=reason, leaving_date=leaving or None,
                                      by=by, withdrawal_reason=ilr_code,
                                      withdrawal_detail=reason)
            else:
                data.set_status(sid, new, reason=reason or None, by=by)
                if st.status == "Left":
                    back_on_roll.append(sid)
            done += 1
        except Exception as e:  # reported per learner
            failed.append(f"{sid}: {e}")
    print(f"\n  ✓ {done} student(s) now {new}")
    for line in failed:
        print(f"  ✗ {line}")
    if back_on_roll:
        _offer_enrolment_reinstate(back_on_roll)
    _pause()


def _study_programme(student_id: str | None = None) -> None:
    from education_system.systems.sixth_form.interfaces.cli.academics.qualifications import (
        study_programme_cli,
    )
    study_programme_cli.run_for_student(student_id)


def _study_programme_reports() -> None:
    from education_system.systems.sixth_form.interfaces.cli.academics.qualifications import (
        study_programme_cli,
    )
    study_programme_cli.run_reports()


# ── Dispatch ────────────────────────────────────────────────────────

HANDLERS: dict[str, Callable[[], None]] = {
    "Student Directory": student_directory,
    "Add Student":       add_student,
    "Search Students":   search_students,
    "Student Profile":   view_profile,
    # For a top-level "Study Programme" entry, if the lead adds one.
    "Study Programme":   _study_programme_reports,
}


def dispatch(label: str) -> bool:
    """Run the CLI flow matching a menu label.

    Returns True if a handler ran (the caller should skip its stub
    output), False if no real handler exists for that label.
    """
    handler = HANDLERS.get(label)
    if handler is None:
        return False
    try:
        handler()
    except _UserAbort:
        print("\n  Cancelled.")
    except Exception as e:
        logger.exception("CLI handler %r crashed", label)
        print(f"\n  ✗ Unexpected error in {label}: {e}")
        _pause()
    return True
