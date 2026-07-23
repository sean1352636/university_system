"""CLI flows for Sixth Form Alumni."""

from __future__ import annotations

import logging
from datetime import date as _date
from typing import Any, Callable
from education_system.post_16.sixthform_system.modules.domain.students.alumni import (
    alumni as data,
)
from education_system.post_16.sixthform_system.modules.domain.students.students import (
    students as student_data,
)
from education_system.post_16.sixthform_system.modules.domain.students.alumni.alumni import (
    ACHIEVEMENT_CATEGORIES,
    Alumnus,
    CAMPAIGN_STATUSES,
    APPLICATION_STATUSES,
    BEQUEST_STATUSES,
    CUSTOM_FIELD_TYPES,
    ERASURE_STATUSES,
    MEDIA_KINDS,
    PROTECTED_CHARS,
    WEBHOOK_EVENT_TYPES,
    CHAPTER_KINDS,
    CHAPTER_ROLES,
    CONNECTION_KINDS,
    DIRECTORY_CONSENT_SCOPE,
    DONOR_STAGES,
    DRIP_STATUSES,
    JOB_STATUSES,
    JOB_TYPES,
    MILESTONE_KINDS,
    NEET_STATUSES,
    NEWSLETTER_STATUSES,
    PROFICIENCY_LEVELS,
    RECURRING_FREQS,
    RECURRING_STATUSES,
    SAFEGUARDING_STATUSES,
    SOCIAL_PLATFORMS,
    TRACK_KINDS,
    COMM_CHANNELS,
    COMM_STATUSES,
    CONSENT_SCOPES,
    DEFAULT_CAMPAIGN_STATUS,
    DEFAULT_DESTINATION,
    DEFAULT_EDUCATION_STATUS,
    DEFAULT_EVENT_STATUS,
    DEFAULT_LEAVING_REASON,
    DEFAULT_PLEDGE_STATUS,
    DEFAULT_RSVP_STATUS,
    DEFAULT_STATUS,
    DESTINATION_TYPES,
    EDUCATION_STATUSES,
    EMAIL_LABELS,
    EVENT_STATUSES,
    EVENT_TYPES,
    GENDER_OPTIONS,
    LEAVING_REASONS,
    MENTORSHIP_STATUSES,
    PAYMENT_METHODS,
    PHONE_LABELS,
    PLEDGE_STATUSES,
    REFERENCE_TYPES,
    RSVP_STATUSES,
    SALARY_BANDS,
    SECTORS,
    SESSION_FORMATS,
    STATUSES,
    VOLUNTEER_ACTIVITY_TYPES,
    WORK_EXP_STATUSES,
    ValidationError,
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


def _yes_no(prompt: str, *, default: bool = False) -> bool:
    raw = _input(f"{prompt} (y/n)",
                  default="y" if default else "n").strip().lower()
    return raw in ("y", "yes")


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


def _pick_alumnus() -> Alumnus:
    rows = data.list_alumni()
    if not rows:
        print("    No alumni.")
        raise _UserAbort
    print("\n  Alumni:")
    for i, a in enumerate(rows, 1):
        print(f"    {i:>3}) #{a.alumni_id}  {a.full_name[:24]:<24}  "
              f"({a.leaving_year or '—'})  [{a.status}]")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or alumni id)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1]
            match = next((a for a in rows if a.alumni_id == n), None)
            if match:
                return match
        print("    No matching alumnus.")


def _pick_student() -> str:
    rows = student_data.list_students()
    if not rows:
        print("    No current students.")
        raise _UserAbort
    print("\n  Students:")
    for i, s in enumerate(rows, 1):
        print(f"    {i:>3}) {s.student_id}  {s.full_name}")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or student ID)",
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


# ── Print helpers ──────────────────────────────────────────────────

def _print_alumni(rows: list[Alumnus]) -> None:
    if not rows:
        print("\n  (no alumni)")
        return
    print()
    print(f"  {'#':>4}  {'Name':<24}  {'Year':<6}  "
          f"{'Destination':<14}  {'Detail':<28}  Status")
    print("  " + "-" * 95)
    for a in rows:
        print(f"  {a.alumni_id:>4}  {a.full_name[:24]:<24}  "
              f"{a.leaving_year or '—':<6}  "
              f"{a.destination_type[:14]:<14}  "
              f"{(a.destination_detail or '—')[:28]:<28}  "
              f"{a.status}")
    print(f"\n  {len(rows)} alumnus/alumni.")


# ── Flows ──────────────────────────────────────────────────────────

def list_all() -> None:
    print("\n═══ All Alumni ═══")
    _print_alumni(data.list_alumni())
    _pause()


def filter_alumni() -> None:
    print("\n═══ Filter Alumni ═══")
    print("  (blank to skip)\n")
    try:
        year = _input("Leaving year (YYYY)") or None
        dest = _input(f"Destination ({'/'.join(DESTINATION_TYPES)})") or None
        status = _input(f"Status ({'/'.join(STATUSES)})") or None
        search = _input("Search (name/email/employer)") or None
        contactable = _yes_no("Contactable only?", default=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        rows = data.list_alumni(
            leaving_year=year, destination_type=dest, status=status,
            search=search, contactable_only=contactable,
        )
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    _print_alumni(rows)
    _pause()


def view_alumnus() -> None:
    print("\n═══ View Alumnus ═══")
    try:
        a = _pick_alumnus()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    print()
    print(f"    #{a.alumni_id}  {a.display_name}")
    print(f"    Pronouns            : {a.pronouns or '—'}")
    print(f"    Gender              : {a.gender or '—'}")
    print(f"    Original student id : {a.original_student_id or '—'}")
    print(f"    DOB                 : {a.dob or '—'}")
    print(f"    Leaving year        : {a.leaving_year or '—'}")
    print(f"    Leaving date        : {a.leaving_date or '—'}")
    print(f"    Leaving reason      : {a.leaving_reason or '—'}")
    print(f"    Destination         : {a.destination_type}")
    if a.destination_detail:
        print(f"      Detail            : {a.destination_detail}")
    print(f"    Current role        : {a.current_role or '—'}")
    print(f"    Employer            : {a.current_employer or '—'}")
    print(f"    Sector              : {a.current_sector or '—'}")
    print(f"    Location            : {a.current_location or '—'}")
    print(f"    Country / region    : "
          f"{a.country or '—'} / {a.region or '—'}")
    print(f"    Email               : {a.email or '—'}")
    print(f"    Phone               : {a.phone or '—'}")
    print(f"    Address             : {a.address or '—'}")
    print(f"    LinkedIn            : {a.linkedin or '—'}")
    print(f"    Other social        : {a.other_social or '—'}")
    print(f"    Opt-in contact      : "
          f"{'yes' if a.opt_in_contact else 'no'}")
    print(f"    Status              : {a.status}")
    print(f"    Last contacted      : {a.last_contacted or '—'}")
    if a.photo_path:
        print(f"    Photo               : {a.photo_path}")
    if a.bio:
        print(f"    Bio                 : {a.bio}")
    tags = data.list_tags_for(a.alumni_id)
    if tags:
        print(f"    Tags                : "
              f"{', '.join(t.name for t in tags)}")
    emails = data.list_emails(a.alumni_id)
    if emails:
        print("\n    Emails:")
        for e in emails:
            star = "*" if e.is_primary else " "
            print(f"     {star} #{e.email_id} [{e.label}] {e.email}")
    phones = data.list_phones(a.alumni_id)
    if phones:
        print("\n    Phones:")
        for ph in phones:
            star = "*" if ph.is_primary else " "
            print(f"     {star} #{ph.phone_id} [{ph.label}] {ph.phone}")
    edu = data.list_education(a.alumni_id)
    if edu:
        print("\n    Education:")
        for e in edu:
            span = f"{e.start_date or '?'} → {e.end_date or '…'}"
            print(f"      #{e.education_id} {e.qualification}"
                  f"{(' ' + e.subject) if e.subject else ''} "
                  f"@ {e.institution}  ({span})  "
                  f"[{e.status}{', ' + e.grade if e.grade else ''}]")
    career = data.list_career(a.alumni_id)
    if career:
        print("\n    Career:")
        for c in career:
            span = f"{c.start_date or '?'} → " + (
                "present" if c.is_current else (c.end_date or '?'))
            sect = f" / {c.sector}" if c.sector else ""
            print(f"      #{c.career_id} {c.role} @ {c.employer}"
                  f"{sect}  ({span})"
                  + (f"  [{c.salary_band}]" if c.salary_band else ""))
    ach = data.list_achievements(a.alumni_id)
    if ach:
        print("\n    Achievements:")
        for x in ach:
            dt = f"{x.date}  " if x.date else ""
            cat = f"[{x.category}] " if x.category else ""
            print(f"      #{x.achievement_id} {dt}{cat}{x.title}")
    if a.notes:
        print("\n    Notes:")
        for line in a.notes.splitlines():
            print(f"      {line}")
    _pause()


def _collect_form(existing: Alumnus | None) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    is_edit = existing is not None
    payload["first_name"] = _input(
        "First name",
        default=(existing.first_name if is_edit else ""),
        allow_empty=False)
    payload["last_name"] = _input(
        "Last name",
        default=(existing.last_name if is_edit else ""),
        allow_empty=False)
    payload["preferred_name"] = _input(
        "Preferred name",
        default=(existing.preferred_name or "") if is_edit else "")
    payload["pronouns"] = _input(
        "Pronouns (e.g. she/her)",
        default=(existing.pronouns or "") if is_edit else "")
    gender_default = (existing.gender if is_edit and existing.gender
                        else "")
    if _yes_no("Set gender?",
                default=bool(gender_default)):
        payload["gender"] = _pick_from(
            "Gender", list(GENDER_OPTIONS),
            default=gender_default or GENDER_OPTIONS[0])
    else:
        payload["gender"] = gender_default
    payload["dob"] = _input(
        "Date of birth (YYYY-MM-DD)",
        default=(existing.dob or "") if is_edit else "")
    payload["leaving_year"] = _input(
        "Leaving year (YYYY)",
        default=(existing.leaving_year or "") if is_edit else "")
    payload["leaving_date"] = _input(
        "Leaving date (YYYY-MM-DD)",
        default=(existing.leaving_date or "") if is_edit else "")
    payload["leaving_reason"] = _pick_from(
        "Leaving reason", [""] + list(LEAVING_REASONS),
        default=(existing.leaving_reason
                  if is_edit and existing.leaving_reason
                  else DEFAULT_LEAVING_REASON))
    payload["destination_type"] = _pick_from(
        "Destination", list(DESTINATION_TYPES),
        default=(existing.destination_type if is_edit
                  else DEFAULT_DESTINATION))
    payload["destination_detail"] = _input(
        "Destination detail",
        default=(existing.destination_detail or "") if is_edit else "")
    payload["current_role"] = _input(
        "Current role",
        default=(existing.current_role or "") if is_edit else "")
    payload["current_employer"] = _input(
        "Current employer",
        default=(existing.current_employer or "") if is_edit else "")
    sector_default = (existing.current_sector
                       if is_edit and existing.current_sector else "")
    if _yes_no("Set sector?", default=bool(sector_default)):
        payload["current_sector"] = _pick_from(
            "Sector", list(SECTORS),
            default=sector_default or SECTORS[0])
    else:
        payload["current_sector"] = sector_default
    payload["current_location"] = _input(
        "Current location",
        default=(existing.current_location or "") if is_edit else "")
    payload["country"] = _input(
        "Country",
        default=(existing.country or "") if is_edit else "")
    payload["region"] = _input(
        "Region / state",
        default=(existing.region or "") if is_edit else "")
    payload["email"] = _input(
        "Email",
        default=(existing.email or "") if is_edit else "")
    payload["phone"] = _input(
        "Phone",
        default=(existing.phone or "") if is_edit else "")
    payload["address"] = _input(
        "Address",
        default=(existing.address or "") if is_edit else "")
    payload["linkedin"] = _input(
        "LinkedIn URL",
        default=(existing.linkedin or "") if is_edit else "")
    payload["other_social"] = _input(
        "Other social",
        default=(existing.other_social or "") if is_edit else "")
    payload["photo_path"] = _input(
        "Photo path",
        default=(existing.photo_path or "") if is_edit else "")
    payload["bio"] = _input(
        "Bio (single line)",
        default=(existing.bio or "") if is_edit else "")
    payload["opt_in_contact"] = _yes_no(
        "Opt-in to contact?",
        default=(existing.opt_in_contact if is_edit else False))
    payload["status"] = _pick_from(
        "Status", list(STATUSES),
        default=(existing.status if is_edit else DEFAULT_STATUS))
    payload["last_contacted"] = _input(
        "Last contacted (YYYY-MM-DD)",
        default=(existing.last_contacted or "") if is_edit else "")
    payload["notes"] = _input(
        "Notes",
        default=(existing.notes or "") if is_edit else "")
    return payload


def new_alumnus() -> None:
    print("\n═══ New Alumnus (manual) ═══")
    try:
        payload = _collect_form(None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        a = data.create_alumnus(payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Created alumnus #{a.alumni_id} ({a.full_name})")
    _pause()


def edit_alumnus() -> None:
    print("\n═══ Edit Alumnus ═══")
    try:
        a = _pick_alumnus()
        payload = _collect_form(a)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_alumnus(a.alumni_id, payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Updated #{a.alumni_id}")
    _pause()


def archive_student_flow() -> None:
    print("\n═══ Archive Current Student → Alumni ═══")
    print("  (will auto-fill destination from UCAS, seed A-level "
           "results,\n   and tag bursary recipients)\n")
    try:
        sid = _pick_student()
        year = _input("Leaving year (YYYY, blank = derive)",
                       default=str(_date.today().year))
        date_str = _input("Leaving date (YYYY-MM-DD)",
                            default=_date.today().isoformat())
        reason = _pick_from("Leaving reason", list(LEAVING_REASONS),
                              default=DEFAULT_LEAVING_REASON)
        override_dest = _yes_no(
            "Override auto-derived destination?", default=False)
        dest = None
        detail = None
        if override_dest:
            dest = _pick_from("Destination", list(DESTINATION_TYPES),
                                default=DEFAULT_DESTINATION)
            detail = _input("Destination detail")
        delete = _yes_no(
            "Also delete the student row? "
            "(history/links will be cascade-removed)",
            default=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        kwargs: dict[str, Any] = {
            "leaving_year":   year or None,
            "leaving_date":   date_str,
            "leaving_reason": reason,
            "delete_student": delete,
        }
        if dest:
            kwargs["destination_type"] = dest
            kwargs["destination_detail"] = detail or None
        a = data.archive_student_enriched(sid, **kwargs)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Archived {sid} as alumnus #{a.alumni_id}")
    edu = data.list_education(a.alumni_id)
    if edu:
        print(f"    Seeded {len(edu)} education row(s) "
               "from exam results")
    tags = data.list_tags_for(a.alumni_id)
    if tags:
        print(f"    Tags: {', '.join(t.name for t in tags)}")
    _pause()


def record_contact_flow() -> None:
    print("\n═══ Record Contact ═══")
    try:
        a = _pick_alumnus()
        when = _input("When (YYYY-MM-DD)",
                        default=_date.today().isoformat())
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.record_contact(a.alumni_id, when=when)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Logged contact on {when}")
    _pause()


def set_status_flow() -> None:
    print("\n═══ Change Status ═══")
    try:
        a = _pick_alumnus()
        new_status = _pick_from("New status", list(STATUSES),
                                  default=a.status)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.set_status(a.alumni_id, new_status)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{a.alumni_id} → {new_status}")
    _pause()


def delete_alumnus_flow() -> None:
    print("\n═══ Delete Alumnus ═══")
    try:
        a = _pick_alumnus()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if _input(
            f"Soft-delete alumnus #{a.alumni_id} ({a.full_name})?\n"
            f"  Recoverable for {data.SOFT_DELETE_UNDO_DAYS} days "
            "via Trash. Type 'yes'",
            default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_alumnus(a.alumni_id):
        print(f"\n  ✓ Soft-deleted #{a.alumni_id}")
    _pause()


def summary_flow() -> None:
    print("\n═══ Alumni Summary ═══")
    summ = data.summary()
    print(f"\n  Total alumni      : {summ.total}")
    print(f"  Contactable       : {summ.contactable}")
    print(f"  No contact method : {summ.no_contact_method}")
    print(f"  Most recent year  : {summ.most_recent_year or '—'}")
    print("\n  By status:")
    for s in STATUSES:
        n = summ.by_status.get(s, 0)
        if n:
            print(f"    {s:<14} : {n}")
    print("\n  By destination:")
    for d in DESTINATION_TYPES:
        n = summ.by_destination.get(d, 0)
        if n:
            print(f"    {d:<18} : {n}")
    if summ.by_leaving_year:
        print("\n  By leaving year:")
        for year, n in list(summ.by_leaving_year.items())[:10]:
            print(f"    {year} : {n}")
    _pause()


# ── Education / Career / Contacts / Tags / Achievements ───────────

def _opt(s: str | None) -> str:
    return s or "—"


def education_flow() -> None:
    print("\n═══ Education History ═══")
    try:
        a = _pick_alumnus()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    while True:
        rows = data.list_education(a.alumni_id)
        print(f"\n  Education for #{a.alumni_id} {a.full_name}:")
        if not rows:
            print("    (none)")
        for e in rows:
            span = f"{e.start_date or '?'} → {e.end_date or '…'}"
            print(f"    #{e.education_id:<3} {e.qualification} "
                  f"{e.subject or ''} @ {e.institution}  "
                  f"({span})  [{e.status}{', ' + e.grade if e.grade else ''}]")
        print("\n    a) Add    e) Edit    d) Delete    0) Back")
        try:
            choice = _input("Choice", default="0").lower()
        except _UserAbort:
            return
        if choice in ("0", ""):
            return
        try:
            if choice == "a":
                payload = {
                    "qualification": _input("Qualification (e.g. BA, MSc)",
                                              allow_empty=False),
                    "subject":       _input("Subject"),
                    "institution":   _input("Institution",
                                              allow_empty=False),
                    "start_date":    _input("Start date (YYYY-MM-DD)"),
                    "end_date":      _input("End date (YYYY-MM-DD)"),
                    "grade":         _input("Grade / classification"),
                    "status":        _pick_from(
                        "Status", list(EDUCATION_STATUSES),
                        default=DEFAULT_EDUCATION_STATUS),
                    "notes":         _input("Notes"),
                }
                data.add_education(a.alumni_id, payload)
            elif choice == "e":
                eid = int(_input("Edit #id", allow_empty=False))
                cur = next((x for x in rows
                              if x.education_id == eid), None)
                if not cur:
                    print("    No such row."); continue
                payload = {
                    "qualification": _input("Qualification",
                                              default=cur.qualification),
                    "subject":       _input("Subject",
                                              default=cur.subject or ""),
                    "institution":   _input("Institution",
                                              default=cur.institution),
                    "start_date":    _input("Start date",
                                              default=cur.start_date or ""),
                    "end_date":      _input("End date",
                                              default=cur.end_date or ""),
                    "grade":         _input("Grade",
                                              default=cur.grade or ""),
                    "status":        _pick_from(
                        "Status", list(EDUCATION_STATUSES),
                        default=cur.status),
                    "notes":         _input("Notes",
                                              default=cur.notes or ""),
                }
                data.update_education(eid, payload)
            elif choice == "d":
                eid = int(_input("Delete #id", allow_empty=False))
                if data.delete_education(eid):
                    print("    ✓ Deleted")
        except _UserAbort:
            print("    Cancelled.")
        except (ValidationError, ValueError) as ex:
            print(f"    ✗ {ex}")


def career_flow() -> None:
    print("\n═══ Career History ═══")
    try:
        a = _pick_alumnus()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    while True:
        rows = data.list_career(a.alumni_id)
        print(f"\n  Career for #{a.alumni_id} {a.full_name}:")
        if not rows:
            print("    (none)")
        for c in rows:
            span = (f"{c.start_date or '?'} → "
                     + ("present" if c.is_current
                        else (c.end_date or '?')))
            print(f"    #{c.career_id:<3} {c.role} @ {c.employer}  "
                  f"({_opt(c.sector)})  ({span})  "
                  f"[{_opt(c.salary_band)}]")
        print("\n    a) Add    e) Edit    d) Delete    0) Back")
        try:
            choice = _input("Choice", default="0").lower()
        except _UserAbort:
            return
        if choice in ("0", ""):
            return
        try:
            if choice == "a":
                sector = ""
                if _yes_no("Set sector?", default=True):
                    sector = _pick_from("Sector", list(SECTORS),
                                          default=SECTORS[0])
                band = ""
                if _yes_no("Set salary band?", default=False):
                    band = _pick_from("Salary band",
                                        list(SALARY_BANDS),
                                        default=SALARY_BANDS[0])
                payload = {
                    "role":        _input("Role", allow_empty=False),
                    "employer":    _input("Employer", allow_empty=False),
                    "sector":      sector,
                    "country":     _input("Country"),
                    "location":    _input("Location"),
                    "start_date":  _input("Start date (YYYY-MM-DD)"),
                    "end_date":    _input("End date (YYYY-MM-DD)"),
                    "is_current":  _yes_no("Current role?", default=False),
                    "salary_band": band,
                    "notes":       _input("Notes"),
                }
                data.add_career(a.alumni_id, payload)
            elif choice == "e":
                cid = int(_input("Edit #id", allow_empty=False))
                cur = next((x for x in rows
                              if x.career_id == cid), None)
                if not cur:
                    print("    No such row."); continue
                sector = cur.sector or ""
                if _yes_no("Change sector?", default=False):
                    sector = _pick_from("Sector", list(SECTORS),
                                          default=sector or SECTORS[0])
                band = cur.salary_band or ""
                if _yes_no("Change salary band?", default=False):
                    band = _pick_from("Salary band",
                                        list(SALARY_BANDS),
                                        default=band or SALARY_BANDS[0])
                payload = {
                    "role":        _input("Role", default=cur.role),
                    "employer":    _input("Employer",
                                            default=cur.employer),
                    "sector":      sector,
                    "country":     _input("Country",
                                            default=cur.country or ""),
                    "location":    _input("Location",
                                            default=cur.location or ""),
                    "start_date":  _input("Start date",
                                            default=cur.start_date or ""),
                    "end_date":    _input("End date",
                                            default=cur.end_date or ""),
                    "is_current":  _yes_no("Current role?",
                                             default=cur.is_current),
                    "salary_band": band,
                    "notes":       _input("Notes",
                                            default=cur.notes or ""),
                }
                data.update_career(cid, payload)
            elif choice == "d":
                cid = int(_input("Delete #id", allow_empty=False))
                if data.delete_career(cid):
                    print("    ✓ Deleted")
        except _UserAbort:
            print("    Cancelled.")
        except (ValidationError, ValueError) as ex:
            print(f"    ✗ {ex}")


def contacts_flow() -> None:
    print("\n═══ Emails & Phones ═══")
    try:
        a = _pick_alumnus()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    while True:
        emails = data.list_emails(a.alumni_id)
        phones = data.list_phones(a.alumni_id)
        print(f"\n  Contacts for #{a.alumni_id} {a.full_name}:")
        print("\n  Emails:")
        if not emails:
            print("    (none)")
        for e in emails:
            star = "*" if e.is_primary else " "
            print(f"    {star} #{e.email_id:<3} [{e.label}] {e.email}")
        print("\n  Phones:")
        if not phones:
            print("    (none)")
        for ph in phones:
            star = "*" if ph.is_primary else " "
            print(f"    {star} #{ph.phone_id:<3} [{ph.label}] {ph.phone}")
        print("\n    ae) Add email   ap) Add phone")
        print("    pe) Make email primary   pp) Make phone primary")
        print("    de) Delete email   dp) Delete phone   0) Back")
        try:
            choice = _input("Choice", default="0").lower()
        except _UserAbort:
            return
        if choice in ("0", ""):
            return
        try:
            if choice == "ae":
                addr = _input("Email", allow_empty=False)
                label = _pick_from("Label", list(EMAIL_LABELS),
                                     default="Personal")
                is_p = _yes_no("Make primary?",
                                default=not emails)
                data.add_email(a.alumni_id, addr,
                                 label=label, is_primary=is_p)
            elif choice == "ap":
                num = _input("Phone", allow_empty=False)
                label = _pick_from("Label", list(PHONE_LABELS),
                                     default="Mobile")
                is_p = _yes_no("Make primary?",
                                default=not phones)
                data.add_phone(a.alumni_id, num,
                                 label=label, is_primary=is_p)
            elif choice == "pe":
                eid = int(_input("Email #id", allow_empty=False))
                data.set_primary_email(eid)
            elif choice == "pp":
                pid = int(_input("Phone #id", allow_empty=False))
                data.set_primary_phone(pid)
            elif choice == "de":
                eid = int(_input("Email #id", allow_empty=False))
                if data.delete_email(eid):
                    print("    ✓ Deleted")
            elif choice == "dp":
                pid = int(_input("Phone #id", allow_empty=False))
                if data.delete_phone(pid):
                    print("    ✓ Deleted")
        except _UserAbort:
            print("    Cancelled.")
        except (ValidationError, ValueError) as ex:
            print(f"    ✗ {ex}")


def tags_flow() -> None:
    print("\n═══ Tags ═══")
    try:
        a = _pick_alumnus()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    while True:
        tags = data.list_tags_for(a.alumni_id)
        print(f"\n  Tags on #{a.alumni_id} {a.full_name}:")
        if not tags:
            print("    (none)")
        for t in tags:
            print(f"    #{t.tag_id:<3} {t.name}")
        all_tags = data.list_all_tags()
        if all_tags:
            print("\n  All tags in system: "
                  + ", ".join(t.name for t in all_tags))
        print("\n    a) Add/attach    r) Remove from alumnus")
        print("    x) Delete tag globally    0) Back")
        try:
            choice = _input("Choice", default="0").lower()
        except _UserAbort:
            return
        if choice in ("0", ""):
            return
        try:
            if choice == "a":
                name = _input("Tag name (new or existing)",
                                allow_empty=False)
                t = data.add_tag(a.alumni_id, name)
                print(f"    ✓ Tagged with '{t.name}'")
            elif choice == "r":
                tid = int(_input("Tag #id to remove from alumnus",
                                    allow_empty=False))
                if data.remove_tag(a.alumni_id, tid):
                    print("    ✓ Removed")
            elif choice == "x":
                tid = int(_input("Tag #id to delete globally",
                                    allow_empty=False))
                if _yes_no("Delete this tag from all alumni?",
                             default=False):
                    if data.delete_tag(tid):
                        print("    ✓ Deleted")
        except _UserAbort:
            print("    Cancelled.")
        except (ValidationError, ValueError) as ex:
            print(f"    ✗ {ex}")


def achievements_flow() -> None:
    print("\n═══ Achievements ═══")
    try:
        a = _pick_alumnus()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    while True:
        rows = data.list_achievements(a.alumni_id)
        print(f"\n  Achievements for #{a.alumni_id} {a.full_name}:")
        if not rows:
            print("    (none)")
        for x in rows:
            dt = f"{x.date}  " if x.date else ""
            cat = f"[{x.category}] " if x.category else ""
            print(f"    #{x.achievement_id:<3} {dt}{cat}{x.title}")
        print("\n    a) Add    e) Edit    d) Delete    0) Back")
        try:
            choice = _input("Choice", default="0").lower()
        except _UserAbort:
            return
        if choice in ("0", ""):
            return
        try:
            if choice == "a":
                category = ""
                if _yes_no("Set category?", default=True):
                    category = _pick_from(
                        "Category", list(ACHIEVEMENT_CATEGORIES),
                        default=ACHIEVEMENT_CATEGORIES[0])
                data.add_achievement(a.alumni_id, {
                    "title":       _input("Title", allow_empty=False),
                    "date":        _input("Date (YYYY-MM-DD)"),
                    "category":    category,
                    "description": _input("Description"),
                    "url":         _input("URL"),
                })
            elif choice == "e":
                aid = int(_input("Edit #id", allow_empty=False))
                cur = next((x for x in rows
                              if x.achievement_id == aid), None)
                if not cur:
                    print("    No such row."); continue
                category = cur.category or ""
                if _yes_no("Change category?", default=False):
                    category = _pick_from(
                        "Category", list(ACHIEVEMENT_CATEGORIES),
                        default=category or ACHIEVEMENT_CATEGORIES[0])
                data.update_achievement(aid, {
                    "title":       _input("Title", default=cur.title),
                    "date":        _input("Date",
                                            default=cur.date or ""),
                    "category":    category,
                    "description": _input("Description",
                                            default=cur.description or ""),
                    "url":         _input("URL", default=cur.url or ""),
                })
            elif choice == "d":
                aid = int(_input("Delete #id", allow_empty=False))
                if data.delete_achievement(aid):
                    print("    ✓ Deleted")
        except _UserAbort:
            print("    Cancelled.")
        except (ValidationError, ValueError) as ex:
            print(f"    ✗ {ex}")


# ── Communications / consent / channels / leavers / portal ───────

def comms_flow() -> None:
    print("\n═══ Communications Log ═══")
    try:
        a = _pick_alumnus()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    while True:
        rows = data.list_communications(a.alumni_id)
        print(f"\n  Comms for #{a.alumni_id} {a.full_name}  "
              f"(bounce_count={a.bounce_count}):")
        if not rows:
            print("    (none)")
        for c in rows[:25]:
            when = (c.sent_at or c.received_at or c.created_at or ""
                      )[:16]
            print(f"    #{c.message_id:<4} {when:<16}  "
                  f"[{c.channel:<18}] {c.status:<10} "
                  f"{(c.subject or '')[:50]}")
        print("\n    a) Add    d) Delete    "
               "b) Record bounce   cb) Clear bounces   0) Back")
        try:
            choice = _input("Choice", default="0").lower()
        except _UserAbort:
            return
        if choice in ("0", ""):
            return
        try:
            if choice == "a":
                data.add_communication(a.alumni_id, {
                    "date":     _input("Date (YYYY-MM-DD)",
                                          default=_date.today().isoformat()),
                    "channel":  _pick_from("Channel",
                                             list(COMM_CHANNELS),
                                             default="Email"),
                    "staff_id": _input("Staff id"),
                    "subject":  _input("Subject"),
                    "summary":  _input("Summary"),
                    "status":   _pick_from("Status",
                                             list(COMM_STATUSES),
                                             default="Sent"),
                })
            elif choice == "d":
                cid = int(_input("Delete #id", allow_empty=False))
                if data.delete_communication(cid):
                    print("    ✓ Deleted")
            elif choice == "b":
                hard = _yes_no("Hard bounce?", default=True)
                reason = _input("Reason / notes")
                a = data.record_bounce(a.alumni_id, hard=hard,
                                         reason=reason or None)
                print(f"    bounce_count now {a.bounce_count} "
                       f"(status={a.status})")
            elif choice == "cb":
                a = data.clear_bounces(a.alumni_id)
                print("    ✓ Cleared")
        except _UserAbort:
            print("    Cancelled.")
        except (ValidationError, ValueError) as ex:
            print(f"    ✗ {ex}")


def send_email_flow() -> None:
    print("\n═══ Send Email ═══")
    print("  Templates support {first_name} {last_name} "
           "{preferred_name} {leaving_year}\n")
    print("  1) Single alumnus")
    print("  2) Filtered bulk send")
    try:
        which = _input("Which?", default="1")
        subject = _input("Subject", allow_empty=False)
        print("  Body (end with a single '.' on its own line):")
        lines: list[str] = []
        while True:
            line = input()
            if line.strip() == ".":
                break
            lines.append(line)
        body = "\n".join(lines)
        staff = _input("Logged-by staff id") or None
        if which == "2":
            year = _input("Leaving year (blank = any)") or None
            dest = _input("Destination type (blank = any)") or None
            sent, skipped = data.send_email_bulk(
                {"leaving_year": year, "destination_type": dest,
                 "status": "Active"},
                subject, body, staff_id=staff)
            print(f"\n  ✓ Sent={sent}  skipped={skipped}")
        else:
            a = _pick_alumnus()
            ok = data.send_email_to_alumnus(
                a.alumni_id, subject, body, staff_id=staff)
            print("\n  ✓ Delivered" if ok
                   else "\n  ! Logged (no shared email infra)")
    except _UserAbort:
        print("\n  Cancelled.")
    except ValidationError as e:
        print(f"\n  ✗ {e}")
    _pause()


def channel_prefs_flow() -> None:
    print("\n═══ Channel Preferences ═══")
    try:
        a = _pick_alumnus()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    p = data.get_channel_prefs(a.alumni_id)
    print(f"\n  Current for #{a.alumni_id} {a.full_name}:")
    print(f"    Email : {'✓' if p.opt_in_email else '✗'}")
    print(f"    Post  : {'✓' if p.opt_in_post  else '✗'}")
    print(f"    Phone : {'✓' if p.opt_in_phone else '✗'}")
    print(f"    SMS   : {'✓' if p.opt_in_sms   else '✗'}")
    try:
        new = data.update_channel_prefs(
            a.alumni_id,
            opt_in_email=_yes_no("Email?",  default=p.opt_in_email),
            opt_in_post= _yes_no("Post?",   default=p.opt_in_post),
            opt_in_phone=_yes_no("Phone?",  default=p.opt_in_phone),
            opt_in_sms=  _yes_no("SMS?",    default=p.opt_in_sms),
        )
        print(f"\n  ✓ Saved.  Legacy opt_in_contact = "
               f"{'on' if any([new.opt_in_email, new.opt_in_post, new.opt_in_phone, new.opt_in_sms]) else 'off'}")
    except _UserAbort:
        print("\n  Cancelled.")
    _pause()


def consent_flow() -> None:
    print("\n═══ GDPR Consent ═══")
    try:
        a = _pick_alumnus()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    while True:
        rows = data.list_consents(a.alumni_id)
        print(f"\n  Consents for #{a.alumni_id} {a.full_name}:")
        if not rows:
            print("    (none)")
        for c in rows:
            state = ("withdrawn " + c.withdrawn_at[:10]
                       if c.withdrawn_at else "active")
            print(f"    #{c.consent_id:<3} {c.scope:<14} {c.version}  "
                  f"granted {c.granted_at[:10]}  [{state}]")
        print("\n    g) Grant    w) Withdraw    0) Back")
        try:
            choice = _input("Choice", default="0").lower()
        except _UserAbort:
            return
        if choice in ("0", ""):
            return
        try:
            if choice == "g":
                scope = _pick_from("Scope", list(CONSENT_SCOPES),
                                     default=CONSENT_SCOPES[0])
                source = _input("Source (e.g. form, email, in person)")
                notes  = _input("Notes")
                data.grant_consent(a.alumni_id, scope,
                                     source=source or None,
                                     notes=notes or None)
            elif choice == "w":
                cid = int(_input("Withdraw consent #id",
                                    allow_empty=False))
                notes = _input("Notes (optional)")
                data.withdraw_consent(cid, notes=notes or None)
        except _UserAbort:
            print("    Cancelled.")
        except (ValidationError, ValueError) as ex:
            print(f"    ✗ {ex}")


def unarchived_leavers_flow() -> None:
    print("\n═══ Unarchived Leavers ═══")
    rows = data.find_unarchived_leavers()
    if not rows:
        print("\n  None found.")
        _pause()
        return
    print(f"\n  {len(rows)} student(s) look like leavers without an "
           "alumni row:\n")
    print(f"  {'Student':<10}  {'Name':<26}  {'UCAS':<6} "
           f"{'Exam':<5}  Destination")
    print("  " + "-" * 92)
    for r in rows:
        print(f"  {r.student_id:<10}  {r.full_name[:26]:<26}  "
              f"{str(r.ucas_cycle_year or '—'):<6} "
              f"{str(r.last_exam_year or '—'):<5}  "
              f"{(r.final_destination or '—')[:40]}")
    print(f"\n  {len(rows)} flagged. Use 'Archive student' "
           "to convert one.")
    _pause()


def retention_flow() -> None:
    print("\n═══ Retention ═══")
    try:
        years = int(_input("Years since last update", default="7"))
    except (ValueError, _UserAbort):
        print("\n  Cancelled.")
        return
    rows = data.find_retention_candidates(years=years)
    if not rows:
        print(f"\n  No alumni inactive for {years}+ years.")
        _pause()
        return
    print(f"\n  {len(rows)} candidate(s):\n")
    for a in rows:
        print(f"    #{a.alumni_id:<4} {a.full_name:<26} "
              f"[{a.status}]  updated {a.updated_at[:10]}")
    print("\n    A) Anonymise one    D) Delete one    0) Back")
    try:
        choice = _input("Choice", default="0").lower()
        if choice == "a":
            aid = int(_input("Alumni #id", allow_empty=False))
            if _yes_no(f"Anonymise #{aid}? (destructive)",
                          default=False):
                data.anonymise_alumnus(aid)
                print("    ✓ Anonymised")
        elif choice == "d":
            aid = int(_input("Alumni #id", allow_empty=False))
            if _yes_no(f"Delete #{aid}? (irreversible)",
                          default=False):
                data.delete_alumnus(aid)
                print("    ✓ Deleted")
    except _UserAbort:
        print("\n  Cancelled.")
    except (ValidationError, ValueError) as ex:
        print(f"  ✗ {ex}")
    _pause()


def portal_token_flow() -> None:
    print("\n═══ Self-Service Portal Token ═══")
    try:
        a = _pick_alumnus()
        ttl = int(_input("TTL days", default="14"))
    except (_UserAbort, ValueError):
        print("\n  Cancelled.")
        return
    try:
        tok = data.create_portal_token(a.alumni_id, ttl_days=ttl)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Token created for #{a.alumni_id} ({a.full_name})")
    print(f"    Token   : {tok.token}")
    print(f"    Expires : {tok.expires_at}")
    print("\n  Share this token with the alumnus so they can "
           "self-update their profile.")
    _pause()


# ── Engagement & programmes ───────────────────────────────────────

def _money_str(pence: int | None) -> str:
    if pence is None:
        return "—"
    return f"£{pence / 100:,.2f}"


def _pick_event() -> int:
    rows = data.list_events()
    if not rows:
        print("    (no events yet)")
        raise _UserAbort
    print("\n  Events:")
    for i, e in enumerate(rows, 1):
        print(f"    {i:>2}) #{e.event_id:<3} {e.name[:40]:<40} "
              f"{e.event_date or '—':<10}  [{e.status}]")
    raw = _input(f"Pick #1..{len(rows)} (or event id)",
                    allow_empty=False)
    n = int(raw) if raw.isdigit() else -1
    if 1 <= n <= len(rows):
        return rows[n - 1].event_id
    match = next((e for e in rows if e.event_id == n), None)
    if match is None:
        raise _UserAbort
    return match.event_id


def _pick_campaign() -> int:
    rows = data.list_campaigns()
    if not rows:
        print("    (no campaigns yet)")
        raise _UserAbort
    print("\n  Campaigns:")
    for i, c in enumerate(rows, 1):
        print(f"    {i:>2}) #{c.campaign_id:<3} {c.name[:40]:<40} "
              f"[{c.status}]  target={_money_str(c.target_pence)}")
    raw = _input(f"Pick #1..{len(rows)} (or campaign id)",
                    allow_empty=False)
    n = int(raw) if raw.isdigit() else -1
    if 1 <= n <= len(rows):
        return rows[n - 1].campaign_id
    match = next((c for c in rows if c.campaign_id == n), None)
    if match is None:
        raise _UserAbort
    return match.campaign_id


def events_flow() -> None:
    print("\n═══ Events ═══")
    while True:
        rows = data.list_events()
        print(f"\n  {len(rows)} event(s):")
        for e in rows[:25]:
            print(f"    #{e.event_id:<3} {e.event_date or '—':<10} "
                  f"[{e.status:<10}] {e.event_type:<14} "
                  f"{e.name[:36]:<36}  cost={_money_str(e.cost_pence)}")
        print("\n    a) Add  e) Edit status  v) View RSVPs  "
               "r) Set RSVP  d) Delete  0) Back")
        try:
            choice = _input("Choice", default="0").lower()
        except _UserAbort:
            return
        if choice in ("0", ""):
            return
        try:
            if choice == "a":
                data.create_event({
                    "name":       _input("Name", allow_empty=False),
                    "event_type": _pick_from("Type", list(EVENT_TYPES),
                                               default=EVENT_TYPES[0]),
                    "event_date": _input("Date (YYYY-MM-DD)"),
                    "location":   _input("Location"),
                    "capacity":   _input("Capacity") or None,
                    "cost":       _input("Cost in £") or 0,
                    "status":     _pick_from(
                        "Status", list(EVENT_STATUSES),
                        default=DEFAULT_EVENT_STATUS),
                    "notes":      _input("Notes"),
                })
            elif choice == "e":
                eid = int(_input("Event #id", allow_empty=False))
                new = _pick_from("New status", list(EVENT_STATUSES),
                                   default=DEFAULT_EVENT_STATUS)
                data.update_event(eid, {"status": new})
            elif choice == "v":
                eid = int(_input("Event #id", allow_empty=False))
                rsvps = data.list_rsvps_for_event(eid)
                att = data.event_attendance(eid)
                print(f"\n  {len(rsvps)} RSVP(s); invited={att.invited} "
                      f"accepted={att.accepted} declined={att.declined} "
                      f"attended={att.attended} (headcount {att.headcount})")
                for r in rsvps:
                    print(f"    rsvp #{r.rsvp_id:<3} alumnus #{r.alumni_id:<3} "
                          f"[{r.status:<10}] guests={r.guests} "
                          f"attended={'✓' if r.attended else ' '}")
                _pause()
            elif choice == "r":
                eid = int(_input("Event #id", allow_empty=False))
                a = _pick_alumnus()
                status = _pick_from("RSVP status",
                                       list(RSVP_STATUSES),
                                       default=DEFAULT_RSVP_STATUS)
                guests = int(_input("Guests", default="0") or 0)
                att = _yes_no("Attended?", default=False)
                data.set_rsvp(eid, a.alumni_id, status=status,
                                guests=guests, attended=att)
            elif choice == "d":
                eid = int(_input("Delete event #id",
                                    allow_empty=False))
                if _yes_no(f"Delete event #{eid} and all RSVPs?",
                             default=False):
                    data.delete_event(eid)
                    print("    ✓ Deleted")
        except _UserAbort:
            print("    Cancelled.")
        except (ValidationError, ValueError) as ex:
            print(f"    ✗ {ex}")


def mentoring_flow() -> None:
    print("\n═══ Mentoring ═══")
    try:
        a = _pick_alumnus()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    while True:
        mships = data.list_mentorships_by_mentor(a.alumni_id)
        print(f"\n  Mentorships by #{a.alumni_id} {a.full_name}:")
        if not mships:
            print("    (none)")
        for m in mships:
            print(f"    #{m.mentorship_id:<3} mentee={m.mentee_student_id:<10} "
                  f"started {m.started_on}  [{m.status}]  "
                  f"{(m.topic or '')[:30]}")
        print("\n    s) Start  l) Sessions  ls) Log session  "
               "e) End  d) Delete  0) Back")
        try:
            choice = _input("Choice", default="0").lower()
        except _UserAbort:
            return
        if choice in ("0", ""):
            return
        try:
            if choice == "s":
                sid = _input("Mentee student id", allow_empty=False)
                data.start_mentorship(a.alumni_id, sid,
                                        topic=_input("Topic"),
                                        notes=_input("Notes"))
            elif choice == "l":
                mid = int(_input("Mentorship #id", allow_empty=False))
                sessions = data.list_mentor_sessions(mid)
                if not sessions:
                    print("    (no sessions)")
                for s in sessions:
                    print(f"    sess #{s.session_id:<3} {s.session_date} "
                          f"{s.duration_minutes or 0}m "
                          f"{s.format or ''}  {(s.summary or '')[:40]}")
                _pause()
            elif choice == "ls":
                mid = int(_input("Mentorship #id", allow_empty=False))
                fmt = ""
                if _yes_no("Set format?", default=True):
                    fmt = _pick_from("Format", list(SESSION_FORMATS),
                                       default="Video")
                data.log_mentor_session(mid, {
                    "session_date":     _input("Date (YYYY-MM-DD)",
                                                  default=_date.today().isoformat()),
                    "duration_minutes": _input("Duration (mins)"),
                    "format":           fmt,
                    "summary":          _input("Summary"),
                    "mentor_feedback":  _input("Mentor feedback"),
                    "mentee_feedback":  _input("Mentee feedback"),
                })
            elif choice == "e":
                mid = int(_input("Mentorship #id", allow_empty=False))
                new = _pick_from("Final status",
                                   list(MENTORSHIP_STATUSES),
                                   default="Completed")
                data.end_mentorship(mid, status=new,
                                      notes=_input("Closing notes"))
            elif choice == "d":
                mid = int(_input("Mentorship #id", allow_empty=False))
                if _yes_no("Delete? Cascades sessions.",
                             default=False):
                    data.delete_mentorship(mid)
        except _UserAbort:
            print("    Cancelled.")
        except (ValidationError, ValueError) as ex:
            print(f"    ✗ {ex}")


def speakers_flow() -> None:
    print("\n═══ Speaker Register ═══")
    print("  1) Browse register   2) Edit one alumnus's profile")
    try:
        which = _input("Choice", default="1")
        if which == "2":
            a = _pick_alumnus()
            cur = data.get_speaker(a.alumni_id)
            print(f"\n  Existing profile: {cur}")
            topics  = _input("Topics (comma-separated)",
                                default=(cur.topics or "") if cur else "")
            years   = _input("Year groups",
                                default=(cur.year_groups or "") if cur else "")
            avail   = _input("Availability notes",
                                default=(cur.availability_notes or "")
                                  if cur else "")
            confirm = _yes_no("Mark as confirmed today?", default=False)
            data.upsert_speaker(a.alumni_id, topics=topics,
                                  year_groups=years,
                                  availability_notes=avail,
                                  confirm=confirm)
            print("\n  ✓ Saved.")
        else:
            topic = _input("Filter: topic contains") or None
            yr    = _input("Filter: year group") or None
            rows = data.list_speakers(topic_like=topic, year_group=yr)
            print(f"\n  {len(rows)} speaker(s):")
            for s in rows:
                al = data.get_alumnus(s.alumni_id)
                if al:
                    print(f"    #{al.alumni_id:<3} {al.full_name:<26}  "
                          f"topics={(s.topics or '')[:30]}  "
                          f"years={(s.year_groups or '')[:12]}  "
                          f"confirmed={s.last_confirmed_at or '—'}")
    except _UserAbort:
        print("\n  Cancelled.")
    except ValidationError as e:
        print(f"  ✗ {e}")
    _pause()


def work_exp_flow() -> None:
    print("\n═══ Work-Experience Offers ═══")
    while True:
        rows = data.list_work_exp_offers()
        print(f"\n  {len(rows)} offer(s):")
        for o in rows[:25]:
            print(f"    #{o.offer_id:<3} alumnus #{o.alumni_id:<3} "
                  f"[{o.status:<8}] {o.title[:30]:<30} @ "
                  f"{(o.employer or '—')[:18]:<18} "
                  f"deadline={o.deadline or '—'}")
        print("\n    a) Add  v) Applicants  app) Apply (student)  "
               "s) Set offer status  ss) Set app status  "
               "d) Delete offer  0) Back")
        try:
            choice = _input("Choice", default="0").lower()
        except _UserAbort:
            return
        if choice in ("0", ""):
            return
        try:
            if choice == "a":
                al = _pick_alumnus()
                sector = ""
                if _yes_no("Set sector?", default=False):
                    sector = _pick_from("Sector", list(SECTORS),
                                          default=SECTORS[0])
                data.add_work_exp_offer(al.alumni_id, {
                    "title":          _input("Title",
                                                allow_empty=False),
                    "employer":       _input("Employer"),
                    "sector":         sector,
                    "location":       _input("Location"),
                    "duration_weeks": _input("Duration (weeks)"),
                    "start_window":   _input("Start window"),
                    "vacancy_count":  _input("Vacancies", default="1"),
                    "requirements":   _input("Requirements"),
                    "deadline":       _input("Deadline (YYYY-MM-DD)"),
                    "notes":          _input("Notes"),
                })
            elif choice == "v":
                oid = int(_input("Offer #id", allow_empty=False))
                apps = data.list_work_exp_applications(oid)
                print(f"\n  {len(apps)} application(s):")
                for ap in apps:
                    print(f"    app #{ap.application_id:<3} "
                          f"{ap.student_id:<10} {ap.applied_on}  "
                          f"[{ap.status}]")
                _pause()
            elif choice == "app":
                oid = int(_input("Offer #id", allow_empty=False))
                sid = _input("Student id", allow_empty=False)
                data.apply_to_work_exp(oid, sid)
            elif choice == "s":
                oid = int(_input("Offer #id", allow_empty=False))
                new = _pick_from("New status",
                                   list(WORK_EXP_STATUSES),
                                   default="Open")
                data.update_work_exp_status(oid, new)
            elif choice == "ss":
                aid = int(_input("Application #id",
                                    allow_empty=False))
                from education_system.post_16.sixthform_system.modules.domain.students.alumni.alumni \
                    import WORK_EXP_APP_STATUSES as _S
                new = _pick_from("New status", list(_S),
                                   default="Submitted")
                data.set_work_exp_application_status(
                    aid, new, notes=_input("Outcome notes"))
            elif choice == "d":
                oid = int(_input("Delete offer #id",
                                    allow_empty=False))
                if _yes_no("Delete? Cascades applications.",
                             default=False):
                    data.delete_work_exp_offer(oid)
        except _UserAbort:
            print("    Cancelled.")
        except (ValidationError, ValueError) as ex:
            print(f"    ✗ {ex}")


def references_flow() -> None:
    print("\n═══ References ═══")
    try:
        a = _pick_alumnus()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    while True:
        rows = data.list_references(a.alumni_id)
        print(f"\n  References for #{a.alumni_id} {a.full_name}:")
        if not rows:
            print("    (none)")
        for r in rows:
            print(f"    #{r.reference_id:<3} {r.ref_type:<9}  "
                  f"requested={r.requested_on or '—':<10} "
                  f"sent={r.sent_on or '—':<10}  "
                  f"{(r.target_name or '')[:30]}")
        print("\n    a) Add  m) Mark sent  d) Delete  0) Back")
        try:
            choice = _input("Choice", default="0").lower()
        except _UserAbort:
            return
        if choice in ("0", ""):
            return
        try:
            if choice == "a":
                data.add_reference(a.alumni_id, {
                    "staff_id":     _input("Staff id (writer)"),
                    "ref_type":     _pick_from("Type",
                                                  list(REFERENCE_TYPES),
                                                  default="Job"),
                    "requested_on": _input("Requested on (YYYY-MM-DD)"),
                    "sent_on":      _input("Sent on (YYYY-MM-DD)"),
                    "target_name":  _input("Target (employer / "
                                              "institution)"),
                    "target_url":   _input("Target URL"),
                    "notes":        _input("Notes"),
                })
            elif choice == "m":
                rid = int(_input("Reference #id", allow_empty=False))
                data.mark_reference_sent(rid)
            elif choice == "d":
                rid = int(_input("Reference #id", allow_empty=False))
                if data.delete_reference(rid):
                    print("    ✓ Deleted")
        except _UserAbort:
            print("    Cancelled.")
        except (ValidationError, ValueError) as ex:
            print(f"    ✗ {ex}")


def volunteering_flow() -> None:
    print("\n═══ Volunteering ═══")
    try:
        a = _pick_alumnus()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    while True:
        rows = data.list_volunteer_hours(a.alumni_id)
        total = data.total_volunteer_hours(a.alumni_id)
        print(f"\n  Volunteer log for #{a.alumni_id} {a.full_name} "
              f"(total {total:g}h):")
        if not rows:
            print("    (none)")
        for v in rows[:25]:
            ev = f" (event #{v.event_id})" if v.event_id else ""
            print(f"    #{v.volunteer_id:<3} {v.activity_date}  "
                  f"{v.hours:>5g}h  {v.activity_type:<18}{ev}")
        print("\n    a) Add  d) Delete  0) Back")
        try:
            choice = _input("Choice", default="0").lower()
        except _UserAbort:
            return
        if choice in ("0", ""):
            return
        try:
            if choice == "a":
                attach_event = None
                if _yes_no("Attach to an event?", default=False):
                    attach_event = _pick_event()
                data.log_volunteer_hours(
                    a.alumni_id,
                    float(_input("Hours", allow_empty=False)),
                    activity_type=_pick_from(
                        "Activity", list(VOLUNTEER_ACTIVITY_TYPES),
                        default="Mock Interview"),
                    activity_date=_input(
                        "Date (YYYY-MM-DD)",
                        default=_date.today().isoformat()),
                    event_id=attach_event,
                    notes=_input("Notes"))
            elif choice == "d":
                vid = int(_input("Entry #id", allow_empty=False))
                if data.delete_volunteer_entry(vid):
                    print("    ✓ Deleted")
        except _UserAbort:
            print("    Cancelled.")
        except (ValidationError, ValueError) as ex:
            print(f"    ✗ {ex}")


def campaigns_flow() -> None:
    print("\n═══ Fundraising Campaigns ═══")
    while True:
        rows = data.list_campaigns()
        print(f"\n  {len(rows)} campaign(s):")
        for c in rows:
            t = data.campaign_totals(c.campaign_id)
            print(f"    #{c.campaign_id:<3} [{c.status:<8}] "
                  f"{c.name[:30]:<30}  raised={_money_str(t.raised_pence)} "
                  f"pledged_open={_money_str(t.pledged_open_pence)} "
                  f"target={_money_str(c.target_pence)}")
        print("\n    a) Add  s) Set status  d) Delete  v) View "
               "donations  0) Back")
        try:
            choice = _input("Choice", default="0").lower()
        except _UserAbort:
            return
        if choice in ("0", ""):
            return
        try:
            if choice == "a":
                data.create_campaign({
                    "name":        _input("Name", allow_empty=False),
                    "description": _input("Description"),
                    "target":      _input("Target in £"),
                    "start_on":    _input("Start (YYYY-MM-DD)"),
                    "end_on":      _input("End (YYYY-MM-DD)"),
                    "status":      _pick_from(
                        "Status", list(CAMPAIGN_STATUSES),
                        default=DEFAULT_CAMPAIGN_STATUS),
                })
            elif choice == "s":
                cid = int(_input("Campaign #id", allow_empty=False))
                new = _pick_from("New status",
                                   list(CAMPAIGN_STATUSES),
                                   default=DEFAULT_CAMPAIGN_STATUS)
                data.update_campaign_status(cid, new)
            elif choice == "d":
                cid = int(_input("Campaign #id", allow_empty=False))
                if _yes_no("Delete? Donations/pledges keep their "
                             "history but lose the campaign link.",
                             default=False):
                    data.delete_campaign(cid)
            elif choice == "v":
                cid = int(_input("Campaign #id", allow_empty=False))
                dons = data.list_donations(campaign_id=cid)
                print(f"\n  {len(dons)} donation(s):")
                for d in dons:
                    print(f"    #{d.donation_id:<4} {d.donation_date} "
                          f"alumnus #{d.alumni_id:<3} "
                          f"{_money_str(d.amount_pence):>10} "
                          f"{'GA' if d.gift_aid else '  '} "
                          f"{(d.payment_method or '—')[:14]:<14}")
                pls = data.list_pledges(campaign_id=cid)
                print(f"\n  {len(pls)} pledge(s):")
                for p in pls:
                    print(f"    #{p.pledge_id:<4} {p.pledged_on} "
                          f"alumnus #{p.alumni_id:<3} "
                          f"{_money_str(p.amount_pence):>10} "
                          f"[{p.status}]")
                _pause()
        except _UserAbort:
            print("    Cancelled.")
        except (ValidationError, ValueError) as ex:
            print(f"    ✗ {ex}")


def donations_flow() -> None:
    print("\n═══ Donations & Pledges ═══")
    try:
        a = _pick_alumnus()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    while True:
        dons = data.list_donations(alumni_id=a.alumni_id)
        pls  = data.list_pledges(alumni_id=a.alumni_id)
        print(f"\n  For #{a.alumni_id} {a.full_name}:")
        print(f"\n  Donations ({len(dons)}):")
        for d in dons[:15]:
            print(f"    #{d.donation_id:<4} {d.donation_date} "
                  f"{_money_str(d.amount_pence):>10}  "
                  f"campaign #{d.campaign_id or '—':<3}  "
                  f"{'GA' if d.gift_aid else '  '} "
                  f"{(d.payment_method or '—')}")
        print(f"\n  Pledges ({len(pls)}):")
        for p in pls[:15]:
            print(f"    #{p.pledge_id:<4} {p.pledged_on} "
                  f"{_money_str(p.amount_pence):>10}  "
                  f"campaign #{p.campaign_id or '—':<3}  "
                  f"[{p.status}]  due={p.due_by or '—'}")
        print("\n    d) Add donation   p) Add pledge   "
               "sp) Set pledge status   xd) Delete donation   "
               "xp) Delete pledge   0) Back")
        try:
            choice = _input("Choice", default="0").lower()
        except _UserAbort:
            return
        if choice in ("0", ""):
            return
        try:
            cid = None
            if choice in ("d", "p"):
                if _yes_no("Attach to a campaign?", default=True):
                    cid = _pick_campaign()
            if choice == "d":
                method = ""
                if _yes_no("Set payment method?", default=True):
                    method = _pick_from(
                        "Payment method", list(PAYMENT_METHODS),
                        default="Card")
                data.record_donation(a.alumni_id, {
                    "amount":         _input("Amount in £",
                                                allow_empty=False),
                    "campaign_id":    cid,
                    "donation_date":  _input(
                        "Date (YYYY-MM-DD)",
                        default=_date.today().isoformat()),
                    "gift_aid":       _yes_no("Gift Aid?",
                                                default=False),
                    "payment_method": method,
                    "anonymous":      _yes_no("Anonymous?",
                                                default=False),
                    "restricted_to":  _input("Restricted to (purpose)"),
                    "notes":          _input("Notes"),
                })
            elif choice == "p":
                data.add_pledge(a.alumni_id, {
                    "amount":      _input("Pledge amount in £",
                                             allow_empty=False),
                    "campaign_id": cid,
                    "pledged_on":  _input(
                        "Pledged on (YYYY-MM-DD)",
                        default=_date.today().isoformat()),
                    "due_by":      _input("Due by (YYYY-MM-DD)"),
                    "status":      _pick_from(
                        "Status", list(PLEDGE_STATUSES),
                        default=DEFAULT_PLEDGE_STATUS),
                    "notes":       _input("Notes"),
                })
            elif choice == "sp":
                pid = int(_input("Pledge #id", allow_empty=False))
                new = _pick_from("New status", list(PLEDGE_STATUSES),
                                   default=DEFAULT_PLEDGE_STATUS)
                data.update_pledge_status(pid, new)
            elif choice == "xd":
                did = int(_input("Donation #id", allow_empty=False))
                if _yes_no("Delete donation? Irreversible.",
                             default=False):
                    data.delete_donation(did)
            elif choice == "xp":
                pid = int(_input("Pledge #id", allow_empty=False))
                if data.delete_pledge(pid):
                    print("    ✓ Deleted")
        except _UserAbort:
            print("    Cancelled.")
        except (ValidationError, ValueError) as ex:
            print(f"    ✗ {ex}")


# ── Reports & analytics ───────────────────────────────────────────

def _ask_year(label: str = "Leaving year (YYYY)") -> str:
    raw = _input(label, allow_empty=False)
    return raw


def report_ks5_csv() -> None:
    print("\n═══ DfE KS5 Destinations CSV ═══")
    try:
        year = _ask_year()
        path = _input("Output path (blank to print)")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        result = data.ks5_destinations_csv(
            leaving_year=year, out_path=path or None)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    if path:
        print(f"\n  ✓ Wrote {result}")
    else:
        print("\n" + result)
    _pause()


def report_sustained() -> None:
    print("\n═══ Sustained Destinations (1y / 3y / 5y) ═══")
    try:
        year = _ask_year()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        rows = data.sustained_destinations(leaving_year=year)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    print(f"\n  Cohort of {year}:")
    print(f"  {'#':>4}  {'Name':<26}  {'+1y':<14} {'+3y':<14} {'+5y':<14}")
    print("  " + "-" * 80)
    for r in rows:
        print(f"  {r.alumni_id:>4}  {r.full_name[:26]:<26}  "
              f"{r.year_plus_1:<14} {r.year_plus_3:<14} "
              f"{r.year_plus_5:<14}")
    _pause()


def report_cohort_comparison() -> None:
    print("\n═══ Cohort Comparison ═══")
    cc = data.cohort_comparison()
    if not cc.years:
        print("\n  (no data)")
        _pause()
        return
    # column widths
    cw = max(len(d) for d in cc.destinations) + 2
    header = "  Year  Total  " + "  ".join(
        f"{d[:cw]:<{cw}}" for d in cc.destinations)
    print()
    print(header)
    print("  " + "-" * (len(header) - 2))
    for y in cc.years:
        cells = []
        for d in cc.destinations:
            n = cc.counts.get(y, {}).get(d, 0)
            cells.append(f"{n:<{cw}}")
        print(f"  {y}  {cc.totals[y]:>5}  " + "  ".join(cells))
    _pause()


def report_university_success() -> None:
    print("\n═══ University Success Rates ═══")
    rows = data.university_success_rates()
    if not rows:
        print("\n  (no university destinations)")
        _pause()
        return
    print(f"\n  {'Year':<6} {'Total':>6} {'Russell':>8} "
          f"{'Oxbridge':>9} {'TopThird':>9}")
    print("  " + "-" * 45)
    for r in rows:
        rp = 100 * r.russell / r.uni_total if r.uni_total else 0
        op = 100 * r.oxbridge / r.uni_total if r.uni_total else 0
        tp = 100 * r.top_third / r.uni_total if r.uni_total else 0
        print(f"  {r.leaving_year:<6} {r.uni_total:>6} "
              f"{r.russell:>3} ({rp:>3.0f}%) "
              f"{r.oxbridge:>3} ({op:>3.0f}%) "
              f"{r.top_third:>3} ({tp:>3.0f}%)")
    _pause()


def report_apprenticeship_outcomes() -> None:
    print("\n═══ Apprenticeship Outcomes ═══")
    rows = data.apprenticeship_outcomes()
    if not rows:
        print("\n  (no apprenticeship destinations)")
        _pause()
        return
    print(f"\n  {'Year':<6} {'Level':<10} {'Provider':<40} {'#':>3}")
    print("  " + "-" * 64)
    for r in rows:
        print(f"  {r.leaving_year:<6} {r.level:<10} "
              f"{r.provider[:40]:<40} {r.count:>3}")
    _pause()


def report_disadvantage_gap() -> None:
    print("\n═══ Disadvantage Gap ═══")
    tag = _input("Tag to compare against cohort",
                    default="Bursary recipient")
    year = _input("Leaving year (blank = all years)")
    try:
        rows = data.disadvantage_gap(
            tag_name=tag,
            leaving_year=year or None)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    print(f"\n  Tag: '{tag}'"
          + (f"  Year: {year}" if year else ""))
    print(f"\n  {'Destination':<16} "
          f"{'Cohort':>8} {'Coh %':>7} "
          f"{'Tagged':>8} {'Tag %':>7} {'Gap':>7}")
    print("  " + "-" * 60)
    for r in rows:
        print(f"  {r.destination_type:<16} "
              f"{r.cohort_count:>8} {r.cohort_pct:>6.1f}% "
              f"{r.tagged_count:>8} {r.tagged_pct:>6.1f}% "
              f"{r.gap_pct:>+6.1f}%")
    _pause()


def report_geographic() -> None:
    print("\n═══ Geographic Distribution ═══")
    rows = data.geographic_distribution()
    if not rows:
        print("\n  (no location data)")
        _pause()
        return
    print(f"\n  {'Country':<24} {'Region':<24} {'#':>5}")
    print("  " + "-" * 60)
    for g in rows:
        print(f"  {g.country[:24]:<24} {g.region[:24]:<24} "
              f"{g.count:>5}")
    _pause()


def report_sector_breakdown() -> None:
    print("\n═══ Sector Breakdown ═══")
    rows = data.sector_breakdown()
    print(f"\n  {'Sector':<24} {'#':>6} {'%':>7}")
    print("  " + "-" * 40)
    for r in rows:
        print(f"  {r.sector[:24]:<24} {r.count:>6} {r.pct:>6.1f}%")
    _pause()


def report_where_are_they_now() -> None:
    print("\n═══ Generate 'Where are they now' site ═══")
    print("  Only alumni with active 'Photo Use' consent are "
           "included.\n")
    try:
        out_dir = _input("Output directory", allow_empty=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        n = data.generate_where_are_they_now(out_dir)
    except Exception as e:
        print(f"  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Wrote {n} profile page(s) + index.html to {out_dir}")
    _pause()


# ── Operational quality ──────────────────────────────────────────

def import_csv_flow() -> None:
    print("\n═══ Bulk CSV Import ═══")
    try:
        path = _input("CSV file path", allow_empty=False)
        rows = data.parse_import_csv(path)
        print(f"\n  Parsed {len(rows)} row(s).")
        if not rows:
            _pause(); return
        suggestion = data.suggest_import_mapping(
            list(rows[0].keys()))
        print("\n  Suggested column mapping:")
        for csv_col, field in suggestion.items():
            print(f"    {csv_col!r:<28} → {field}")
        unknown = [c for c in rows[0] if c not in suggestion]
        if unknown:
            print(f"\n  Unmapped columns: "
                   f"{', '.join(repr(c) for c in unknown)}")
            if _yes_no("Map any of them now?", default=False):
                for col in unknown:
                    target = _input(
                        f"Map {col!r} to (blank to skip)")
                    if target:
                        suggestion[col] = target
        preview = data.preview_import(rows, suggestion)
        print("\n  Dry-run:")
        print(f"    create  : {preview.will_create}")
        print(f"    update  : {preview.will_update}")
        print(f"    skip    : {preview.will_skip}")
        if preview.errors:
            print("\n  First few problems:")
            for ln, msg in preview.errors[:10]:
                print(f"    row {ln}: {msg}")
        if not _yes_no("Commit import?", default=False):
            print("\n  Cancelled.")
            _pause(); return
        actor = _input("Actor / staff id (optional)") or None
        result = data.apply_import(rows, suggestion, actor=actor)
        print(f"\n  ✓ created={result.created}  "
               f"updated={result.updated}  skipped={result.skipped}")
        if result.errors:
            print(f"    + {len(result.errors)} row error(s)")
    except _UserAbort:
        print("\n  Cancelled.")
    except (ValidationError, Exception) as e:
        print(f"  ✗ {e}")
    _pause()


def export_csv_flow() -> None:
    print("\n═══ Bulk CSV Export ═══")
    all_cols = [f for f, _ in data.EXPORT_FIELDS]
    print("  Available columns:")
    for i, c in enumerate(all_cols, 1):
        print(f"    {i:>2}) {c}")
    try:
        picks = _input(
            "Columns (comma-separated numbers, blank = all)")
        out = _input("Output path", allow_empty=False)
        respect = _yes_no(
            "Apply consent-based PII redaction?", default=True)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    cols: list[str] | None = None
    if picks.strip():
        try:
            idxs = [int(p) for p in picks.split(",") if p.strip()]
            cols = [all_cols[i - 1] for i in idxs]
        except (ValueError, IndexError):
            print("  ✗ Bad column selection."); _pause(); return
    try:
        path = data.export_alumni_csv(
            out_path=out, columns=cols, respect_consent=respect)
    except ValidationError as e:
        print(f"  ✗ {e}"); _pause(); return
    print(f"\n  ✓ Wrote {path}")
    _pause()


def dedupe_flow() -> None:
    print("\n═══ Duplicate Detection ═══")
    try:
        thresh = float(
            _input("Similarity threshold (0..1)", default="0.85"))
    except (ValueError, _UserAbort):
        print("\n  Cancelled."); return
    dups = data.find_duplicates(threshold=thresh)
    print(f"\n  {len(dups)} candidate pair(s):")
    for i, d in enumerate(dups, 1):
        print(f"    {i:>2}) {d.score:.2f}  "
              f"#{d.primary.alumni_id} {d.primary.full_name} "
              f"(DOB {d.primary.dob or '—'}) "
              f"⇆ #{d.other.alumni_id} {d.other.full_name} "
              f"(DOB {d.other.dob or '—'})")
    if not dups:
        _pause(); return
    print("\n    m) Merge a pair    0) Back")
    try:
        choice = _input("Choice", default="0").lower()
        if choice == "m":
            n = int(_input("Pair #", allow_empty=False))
            if not (1 <= n <= len(dups)):
                print("  ✗ out of range"); _pause(); return
            d = dups[n - 1]
            print(f"  Will keep #{d.primary.alumni_id} "
                   f"({d.primary.full_name}), absorbing "
                   f"#{d.other.alumni_id}.")
            if not _yes_no("Proceed?", default=False):
                print("  Cancelled."); _pause(); return
            actor = _input("Actor / staff id (optional)") or None
            merged = data.merge_alumni(
                d.primary.alumni_id, d.other.alumni_id, actor=actor)
            print(f"\n  ✓ Merged into #{merged.alumni_id}")
    except _UserAbort:
        print("\n  Cancelled.")
    except (ValidationError, ValueError) as e:
        print(f"  ✗ {e}")
    _pause()


def merge_flow() -> None:
    print("\n═══ Merge Alumni ═══")
    try:
        keep = int(_input("Keep alumnus #id (the survivor)",
                             allow_empty=False))
        other = int(_input("Merge alumnus #id (will be absorbed)",
                              allow_empty=False))
        if not _yes_no(
                f"Merge #{other} into #{keep}? Irreversible.",
                default=False):
            print("  Cancelled."); _pause(); return
        actor = _input("Actor / staff id (optional)") or None
        merged = data.merge_alumni(keep, other, actor=actor)
        print(f"\n  ✓ Merged. Result: #{merged.alumni_id} "
               f"{merged.full_name}")
    except _UserAbort:
        print("\n  Cancelled.")
    except (ValidationError, ValueError) as e:
        print(f"  ✗ {e}")
    _pause()


def audit_log_flow() -> None:
    print("\n═══ Audit Log ═══")
    try:
        a = _pick_alumnus()
    except _UserAbort:
        print("\n  Cancelled."); return
    log = data.list_audit_log(a.alumni_id)
    if not log:
        print("\n  (no audited changes yet)")
        _pause(); return
    print(f"\n  {'When':<19}  {'Who':<14}  {'Field':<22}  Change")
    print("  " + "-" * 90)
    for r in log:
        old = (r['old_value'] or '—')[:18]
        new = (r['new_value'] or '—')[:18]
        print(f"  {r['changed_at']:<19}  {r['changed_by'][:14]:<14}  "
              f"{r['field'][:22]:<22}  {old} → {new}")
    _pause()


def trash_flow() -> None:
    print("\n═══ Soft-Delete Trash ═══")
    rows = data.list_soft_deleted()
    if not rows:
        print("\n  (trash is empty)")
        _pause(); return
    print(f"\n  {len(rows)} soft-deleted alumnus/alumni:")
    for r in rows:
        print(f"    #{r.alumni_id:<3} {r.full_name:<28} "
              f"deleted {r.deleted_at}")
    print("\n    r) Restore   p) Purge one   "
           "P) Purge all expired  0) Back")
    try:
        choice = _input("Choice", default="0").lower()
        if choice == "r":
            aid = int(_input("Alumni #id", allow_empty=False))
            data.restore_alumnus(aid)
            print("    ✓ Restored")
        elif choice == "p":
            aid = int(_input("Alumni #id", allow_empty=False))
            if _yes_no(f"Hard delete #{aid}? Irreversible.",
                         default=False):
                data.purge_alumnus(aid)
                print("    ✓ Purged")
        elif choice == "P":
            days = int(
                _input("Purge entries older than (days)",
                        default=str(data.SOFT_DELETE_UNDO_DAYS)))
            n = data.purge_expired_soft_deletes(undo_days=days)
            print(f"    ✓ Purged {n}")
    except _UserAbort:
        print("\n  Cancelled.")
    except (ValidationError, ValueError) as e:
        print(f"  ✗ {e}")
    _pause()


def saved_searches_flow() -> None:
    print("\n═══ Saved Searches ═══")
    while True:
        rows = data.list_saved_searches()
        print(f"\n  {len(rows)} saved search(es):")
        for s in rows:
            owner = f" [{s.owner_staff_id}]" if s.owner_staff_id else ""
            print(f"    #{s.search_id:<3} {s.name:<28}{owner}  "
                   f"{s.filters}")
        print("\n    s) Save current filter  r) Run  "
               "d) Delete  0) Back")
        try:
            choice = _input("Choice", default="0").lower()
        except _UserAbort:
            return
        if choice in ("0", ""):
            return
        try:
            if choice == "s":
                name = _input("Name", allow_empty=False)
                year = _input("Filter: leaving year") or None
                dest = _input(f"Filter: destination "
                                 f"({'/'.join(DESTINATION_TYPES)})"
                                 ) or None
                emp = _input("Filter: employer contains") or None
                uni = _input("Filter: university contains") or None
                sec = _input("Filter: sector "
                                f"(blank or {SECTORS[0]}…)") or None
                country = _input("Filter: country") or None
                tag = _input("Filter: tag") or None
                opt_in = (_yes_no("Contactable only?", default=False))
                filters: dict[str, Any] = {}
                if year:    filters["leaving_year"] = year
                if dest:    filters["destination_type"] = dest
                if emp:     filters["employer"] = emp
                if uni:     filters["university"] = uni
                if sec:     filters["sector"] = sec
                if country: filters["country"] = country
                if tag:     filters["tag"] = tag
                if opt_in:  filters["contactable_only"] = True
                replace = _yes_no("Replace if name exists?",
                                     default=False)
                staff = _input("Owner staff id (optional)") or None
                data.save_search(name, filters,
                                   owner_staff_id=staff,
                                   replace=replace)
                print("    ✓ Saved")
            elif choice == "r":
                name = _input("Saved-search name",
                                 allow_empty=False)
                results = data.run_saved_search(name)
                _print_alumni(results)
                _pause()
            elif choice == "d":
                name = _input("Saved-search name",
                                 allow_empty=False)
                if data.delete_saved_search(name):
                    print("    ✓ Deleted")
        except _UserAbort:
            print("    Cancelled.")
        except (ValidationError, ValueError) as ex:
            print(f"    ✗ {ex}")


def surveys_flow() -> None:
    print("\n═══ Surveys ═══")
    while True:
        rows = data.list_surveys()
        print(f"\n  {len(rows)} survey(s):")
        for s in rows:
            stats = data.survey_stats(s.survey_id)
            print(f"    #{s.survey_id:<3} [{s.status:<7}] "
                  f"{s.name[:30]:<30}  "
                  f"inv={stats.invited} sent={stats.sent} "
                  f"completed={stats.completed}")
        print("\n    a) Create  i) Invite cohort  v) View responses  "
               "c) Close  d) Delete  0) Back")
        try:
            choice = _input("Choice", default="0").lower()
        except _UserAbort:
            return
        if choice in ("0", ""):
            return
        try:
            if choice == "a":
                name = _input("Survey name", allow_empty=False)
                desc = _input("Description")
                print("  Add questions one per line. Format:")
                print("    key | prompt | type")
                print(f"    types: {', '.join(sorted(data.SURVEY_QUESTION_TARGETS))}")
                print("  End with a blank line.")
                qs: list[dict[str, Any]] = []
                while True:
                    line = _input("Question",
                                     default="").strip()
                    if not line:
                        break
                    parts = [p.strip() for p in line.split("|")]
                    if len(parts) < 2:
                        print("    Need at least key | prompt"); continue
                    qkey = parts[0]
                    qprompt = parts[1]
                    qtype = parts[2] if len(parts) >= 3 else "freeform"
                    qs.append({"key": qkey, "prompt": qprompt,
                                 "type": qtype})
                if not qs:
                    print("  No questions — cancelled."); continue
                s = data.create_survey(name, qs,
                                          description=desc or None)
                print(f"    ✓ Created survey #{s.survey_id}")
            elif choice == "i":
                sid = int(_input("Survey #id", allow_empty=False))
                year = _input("Filter: leaving year") or None
                staff = _input("Sender staff id (optional)") or None
                filters: dict[str, Any] = {"status": "Active"}
                if year:
                    filters["leaving_year"] = year
                sent, skipped = data.send_survey_invitations(
                    sid, filters, staff_id=staff)
                print(f"    ✓ sent={sent}  skipped={skipped}")
            elif choice == "v":
                sid = int(_input("Survey #id", allow_empty=False))
                resps = data.list_survey_responses(sid)
                print(f"\n  {len(resps)} response(s):")
                for r in resps:
                    print(f"    resp #{r.response_id:<3} "
                          f"inv #{r.invitation_id:<3}  {r.submitted_at}")
                    for k, v in r.answers.items():
                        print(f"      {k}: {v}")
                _pause()
            elif choice == "c":
                sid = int(_input("Survey #id", allow_empty=False))
                data.close_survey(sid)
                print("    ✓ Closed")
            elif choice == "d":
                sid = int(_input("Survey #id", allow_empty=False))
                if _yes_no("Delete survey + invitations + "
                             "responses?", default=False):
                    data.delete_survey(sid)
                    print("    ✓ Deleted")
        except _UserAbort:
            print("    Cancelled.")
        except (ValidationError, ValueError) as ex:
            print(f"    ✗ {ex}")


# ── Engagement extensions (items 1–8) ─────────────────────────────

def social_handles_flow() -> None:
    print("\n═══ Social handles ═══")
    a = _pick_alumnus()
    while True:
        rows = data.list_social_handles(a.alumni_id)
        print(f"\n  {a.full_name} — social handles:")
        if rows:
            print(f"  {'#':>4}  {'Platform':<13}  {'Handle':<24}  Ver  URL")
            for s in rows:
                print(f"  {s.handle_id:>4}  {s.platform:<13}  "
                      f"{s.handle[:24]:<24}  "
                      f"{'✓' if s.verified else ' '}    "
                      f"{(s.url or '')[:40]}")
        else:
            print("  (none)")
        print("\n  1) Add  2) Edit  3) Verify  4) Delete  0) Back")
        try:
            ch = _input("Select", default="0")
        except _UserAbort:
            return
        if ch == "0":
            return
        try:
            if ch == "1":
                plat = _pick_from("Platform", list(SOCIAL_PLATFORMS))
                handle = _input("Handle", allow_empty=False)
                url = _input("URL") or None
                verified = _yes_no("Verified now?", default=False)
                data.add_social_handle(a.alumni_id, plat, handle,
                                          url=url, verified=verified)
                print("    ✓ Added")
            elif ch in ("2", "3", "4"):
                hid_raw = _input("Handle id", allow_empty=False)
                if not hid_raw.isdigit():
                    print("    Not a number."); continue
                hid = int(hid_raw)
                if ch == "2":
                    h = _input("New handle (blank to keep)")
                    u = _input("New URL (blank to keep)")
                    notes = _input("Notes (blank to keep)")
                    payload: dict[str, Any] = {}
                    if h: payload["handle"] = h
                    if u: payload["url"] = u
                    if notes: payload["notes"] = notes
                    if payload:
                        data.update_social_handle(hid, payload)
                        print("    ✓ Updated")
                elif ch == "3":
                    data.verify_social_handle(hid)
                    print("    ✓ Verified")
                else:
                    if _yes_no(f"Delete handle #{hid}?", default=False):
                        data.delete_social_handle(hid)
                        print("    ✓ Deleted")
        except (ValidationError, ValueError) as e:
            print(f"    ✗ {e}")
        except _UserAbort:
            print("    Cancelled.")


def connections_flow() -> None:
    print("\n═══ Connections ═══")
    a = _pick_alumnus()
    while True:
        rows = data.list_connections(a.alumni_id)
        print(f"\n  {a.full_name} — connections ({len(rows)}):")
        for c, other in rows:
            print(f"   #{c.connection_id}  → #{other.alumni_id} "
                  f"{other.full_name}  ({c.kind})")
        print("\n  1) Connect to another alumnus  2) Disconnect")
        print("  3) Mutuals with another  4) Degrees-between  0) Back")
        try:
            ch = _input("Select", default="0")
        except _UserAbort:
            return
        if ch == "0":
            return
        try:
            if ch == "1":
                b = _pick_alumnus()
                kind = _pick_from("Kind", list(CONNECTION_KINDS),
                                     default="Friend")
                since = _input("Since (YYYY-MM-DD, optional)") or None
                notes = _input("Notes (optional)") or None
                data.connect_alumni(a.alumni_id, b.alumni_id,
                                       kind=kind, since=since, notes=notes)
                print("    ✓ Connected")
            elif ch == "2":
                b = _pick_alumnus()
                if data.disconnect_alumni(a.alumni_id, b.alumni_id):
                    print("    ✓ Disconnected")
                else:
                    print("    No such connection.")
            elif ch == "3":
                b = _pick_alumnus()
                mutuals = data.mutuals_of(a.alumni_id, b.alumni_id)
                if not mutuals:
                    print("    (no mutuals)")
                else:
                    for m in mutuals:
                        print(f"    #{m.alumni_id}  {m.full_name}")
            elif ch == "4":
                b = _pick_alumnus()
                d = data.degrees_between(a.alumni_id, b.alumni_id)
                print(f"    Degrees: "
                      f"{'(unconnected within 6)' if d is None else d}")
        except (ValidationError, ValueError) as e:
            print(f"    ✗ {e}")
        except _UserAbort:
            print("    Cancelled.")


def _pick_chapter() -> int:
    rows = data.list_chapters()
    if not rows:
        print("    No chapters."); raise _UserAbort
    print("\n  Chapters:")
    for i, c in enumerate(rows, 1):
        print(f"    {i:>3}) #{c.chapter_id}  {c.name}  "
              f"[{c.kind}, {c.status}]")
    raw = _input(f"  Pick #1..{len(rows)} (or chapter id)",
                   allow_empty=False)
    if raw.isdigit():
        n = int(raw)
        if 1 <= n <= len(rows):
            return rows[n - 1].chapter_id
        match = next((c for c in rows if c.chapter_id == n), None)
        if match:
            return match.chapter_id
    raise _UserAbort


def chapters_flow() -> None:
    print("\n═══ Chapters ═══")
    while True:
        print("\n  1) List  2) Create  3) Edit  4) Delete")
        print("  5) View members  6) Add member  7) Set role  8) Remove member")
        print("  0) Back")
        try:
            ch = _input("Select", default="0")
        except _UserAbort:
            return
        if ch == "0":
            return
        try:
            if ch == "1":
                for c in data.list_chapters():
                    print(f"   #{c.chapter_id:>3}  {c.name:<30}  "
                          f"[{c.kind}/{c.status}]  {c.region or '—'}")
            elif ch == "2":
                name = _input("Name", allow_empty=False)
                kind = _pick_from("Kind", list(CHAPTER_KINDS),
                                     default="Regional")
                region = _input("Region (optional)") or None
                desc = _input("Description (optional)") or None
                c = data.create_chapter(name, kind=kind,
                                           region=region, description=desc)
                print(f"    ✓ Created #{c.chapter_id}")
            elif ch == "3":
                cid = _pick_chapter()
                name = _input("New name (blank to keep)")
                region = _input("New region (blank to keep)")
                desc = _input("New description (blank to keep)")
                status = _input("New status (Active/Archived, blank to keep)")
                payload: dict[str, Any] = {}
                if name: payload["name"] = name
                if region: payload["region"] = region
                if desc: payload["description"] = desc
                if status: payload["status"] = status
                if payload:
                    data.update_chapter(cid, payload)
                    print("    ✓ Updated")
            elif ch == "4":
                cid = _pick_chapter()
                if _yes_no(f"Delete chapter #{cid} (members "
                              "are removed)?", default=False):
                    data.delete_chapter(cid)
                    print("    ✓ Deleted")
            elif ch == "5":
                cid = _pick_chapter()
                inc = _yes_no("Include former members?", default=False)
                for cm, al in data.list_chapter_members(
                        cid, include_left=inc):
                    tag = f" (left {cm.left_on})" if cm.left_on else ""
                    print(f"    #{al.alumni_id}  {al.full_name:<28}  "
                          f"{cm.role}{tag}")
            elif ch == "6":
                cid = _pick_chapter()
                a = _pick_alumnus()
                role = _pick_from("Role", list(CHAPTER_ROLES),
                                     default="Member")
                joined = _input("Joined on (YYYY-MM-DD, optional)") or None
                data.add_chapter_member(cid, a.alumni_id,
                                           role=role, joined_on=joined)
                print("    ✓ Added")
            elif ch == "7":
                cid = _pick_chapter()
                a = _pick_alumnus()
                role = _pick_from("Role", list(CHAPTER_ROLES))
                data.set_chapter_role(cid, a.alumni_id, role)
                print("    ✓ Role updated")
            elif ch == "8":
                cid = _pick_chapter()
                a = _pick_alumnus()
                hard = _yes_no("Hard-delete (no audit trail)?",
                                  default=False)
                if hard:
                    data.purge_chapter_member(cid, a.alumni_id)
                else:
                    data.remove_chapter_member(cid, a.alumni_id)
                print("    ✓ Removed")
        except (ValidationError, ValueError) as e:
            print(f"    ✗ {e}")
        except _UserAbort:
            print("    Cancelled.")


def engagement_flow() -> None:
    print("\n═══ Engagement score ═══")
    print("  1) Score one alumnus  2) Leaderboard  0) Back")
    try:
        ch = _input("Select", default="0")
    except _UserAbort:
        return
    try:
        if ch == "1":
            a = _pick_alumnus()
            s = data.compute_engagement_score(a.alumni_id)
            print(f"\n  {a.full_name}: score = {s.score}")
            print(f"    decay={s.decay}  "
                  f"months_since_contact={s.months_since_contact}")
            print(f"    opens={s.comms_opens}  "
                  f"events_attended={s.events_attended}  "
                  f"donations={s.donations_count} "
                  f"({_money_str(s.donation_total_pence)})  "
                  f"volunteer_hrs={s.volunteer_hours}")
        elif ch == "2":
            year = _input("Leaving year filter (blank = all)") or None
            n = int(_input("How many", default="20") or "20")
            rows = data.engagement_leaderboard(limit=n, leaving_year=year)
            with _connect_alumni_lookup() as lookup:
                for r in rows:
                    name = lookup.get(r.alumni_id, f"#{r.alumni_id}")
                    print(f"  {r.score:>7.1f}  {name}")
    except (ValidationError, ValueError) as e:
        print(f"    ✗ {e}")
    except _UserAbort:
        print("    Cancelled.")
    _pause()


class _connect_alumni_lookup:
    """Tiny context manager that caches alumni id→name for one report."""

    def __enter__(self) -> dict[int, str]:
        self._cache = {a.alumni_id: a.full_name
                          for a in data.list_alumni()}
        return self._cache

    def __exit__(self, *a) -> None:
        self._cache.clear()


def re_engagement_flow() -> None:
    print("\n═══ Re-engagement worklist ═══")
    try:
        thr = float(_input("Score threshold", default="5") or "5")
        months = int(_input("Months quiet", default="18") or "18")
        year = _input("Leaving year filter (blank = all)") or None
        lim = int(_input("Max results", default="50") or "50")
    except _UserAbort:
        return
    cands = data.re_engagement_worklist(
        score_threshold=thr, months_quiet=months,
        leaving_year=year, limit=lim)
    if not cands:
        print("  (none)")
    else:
        for c in cands:
            print(f"  {c.score:>6.1f}  #{c.alumnus.alumni_id:<5} "
                  f"{c.alumnus.full_name:<28}  "
                  f"{c.alumnus.leaving_year or '—':<6}  "
                  f"— {c.reason}")
    _pause()


def milestones_flow() -> None:
    print("\n═══ Upcoming milestones ═══")
    try:
        days = int(_input("Days ahead", default="30") or "30")
    except _UserAbort:
        return
    rows = data.upcoming_milestones(days=days)
    if not rows:
        print("  (none)")
    else:
        for m in rows:
            extra = f" ({m.years}y)" if m.years else ""
            tail = f" — {m.detail}" if m.detail else ""
            print(f"  {m.when}  {m.kind:<22}{extra:<5}  "
                  f"#{m.alumni_id:<5} {m.full_name}{tail}")
    _pause()


def lost_contact_flow() -> None:
    print("\n═══ Lost-contact / find-a-friend queue ═══")
    try:
        thr = int(_input("Hard-bounce threshold",
                            default=str(
                                data.HARD_BOUNCE_THRESHOLD)) or "3")
        need_no_phone = _yes_no("Require no phone too?", default=True)
    except _UserAbort:
        return
    rows = data.lost_contact_queue(
        bounce_threshold=thr, require_no_phone=need_no_phone)
    if not rows:
        print("  (none)")
    else:
        for c in rows:
            a = c.alumnus
            print(f"  #{a.alumni_id:<5} {a.full_name:<28} "
                  f"bounces={c.bounce_count}  "
                  f"email={'Y' if c.has_email else 'N'}  "
                  f"phone={'Y' if c.has_phone else 'N'}  "
                  f"addr={'Y' if c.has_address else 'N'}  "
                  f"last={a.last_contacted or '—'}")
    _pause()


def directory_flow() -> None:
    print("\n═══ Public directory ═══")
    print("  1) Opt-in alumnus  2) Opt-out alumnus  3) Check status")
    print("  4) Browse public directory  0) Back")
    try:
        ch = _input("Select", default="0")
    except _UserAbort:
        return
    try:
        if ch in ("1", "2", "3"):
            a = _pick_alumnus()
            if ch == "1":
                data.opt_in_directory(a.alumni_id,
                                         source="cli",
                                         actor="cli")
                print("    ✓ Opted in to public directory")
            elif ch == "2":
                n = data.opt_out_directory(a.alumni_id, actor="cli")
                print(f"    ✓ Withdrew {n} consent record(s)")
            else:
                print("    listed: "
                      f"{'YES' if data.is_in_directory(a.alumni_id) else 'NO'}")
        elif ch == "4":
            year = _input("Leaving year (blank = all)") or None
            sector = _input("Sector (blank = all)") or None
            q = _input("Search query (blank = all)") or None
            rows = data.list_public_directory(
                leaving_year=year, sector=sector, q=q)
            if not rows:
                print("  (none)")
            else:
                for d in rows:
                    print(f"  #{d.alumni_id:<5} {d.display_name:<28} "
                          f"{d.leaving_year or '—':<6}  "
                          f"{(d.current_role or '—'):<22}  "
                          f"{(d.current_employer or '—'):<22}  "
                          f"{d.current_sector or '—'}")
    except (ValidationError, ValueError) as e:
        print(f"    ✗ {e}")
    except _UserAbort:
        print("    Cancelled.")
    _pause()


# ── Career-cluster extensions (items 9–16) ────────────────────────

def skills_flow() -> None:
    print("\n═══ Skills ═══")
    a = _pick_alumnus()
    while True:
        rows = data.list_skills_for(a.alumni_id)
        print(f"\n  {a.full_name} — skills:")
        if rows:
            for s in rows:
                yrs = f" ({s.years}y)" if s.years else ""
                print(f"   #{s.skill_id:>3}  {s.skill_name:<24} "
                      f"{s.proficiency:<14}{yrs}")
        else:
            print("   (none)")
        print("\n  1) Add  2) Remove  3) Find alumni by skill  0) Back")
        try:
            ch = _input("Select", default="0")
        except _UserAbort:
            return
        if ch == "0":
            return
        try:
            if ch == "1":
                name = _input("Skill name", allow_empty=False)
                prof = _pick_from("Proficiency",
                                     list(PROFICIENCY_LEVELS),
                                     default="Intermediate")
                yrs_raw = _input("Years of experience (blank=none)")
                yrs = float(yrs_raw) if yrs_raw else None
                data.add_skill_to_alumnus(
                    a.alumni_id, name,
                    proficiency=prof, years=yrs)
                print("    ✓ Added")
            elif ch == "2":
                sid_raw = _input("Skill id to remove", allow_empty=False)
                if sid_raw.isdigit():
                    data.remove_skill_from_alumnus(a.alumni_id,
                                                       int(sid_raw))
                    print("    ✓ Removed")
            elif ch == "3":
                name = _input("Skill name to search",
                                 allow_empty=False)
                min_prof = _input(
                    "Min proficiency (blank=any)") or None
                rows = data.find_alumni_by_skill(
                    name, min_proficiency=min_prof)
                if not rows:
                    print("    (no matches)")
                else:
                    for x in rows:
                        print(f"   #{x.alumni_id:<5} {x.full_name}")
        except (ValidationError, ValueError) as e:
            print(f"    ✗ {e}")
        except _UserAbort:
            print("    Cancelled.")


def soc_flow() -> None:
    print("\n═══ SOC/NAICS classification ═══")
    while True:
        print("\n  1) Classify a title  2) Cohort breakdown")
        print("  3) Add SOC pattern  0) Back")
        try:
            ch = _input("Select", default="0")
        except _UserAbort:
            return
        if ch == "0":
            return
        try:
            if ch == "1":
                t = _input("Job title", allow_empty=False)
                cls = data.soc_classify(t)
                if cls:
                    print(f"    SOC {cls[0]}: {cls[1]}  "
                          f"(NAICS {cls[2] or '—'})")
                else:
                    print("    Unclassified")
            elif ch == "2":
                year = _input("Leaving year (blank=all)") or None
                for code, label, n in data.soc_breakdown(
                        leaving_year=year):
                    print(f"   {code:>5}  {label:<48}  {n}")
            elif ch == "3":
                pattern = _input("Pattern (substring)",
                                    allow_empty=False)
                soc = _input("SOC code", allow_empty=False)
                lbl = _input("SOC label", allow_empty=False)
                naics = _input("NAICS code (optional)") or None
                data.upsert_soc_pattern(pattern, soc, lbl,
                                            naics_code=naics)
                print("    ✓ Saved")
        except (ValidationError, ValueError) as e:
            print(f"    ✗ {e}")
        except _UserAbort:
            print("    Cancelled.")


def salary_band_report_flow() -> None:
    print("\n═══ Salary band breakdown ═══")
    try:
        year = _input("Leaving year (blank=all)") or None
        sector = _input("Sector (blank=all)") or None
    except _UserAbort:
        return
    rows = data.salary_band_breakdown(
        leaving_year=year, sector=sector)
    if not rows:
        print("  (no banded data)")
    else:
        for r in rows:
            print(f"   {r.band:<18}  {r.count:>4}  {r.pct:5.1f}%")
        med = data.median_salary_band(leaving_year=year, sector=sector)
        print(f"   median: {med or '—'}")
    _pause()


def promotion_timeline_flow() -> None:
    print("\n═══ Promotion timeline ═══")
    a = _pick_alumnus()
    steps = data.promotion_timeline(a.alumni_id)
    if not steps:
        print("   (no career history)")
    else:
        prev = None
        for s in steps:
            arrow = " → "
            promo = ""
            if prev and prev.role != s.role:
                promo = "  (move)"
            print(f"   {s.start_date or '—':<10}{arrow}"
                  f"{s.role:<26} @ {s.employer:<22}"
                  f"{'  [current]' if s.is_current else ''}{promo}")
            prev = s
    _pause()


def employers_flow() -> None:
    print("\n═══ Employer directory ═══")
    while True:
        print("\n  1) List  2) Add / update  3) Add alias")
        print("  4) Resolve a name  5) Top employers  6) Delete  0) Back")
        try:
            ch = _input("Select", default="0")
        except _UserAbort:
            return
        if ch == "0":
            return
        try:
            if ch == "1":
                for e in data.list_employers():
                    print(f"   #{e.employer_id:>3}  "
                          f"{e.canonical_name:<32}  "
                          f"{e.sector or '—':<18}  {e.country or '—'}")
            elif ch == "2":
                name = _input("Canonical name", allow_empty=False)
                sector = _input("Sector (optional)") or None
                website = _input("Website (optional)") or None
                country = _input("Country (optional)") or None
                e = data.upsert_employer(name, sector=sector,
                                             website=website,
                                             country=country)
                print(f"    ✓ #{e.employer_id} saved")
            elif ch == "3":
                eid_raw = _input("Employer id", allow_empty=False)
                if not eid_raw.isdigit():
                    print("    Not a number."); continue
                alias = _input("Alias", allow_empty=False)
                data.add_employer_alias(alias, int(eid_raw))
                print("    ✓ Added alias")
            elif ch == "4":
                name = _input("Name to resolve", allow_empty=False)
                e = data.resolve_employer(name)
                print(f"    → {e.canonical_name if e else '(not mapped)'}")
            elif ch == "5":
                lim = int(_input("Limit", default="25") or "25")
                year = _input("Leaving year (blank=all)") or None
                for r in data.top_employers(limit=lim, leaving_year=year):
                    print(f"   {r.alumni_count:>4}  {r.employer}")
            elif ch == "6":
                eid_raw = _input("Employer id to delete",
                                    allow_empty=False)
                if eid_raw.isdigit() and _yes_no(
                        f"Delete employer #{eid_raw}?", default=False):
                    data.delete_employer(int(eid_raw))
                    print("    ✓ Deleted")
        except (ValidationError, ValueError) as e:
            print(f"    ✗ {e}")
        except _UserAbort:
            print("    Cancelled.")


def jobs_flow() -> None:
    print("\n═══ Alumni job postings ═══")
    while True:
        print("\n  1) List open  2) Post (per alumnus)  3) View applicants")
        print("  4) Set status  5) Apply (alumnus)  6) Delete  0) Back")
        try:
            ch = _input("Select", default="0")
        except _UserAbort:
            return
        if ch == "0":
            return
        try:
            if ch == "1":
                rows = data.list_jobs()
                if not rows:
                    print("   (none)")
                for j in rows:
                    print(f"   #{j.job_id:>4}  {j.title:<28} "
                          f"@ {j.employer or '—':<20}  "
                          f"[{j.job_type}/{j.status}]")
            elif ch == "2":
                a = _pick_alumnus()
                payload = {
                    "title": _input("Title", allow_empty=False),
                    "employer": _input("Employer") or None,
                    "sector": _input("Sector") or None,
                    "location": _input("Location") or None,
                    "job_type": _pick_from("Job type",
                                              list(JOB_TYPES),
                                              default="Graduate"),
                    "salary_band": _input("Salary band (optional)")
                                       or None,
                    "description": _input("Description") or None,
                    "apply_url": _input("Apply URL") or None,
                    "deadline": _input("Deadline (YYYY-MM-DD)") or None,
                }
                j = data.post_job(a.alumni_id, payload)
                print(f"    ✓ Posted job #{j.job_id}")
            elif ch == "3":
                jid = int(_input("Job id", allow_empty=False))
                for r in data.list_job_applications(jid):
                    print(f"   #{r.application_id:>4}  "
                          f"{r.applicant_kind}:{r.applicant_id:<12} "
                          f"{r.applied_on}  [{r.status}]")
            elif ch == "4":
                jid = int(_input("Job id", allow_empty=False))
                status = _pick_from("Status", list(JOB_STATUSES))
                data.set_job_status(jid, status)
                print("    ✓ Updated")
            elif ch == "5":
                jid = int(_input("Job id", allow_empty=False))
                a = _pick_alumnus()
                data.apply_to_job(jid, applicant_id=str(a.alumni_id))
                print("    ✓ Applied")
            elif ch == "6":
                jid = int(_input("Job id", allow_empty=False))
                if _yes_no(f"Delete job #{jid}?", default=False):
                    data.delete_job(jid)
                    print("    ✓ Deleted")
        except (ValidationError, ValueError) as e:
            print(f"    ✗ {e}")
        except _UserAbort:
            print("    Cancelled.")


def internships_flow() -> None:
    print("\n═══ Internships board ═══")
    while True:
        print("\n  1) List open  2) Post (per alumnus)  3) Applicants")
        print("  4) Set status  5) Apply (student)  6) Delete  0) Back")
        try:
            ch = _input("Select", default="0")
        except _UserAbort:
            return
        if ch == "0":
            return
        try:
            if ch == "1":
                for i in data.list_internships():
                    paid = "PAID" if i.paid else "unpaid"
                    print(f"   #{i.internship_id:>4}  {i.title:<28} "
                          f"@ {i.employer or '—':<20}  "
                          f"[{paid}/{i.status}]  "
                          f"{i.duration_weeks or '?'}w")
            elif ch == "2":
                a = _pick_alumnus()
                paid = _yes_no("Paid?", default=True)
                payload = {
                    "title": _input("Title", allow_empty=False),
                    "employer": _input("Employer") or None,
                    "sector": _input("Sector") or None,
                    "location": _input("Location") or None,
                    "duration_weeks": _input("Duration weeks") or None,
                    "paid": paid,
                    "start_window": _input("Start window") or None,
                    "requirements": _input("Requirements") or None,
                    "apply_url": _input("Apply URL") or None,
                    "deadline": _input("Deadline (YYYY-MM-DD)") or None,
                }
                if paid:
                    p = _input("Hourly pay £ (e.g. 12.50)") or None
                    if p:
                        payload["hourly_pay"] = p
                ip = data.post_internship(a.alumni_id, payload)
                print(f"    ✓ Posted internship #{ip.internship_id}")
            elif ch == "3":
                iid = int(_input("Internship id", allow_empty=False))
                for r in data.list_internship_applications(iid):
                    print(f"   #{r.application_id:>4}  "
                          f"{r.student_id:<12} {r.applied_on}  "
                          f"[{r.status}]")
            elif ch == "4":
                iid = int(_input("Internship id", allow_empty=False))
                status = _pick_from("Status",
                                       list(JOB_STATUSES))
                data.set_internship_status(iid, status)
                print("    ✓ Updated")
            elif ch == "5":
                iid = int(_input("Internship id", allow_empty=False))
                sid = _pick_student()
                data.apply_to_internship(iid, sid)
                print("    ✓ Applied")
            elif ch == "6":
                iid = int(_input("Internship id", allow_empty=False))
                if _yes_no(f"Delete internship #{iid}?", default=False):
                    data.delete_internship(iid)
                    print("    ✓ Deleted")
        except (ValidationError, ValueError) as e:
            print(f"    ✗ {e}")
        except _UserAbort:
            print("    Cancelled.")


def mentor_match_flow() -> None:
    print("\n═══ Mentor matching ═══")
    sid = _pick_student()
    try:
        lim = int(_input("Max matches", default="10") or "10")
        require_consent = _yes_no("Require Mentoring consent?",
                                      default=True)
    except _UserAbort:
        return
    rows = data.match_mentors_for_student(
        sid, limit=lim, require_consent=require_consent)
    if not rows:
        print("   (no matches)")
    else:
        for m in rows:
            print(f"   {m.score:>6.1f}  #{m.alumnus.alumni_id:<5} "
                  f"{m.alumnus.full_name:<26}  — "
                  f"{', '.join(m.reasons) or '—'}")
    _pause()


# ── Mentor + comms extensions (items 17–26) ───────────────────────

def mentor_profile_flow() -> None:
    print("\n═══ Mentor profile (capacity & availability) ═══")
    a = _pick_alumnus()
    p = data.get_mentor_profile(a.alumni_id)
    if p:
        print(f"  current: max={p.max_mentees}  "
              f"from={p.available_from or '—'}  "
              f"until={p.available_until or '—'}  "
              f"paused={p.paused}")
    try:
        mx = int(_input("max_mentees", default=str(p.max_mentees if p else 3)))
        af = _input("available_from (YYYY-MM-DD, blank=keep)") or \
            (p.available_from if p else None)
        au = _input("available_until (YYYY-MM-DD, blank=keep)") or \
            (p.available_until if p else None)
        paused = _yes_no("paused?", default=bool(p.paused) if p else False)
        bio = _input("bio (blank=keep)") or (p.bio if p else None)
    except _UserAbort:
        return
    try:
        out = data.upsert_mentor_profile(a.alumni_id, max_mentees=mx,
            available_from=af, available_until=au, paused=paused, bio=bio)
        print(f"  ✓ saved. capacity now: "
              f"{'yes' if data.mentor_has_capacity(out.alumni_id) else 'no'}")
        print(f"  active mentees: {data.active_mentee_count(out.alumni_id)}")
    except (ValidationError, ValueError) as e:
        print(f"  ✗ {e}")
    _pause()


def mentor_rate_flow() -> None:
    print("\n═══ Rate a mentor session ═══")
    try:
        sid = int(_input("session id", allow_empty=False))
        mr_raw = _input("mentee rating 1-5 (blank=skip)")
        gr_raw = _input("mentor rating 1-5 (blank=skip)")
        mf = _input("mentor feedback (blank=skip)") or None
        bf = _input("mentee feedback (blank=skip)") or None
    except (_UserAbort, ValueError):
        return
    try:
        data.rate_mentor_session(sid,
            mentee_rating=int(mr_raw) if mr_raw else None,
            mentor_rating=int(gr_raw) if gr_raw else None,
            mentor_feedback=mf, mentee_feedback=bf)
        print("  ✓ rated")
    except (ValidationError, ValueError) as e:
        print(f"  ✗ {e}")
    _pause()


def mentor_safeguarding_flow() -> None:
    print("\n═══ Mentor safeguarding ═══")
    print("  1) Set / update record  2) View alerts  0) Back")
    try:
        ch = _input("Select", default="0")
    except _UserAbort:
        return
    if ch == "0":
        return
    try:
        if ch == "1":
            a = _pick_alumnus()
            ref = _input("DBS reference") or None
            iss = _input("DBS issued (YYYY-MM-DD)") or None
            exp = _input("DBS expires (YYYY-MM-DD)") or None
            tdone = _input("Training done (YYYY-MM-DD)") or None
            texp = _input("Training expires (YYYY-MM-DD)") or None
            sg = data.upsert_mentor_safeguarding(a.alumni_id,
                dbs_reference=ref, dbs_issued_on=iss,
                dbs_expires_on=exp, training_done_on=tdone,
                training_expires_on=texp)
            print(f"  ✓ status={sg.status}")
        else:
            days = int(_input("Within how many days", default="60") or "60")
            for s in data.list_safeguarding_alerts(days=days):
                print(f"   #{s.alumni_id:<5}  {s.status:<14} "
                      f"DBS:{s.dbs_expires_on or '—'}  "
                      f"Training:{s.training_expires_on or '—'}")
    except (ValidationError, ValueError) as e:
        print(f"  ✗ {e}")
    _pause()


def templates_flow() -> None:
    print("\n═══ Email templates ═══")
    while True:
        print("\n  1) List  2) New  3) View  4) Render preview  5) Delete  0) Back")
        try:
            ch = _input("Select", default="0")
        except _UserAbort:
            return
        if ch == "0":
            return
        try:
            if ch == "1":
                for t in data.list_email_templates():
                    print(f"   #{t.template_id:<4} {t.name:<24} v{t.version}  "
                          f"{t.category or '—':<14}  {t.subject[:40]}")
            elif ch == "2":
                name = _input("Name", allow_empty=False)
                cat = _input("Category (optional)") or None
                subj = _input("Subject (use {first_name})", allow_empty=False)
                print("  Body (end with a single '.' on a line):")
                lines = []
                while True:
                    line = input()
                    if line.strip() == ".":
                        break
                    lines.append(line)
                body = "\n".join(lines)
                t = data.create_email_template(name, subj, body, category=cat)
                print(f"  ✓ created #{t.template_id} v{t.version}")
            elif ch == "3":
                tid = int(_input("Template id", allow_empty=False))
                for t in data.list_email_templates(latest_only=False):
                    if t.template_id == tid:
                        print(f"  {t.name} v{t.version}")
                        print(f"  Subject: {t.subject}")
                        print("  Body:")
                        print(t.body)
                        break
            elif ch == "4":
                name = _input("Template name", allow_empty=False)
                a = _pick_alumnus()
                t = data.get_email_template(name)
                if not t:
                    print("  not found")
                else:
                    s, b = data.render_template(t, a.alumni_id)
                    print(f"  Subject: {s}")
                    print(f"  Body:\n{b}")
            elif ch == "5":
                tid = int(_input("Template id to delete", allow_empty=False))
                if _yes_no(f"Delete template #{tid}?", default=False):
                    data.delete_email_template(tid)
                    print("  ✓")
        except (ValidationError, ValueError) as e:
            print(f"  ✗ {e}")
        except _UserAbort:
            print("  Cancelled.")


def drip_flow() -> None:
    print("\n═══ Drip campaigns ═══")
    while True:
        print("\n  1) List  2) Create  3) Add step  4) Status  5) Enroll  "
              "6) Tick now  7) Unsubscribe  0) Back")
        try:
            ch = _input("Select", default="0")
        except _UserAbort:
            return
        if ch == "0":
            return
        try:
            if ch == "1":
                for d in data.list_drip_campaigns():
                    print(f"   #{d.drip_id:<4} {d.name:<24}  [{d.status}]  "
                          f"{d.description or ''}")
                    for s in data.list_drip_steps(d.drip_id):
                        print(f"      step {s.position}  +{s.delay_days}d  "
                              f"{('template #' + str(s.template_id)) if s.template_id else (s.subject or '?')}")
            elif ch == "2":
                name = _input("Name", allow_empty=False)
                desc = _input("Description (optional)") or None
                d = data.create_drip_campaign(name, description=desc)
                print(f"  ✓ #{d.drip_id}")
            elif ch == "3":
                did = int(_input("Drip id", allow_empty=False))
                pos = int(_input("Position", allow_empty=False))
                delay = int(_input("Delay days", default="0") or "0")
                use_t = _yes_no("Use template?", default=False)
                tid = subj = body = None
                if use_t:
                    tid = int(_input("Template id", allow_empty=False))
                else:
                    subj = _input("Subject", allow_empty=False)
                    body = _input("Body", allow_empty=False)
                data.add_drip_step(did, position=pos, delay_days=delay,
                    template_id=tid, subject=subj, body=body)
                print("  ✓")
            elif ch == "4":
                did = int(_input("Drip id", allow_empty=False))
                st = _pick_from("Status", list(DRIP_STATUSES))
                data.set_drip_status(did, st)
                print("  ✓")
            elif ch == "5":
                did = int(_input("Drip id", allow_empty=False))
                a = _pick_alumnus()
                data.enroll_in_drip(did, a.alumni_id)
                print("  ✓")
            elif ch == "6":
                ticks = data.tick_drip()
                for t in ticks:
                    print(f"   sent step #{t.step_id} → alumnus #{t.alumni_id} "
                          f"({t.subject})")
                print(f"  → {len(ticks)} tick(s)")
            elif ch == "7":
                did = int(_input("Drip id", allow_empty=False))
                a = _pick_alumnus()
                data.unsubscribe_from_drip(did, a.alumni_id)
                print("  ✓")
        except (ValidationError, ValueError) as e:
            print(f"  ✗ {e}")
        except _UserAbort:
            print("  Cancelled.")


def ab_flow() -> None:
    print("\n═══ A/B tests ═══")
    while True:
        print("\n  1) List  2) Create  3) Add variant  4) Assign  "
              "5) Record event  6) Results  0) Back")
        try:
            ch = _input("Select", default="0")
        except _UserAbort:
            return
        if ch == "0":
            return
        try:
            if ch == "1":
                with _connect_alumni_lookup() as _:
                    pass  # warm cache (not used here, just structural)
                # Simple direct query: reuse list_ab_variants per test
                # Lacking a list_ab_tests helper — query via direct sql:
                import sqlite3
                with sqlite3.connect(str(data.DB_PATH)) as conn:
                    conn.row_factory = sqlite3.Row
                    rows = conn.execute(
                        "SELECT * FROM alumni_ab_tests "
                        "ORDER BY created_at DESC").fetchall()
                for r in rows:
                    print(f"   #{r['test_id']:<4} {r['name']:<24} "
                          f"sent_at={r['sent_at'] or '—'}")
            elif ch == "2":
                name = _input("Name", allow_empty=False)
                desc = _input("Description") or None
                t = data.create_ab_test(name, description=desc)
                print(f"  ✓ #{t.test_id}")
            elif ch == "3":
                tid = int(_input("Test id", allow_empty=False))
                lbl = _input("Variant label (e.g. A)", allow_empty=False)
                subj = _input("Subject", allow_empty=False)
                body = _input("Body", allow_empty=False)
                data.add_ab_variant(tid, label=lbl, subject=subj, body=body)
                print("  ✓")
            elif ch == "4":
                tid = int(_input("Test id", allow_empty=False))
                year = _input("Leaving year filter (blank=all)") or None
                filters = {"year": year} if year else {}
                # list_alumni filter param is 'leaving_year' not 'year';
                # accept either form for convenience:
                if "year" in filters:
                    filters["leaving_year"] = filters.pop("year")
                counts = data.assign_ab_audience(tid, filters=filters)
                print(f"  counts: {counts}")
            elif ch == "5":
                tid = int(_input("Test id", allow_empty=False))
                a = _pick_alumnus()
                kind = _pick_from("Kind", ["send", "open", "click"])
                data.record_ab_event(tid, a.alumni_id, kind)
                print("  ✓")
            elif ch == "6":
                tid = int(_input("Test id", allow_empty=False))
                for r in data.ab_test_results(tid):
                    print(f"   {r.label:<6}  sent={r.sent:<4} "
                          f"opens={r.opens} ({r.open_rate}%)  "
                          f"clicks={r.clicks} ({r.click_rate}%)")
        except (ValidationError, ValueError) as e:
            print(f"  ✗ {e}")
        except _UserAbort:
            print("  Cancelled.")


def sms_flow() -> None:
    print("\n═══ SMS ═══")
    print("  1) Send to one  2) View history  0) Back")
    try:
        ch = _input("Select", default="0")
    except _UserAbort:
        return
    if ch == "0":
        return
    try:
        a = _pick_alumnus()
        if ch == "1":
            body = _input("Body", allow_empty=False)
            sms = data.send_sms_to_alumnus(a.alumni_id, body)
            print(f"  ✓ {sms.status}")
        else:
            for s in data.list_sms_for(a.alumni_id):
                print(f"   #{s.sms_id:<5} {s.sent_at}  [{s.status}]  "
                      f"{s.body[:60]}")
    except (ValidationError, ValueError) as e:
        print(f"  ✗ {e}")
    _pause()


def postal_flow() -> None:
    print("\n═══ Postal mail merge ═══")
    print("  1) Generate one  2) Bulk (filters)  0) Back")
    try:
        ch = _input("Select", default="0")
    except _UserAbort:
        return
    if ch == "0":
        return
    try:
        out_dir = _input("Output directory", allow_empty=False)
        subj = _input("Subject (use {first_name})", allow_empty=False)
        print("  Body (end with '.' on a line):")
        lines: list[str] = []
        while True:
            line = input()
            if line.strip() == ".":
                break
            lines.append(line)
        body = "\n".join(lines)
        if ch == "1":
            a = _pick_alumnus()
            L = data.generate_postal_letter(a.alumni_id,
                subject=subj, body=body, out_dir=out_dir)
            print(f"  ✓ {L.pdf_path}")
        else:
            year = _input("Leaving year (blank=all)") or None
            filters: dict[str, Any] = {}
            if year:
                filters["leaving_year"] = year
            letters = data.generate_postal_bulk(filters, subject=subj,
                body=body, out_dir=out_dir)
            print(f"  ✓ {len(letters)} letters")
    except (ValidationError, ValueError) as e:
        print(f"  ✗ {e}")
    _pause()


def newsletter_flow() -> None:
    print("\n═══ Newsletters ═══")
    while True:
        print("\n  1) List  2) Create  3) Add section  4) Publish  "
              "5) Audience  6) HTML preview  0) Back")
        try:
            ch = _input("Select", default="0")
        except _UserAbort:
            return
        if ch == "0":
            return
        try:
            if ch == "1":
                for n in data.list_newsletters():
                    print(f"   #{n.newsletter_id:<4} {n.issue:<16} "
                          f"{n.title[:36]:<36} [{n.status}]  "
                          f"{n.published_at or '—'}")
            elif ch == "2":
                issue = _input("Issue (e.g. 2025-Spring)",
                                  allow_empty=False)
                title = _input("Title", allow_empty=False)
                n = data.create_newsletter(issue, title)
                print(f"  ✓ #{n.newsletter_id}")
            elif ch == "3":
                nid = int(_input("Newsletter id", allow_empty=False))
                heading = _input("Heading", allow_empty=False)
                body = _input("Body", allow_empty=False)
                data.add_newsletter_section(nid, heading=heading, body=body)
                print("  ✓")
            elif ch == "4":
                nid = int(_input("Newsletter id", allow_empty=False))
                year = _input("Leaving year filter (blank=all)") or None
                filters = {"leaving_year": year} if year else None
                data.publish_newsletter(nid, distribution_filters=filters)
                print("  ✓ Published")
            elif ch == "5":
                nid = int(_input("Newsletter id", allow_empty=False))
                rows = data.newsletter_audience(nid)
                print(f"  audience size: {len(rows)}")
                for a in rows[:20]:
                    print(f"   #{a.alumni_id:<5} {a.full_name}")
                if len(rows) > 20:
                    print(f"   ... +{len(rows) - 20} more")
            elif ch == "6":
                nid = int(_input("Newsletter id", allow_empty=False))
                print(data.render_newsletter_html(nid))
        except (ValidationError, ValueError) as e:
            print(f"  ✗ {e}")
        except _UserAbort:
            print("  Cancelled.")


def tracking_flow() -> None:
    print("\n═══ Open/click tracking ═══")
    while True:
        print("\n  1) Mint pixel  2) Mint link  3) Record event  "
              "4) Resolve token  5) Summary  0) Back")
        try:
            ch = _input("Select", default="0")
        except _UserAbort:
            return
        if ch == "0":
            return
        try:
            if ch == "1":
                a = _pick_alumnus()
                ref = _input("Campaign ref (optional)") or None
                tok = data.create_tracking_pixel(a.alumni_id,
                                                      campaign_ref=ref)
                print(f"  token: {tok}")
            elif ch == "2":
                a = _pick_alumnus()
                url = _input("Target URL", allow_empty=False)
                ref = _input("Campaign ref (optional)") or None
                tok = data.create_tracked_link(url,
                    alumni_id=a.alumni_id, campaign_ref=ref)
                print(f"  token: {tok}")
            elif ch == "3":
                tok = _input("Token", allow_empty=False)
                kind = _pick_from("Kind", list(TRACK_KINDS))
                data.record_track_event(tok, kind)
                print("  ✓")
            elif ch == "4":
                tok = _input("Token", allow_empty=False)
                kind, url = data.resolve_tracked_link(tok)
                print(f"  kind={kind}  target={url or '—'}")
            elif ch == "5":
                ref = _input("Campaign ref (blank=all)") or None
                s = data.tracking_summary(campaign_ref=ref)
                print(f"  sends={s.sends}  opens={s.opens}  "
                      f"clicks={s.clicks}  unique_opens={s.unique_opens}")
        except (ValidationError, ValueError) as e:
            print(f"  ✗ {e}")
        except _UserAbort:
            print("  Cancelled.")


# ── Events / fundraising / outcomes (items 27–40) ─────────────────

def ticketing_flow() -> None:
    print("\n═══ Event ticketing ═══")
    while True:
        print("\n  1) Buy ticket  2) Refund  3) Promote waitlist  "
              "4) Finance summary  0) Back")
        try:
            ch = _input("Select", default="0")
        except _UserAbort:
            return
        if ch == "0":
            return
        try:
            eid = int(_input("Event id", allow_empty=False))
            if ch == "1":
                a = _pick_alumnus()
                guests = int(_input("Guests", default="0") or "0")
                amt = _input("Amount paid pence (blank=auto)") or None
                t = data.buy_ticket(eid, a.alumni_id, guests=guests,
                    amount_paid_pence=int(amt) if amt else None)
                print(f"  ✓ rsvp #{t.rsvp_id}  "
                      f"waitlist={t.waitlisted}  paid={t.amount_paid_pence}p")
            elif ch == "2":
                a = _pick_alumnus()
                amt = _input("Amount pence (blank=full)") or None
                reason = _input("Reason (optional)") or None
                rf = data.refund_ticket(eid, a.alumni_id,
                    amount_pence=int(amt) if amt else None, reason=reason)
                print(f"  ✓ refunded {rf.amount_pence}p")
            elif ch == "3":
                promoted = data.promote_from_waitlist(eid)
                print(f"  ✓ promoted {len(promoted)}")
            elif ch == "4":
                f = data.event_finance(eid)
                print(f"  tickets={f.tickets_sold} seats={f.seats_used} "
                      f"waitlist={f.waitlist}  "
                      f"gross={_money_str(f.gross_pence)} "
                      f"refunds={_money_str(f.refunds_pence)} "
                      f"net={_money_str(f.net_pence)}")
        except (ValidationError, ValueError) as e:
            print(f"  ✗ {e}")
        except _UserAbort:
            print("  Cancelled.")


def checkin_flow() -> None:
    print("\n═══ Event check-in (QR) ═══")
    while True:
        print("\n  1) Issue tokens (event)  2) Scan token  0) Back")
        try:
            ch = _input("Select", default="0")
        except _UserAbort:
            return
        if ch == "0":
            return
        try:
            if ch == "1":
                eid = int(_input("Event id", allow_empty=False))
                n = data.issue_event_checkin_tokens(eid)
                print(f"  ✓ {n} token(s) minted")
            elif ch == "2":
                tok = _input("Token", allow_empty=False)
                res = data.check_in_by_token(tok)
                print(f"  ✓ rsvp #{res.rsvp_id} "
                      f"{'already' if res.already_checked_in else 'now'} "
                      f"in @ {res.checked_in_at}")
        except (ValidationError, ValueError) as e:
            print(f"  ✗ {e}")
        except _UserAbort:
            print("  Cancelled.")


def close_event_flow() -> None:
    print("\n═══ Close event with feedback survey ═══")
    try:
        eid = int(_input("Event id", allow_empty=False))
    except (ValueError, _UserAbort):
        return
    try:
        ev, survey = data.close_event_with_feedback(eid)
        print(f"  ✓ event closed, survey #{survey.survey_id} created, "
              f"{len(data.list_invitations(survey.survey_id))} invitations")
    except (ValidationError, ValueError) as e:
        print(f"  ✗ {e}")
    _pause()


def reunion_planner_flow() -> None:
    print("\n═══ Reunion planner ═══")
    try:
        months = int(_input("Horizon months", default="18") or "18")
    except (ValueError, _UserAbort):
        return
    sugs = data.suggest_reunions(horizon_months=months)
    if not sugs:
        print("  (no suggestions)"); _pause(); return
    for s in sugs:
        print(f"   {s.proposed_date}  {s.proposed_name:<36} "
              f"({s.cohort_size} alumni)")
    if _yes_no("\n  Create draft events from these?", default=False):
        created = data.create_reunion_events(horizon_months=months)
        print(f"  ✓ created {len(created)} draft event(s)")
    _pause()


def gift_aid_flow() -> None:
    print("\n═══ Gift Aid declarations ═══")
    while True:
        print("\n  1) Add  2) Withdraw  3) Check active  "
              "4) Export R68 CSV  0) Back")
        try:
            ch = _input("Select", default="0")
        except _UserAbort:
            return
        if ch == "0":
            return
        try:
            if ch == "1":
                a = _pick_alumnus()
                vfrom = _input("Valid from (YYYY-MM-DD)", allow_empty=False)
                vuntil = _input("Valid until (optional)") or None
                full = _input("Full name", allow_empty=False)
                addr = _input("Address", allow_empty=False)
                pc = _input("Postcode", allow_empty=False)
                data.add_gift_aid_declaration(a.alumni_id,
                    valid_from=vfrom, valid_until=vuntil,
                    full_name=full, address=addr, postcode=pc)
                print("  ✓")
            elif ch == "2":
                did = int(_input("Declaration id", allow_empty=False))
                data.withdraw_gift_aid_declaration(did)
                print("  ✓")
            elif ch == "3":
                a = _pick_alumnus()
                g = data.get_active_gift_aid(a.alumni_id)
                print(f"  {'ACTIVE: ' + g.full_name if g else 'no active declaration'}")
            elif ch == "4":
                p = _input("Output CSV path", allow_empty=False)
                ys = _input("Year start (YYYY-MM-DD)", allow_empty=False)
                ye = _input("Year end   (YYYY-MM-DD)", allow_empty=False)
                n = data.export_r68_csv(p, year_start=ys, year_end=ye)
                print(f"  ✓ wrote {n} rows to {p}")
        except (ValidationError, ValueError) as e:
            print(f"  ✗ {e}")
        except _UserAbort:
            print("  Cancelled.")


def recurring_flow() -> None:
    print("\n═══ Recurring donations ═══")
    while True:
        print("\n  1) List  2) Create  3) Status  4) Tick now  0) Back")
        try:
            ch = _input("Select", default="0")
        except _UserAbort:
            return
        if ch == "0":
            return
        try:
            if ch == "1":
                for s in data.list_recurring():
                    print(f"   #{s.schedule_id:<4} a#{s.alumni_id:<4} "
                          f"{_money_str(s.amount_pence)} {s.frequency} "
                          f"next={s.next_charge_on}  [{s.status}]  "
                          f"fails={s.failure_count}")
            elif ch == "2":
                a = _pick_alumnus()
                amt = int(_input("Amount pence", allow_empty=False))
                freq = _pick_from("Frequency", list(RECURRING_FREQS),
                                     default="Monthly")
                nxt = _input("First charge (YYYY-MM-DD, blank=today)") or None
                fund = _input("Fund code (optional)") or None
                pm = _input("Payment method (Direct Debit/Card/…)") or None
                sch = data.create_recurring(a.alumni_id,
                    amount_pence=amt, frequency=freq,
                    next_charge_on=nxt, fund_code=fund,
                    payment_method=pm)
                print(f"  ✓ #{sch.schedule_id}")
            elif ch == "3":
                sid = int(_input("Schedule id", allow_empty=False))
                st = _pick_from("Status", list(RECURRING_STATUSES))
                data.set_recurring_status(sid, st)
                print("  ✓")
            elif ch == "4":
                ticks = data.tick_recurring()
                ok = sum(1 for t in ticks if t.success)
                print(f"  ✓ {ok}/{len(ticks)} succeeded")
        except (ValidationError, ValueError) as e:
            print(f"  ✗ {e}")
        except _UserAbort:
            print("  Cancelled.")


def donor_pipeline_flow() -> None:
    print("\n═══ Donor pipeline ═══")
    while True:
        print("\n  1) Set stage  2) View per alumnus  "
              "3) List by stage  0) Back")
        try:
            ch = _input("Select", default="0")
        except _UserAbort:
            return
        if ch == "0":
            return
        try:
            if ch == "1":
                a = _pick_alumnus()
                stage = _pick_from("Stage", list(DONOR_STAGES))
                owner = _input("Owner staff id (optional)") or None
                action = _input("Next action (optional)") or None
                when = _input("Next action on (YYYY-MM-DD)") or None
                cap_raw = _input("Capacity pence (optional)")
                cap = int(cap_raw) if cap_raw else None
                data.set_donor_stage(a.alumni_id, stage,
                    owner_staff_id=owner, next_action=action,
                    next_action_on=when, capacity_pence=cap)
                print("  ✓")
            elif ch == "2":
                a = _pick_alumnus()
                p = data.get_donor_pipeline(a.alumni_id)
                print(f"  {p}" if p else "  (no record)")
            elif ch == "3":
                stage = _pick_from("Stage", list(DONOR_STAGES))
                for p in data.list_donor_pipeline(stage=stage):
                    print(f"   a#{p.alumni_id:<5} owner={p.owner_staff_id or '—'}  "
                          f"next={p.next_action or '—'} on {p.next_action_on or '—'}")
        except (ValidationError, ValueError) as e:
            print(f"  ✗ {e}")
        except _UserAbort:
            print("  Cancelled.")


def funds_flow() -> None:
    print("\n═══ Funds ═══")
    while True:
        print("\n  1) List  2) Upsert  3) Tag donation  4) Totals  0) Back")
        try:
            ch = _input("Select", default="0")
        except _UserAbort:
            return
        if ch == "0":
            return
        try:
            if ch == "1":
                for f in data.list_funds():
                    r = "R" if f.restricted else "U"
                    print(f"   #{f.fund_id:<3} {f.code:<10} [{r}] {f.name}")
            elif ch == "2":
                code = _input("Code", allow_empty=False)
                name = _input("Name", allow_empty=False)
                restr = _yes_no("Restricted?", default=False)
                data.upsert_fund(code, name, restricted=restr)
                print("  ✓")
            elif ch == "3":
                did = int(_input("Donation id", allow_empty=False))
                code = _input("Fund code", allow_empty=False)
                data.tag_donation_fund(did, code)
                print("  ✓")
            elif ch == "4":
                for t in data.fund_totals():
                    r = "R" if t.restricted else "U"
                    print(f"   {t.fund_code:<14} [{r}] "
                          f"{_money_str(t.raised_pence):>12} "
                          f"({t.fund_name})")
        except (ValidationError, ValueError) as e:
            print(f"  ✗ {e}")
        except _UserAbort:
            print("  Cancelled.")


def bequests_flow() -> None:
    print("\n═══ Bequests / legacies ═══")
    while True:
        print("\n  1) List  2) Add  3) Set status  0) Back")
        try:
            ch = _input("Select", default="0")
        except _UserAbort:
            return
        if ch == "0":
            return
        try:
            if ch == "1":
                status = _input("Status filter (blank=all)") or None
                for b in data.list_bequests(status=status):
                    print(f"   #{b.bequest_id:<3} a#{b.alumni_id:<4} "
                          f"{_money_str(b.estimated_pence):>12} "
                          f"[{b.status}] confirmed={b.confirmed_on or '—'}")
            elif ch == "2":
                a = _pick_alumnus()
                est_raw = _input("Estimated pence (optional)")
                est = int(est_raw) if est_raw else None
                exec_name = _input("Executor name (optional)") or None
                exec_email = _input("Executor email (optional)") or None
                conf = _input("Confirmed on (YYYY-MM-DD, optional)") or None
                data.add_bequest(a.alumni_id, estimated_pence=est,
                    executor_name=exec_name, executor_email=exec_email,
                    confirmed_on=conf)
                print("  ✓")
            elif ch == "3":
                bid = int(_input("Bequest id", allow_empty=False))
                st = _pick_from("Status", list(BEQUEST_STATUSES))
                rdate = _input("Realised on (YYYY-MM-DD, optional)") or None
                data.set_bequest_status(bid, st, realised_on=rdate)
                print("  ✓")
        except (ValidationError, ValueError) as e:
            print(f"  ✗ {e}")
        except _UserAbort:
            print("  Cancelled.")


def matched_giving_flow() -> None:
    print("\n═══ Matched giving ═══")
    while True:
        print("\n  1) List schemes  2) Upsert scheme  "
              "3) Apply to donation  4) Find for employer  0) Back")
        try:
            ch = _input("Select", default="0")
        except _UserAbort:
            return
        if ch == "0":
            return
        try:
            if ch == "1":
                for s in data.list_matched_schemes():
                    cap = _money_str(s.cap_pence) if s.cap_pence else "—"
                    print(f"   #{s.scheme_id:<3} {s.employer:<22} "
                          f"×{s.multiplier} cap={cap}")
            elif ch == "2":
                emp = _input("Employer", allow_empty=False)
                mult = float(_input("Multiplier", default="1.0") or "1.0")
                cap_raw = _input("Cap pence (optional)")
                cap = int(cap_raw) if cap_raw else None
                data.upsert_matched_scheme(emp, multiplier=mult,
                                              cap_pence=cap)
                print("  ✓")
            elif ch == "3":
                did = int(_input("Donation id", allow_empty=False))
                matched = data.auto_apply_matched_giving(did)
                print(f"  ✓ matched {matched}p")
            elif ch == "4":
                emp = _input("Employer", allow_empty=False)
                s = data.find_matched_scheme(emp)
                print(f"  {s if s else '(no scheme)'}")
        except (ValidationError, ValueError) as e:
            print(f"  ✗ {e}")
        except _UserAbort:
            print("  Cancelled.")


def neet_flow() -> None:
    print("\n═══ NEET tracking ═══")
    while True:
        print("\n  1) Record check  2) View alumnus  "
              "3) Breakdown  0) Back")
        try:
            ch = _input("Select", default="0")
        except _UserAbort:
            return
        if ch == "0":
            return
        try:
            if ch == "1":
                a = _pick_alumnus()
                m = int(_input("Months after (3/6/12/24)",
                                  allow_empty=False))
                st = _pick_from("Status", list(NEET_STATUSES))
                data.record_neet_check(a.alumni_id, months_after=m,
                                          status=st)
                print("  ✓")
            elif ch == "2":
                a = _pick_alumnus()
                for c in data.list_neet_checks(a.alumni_id):
                    print(f"   {c.months_after}m: {c.status}  ({c.checked_on})")
            elif ch == "3":
                year = _input("Leaving year (blank=all)") or None
                for r in data.neet_breakdown(leaving_year=year):
                    print(f"   {r.months_after:>2}m  cohort={r.cohort}  "
                          f"neet={r.neet}  not_neet={r.not_neet}  "
                          f"unk={r.unknown}  rate={r.neet_rate_pct}%")
        except (ValidationError, ValueError) as e:
            print(f"  ✗ {e}")
        except _UserAbort:
            print("  Cancelled.")


def russell_oxbridge_flow() -> None:
    print("\n═══ Russell Group / Oxbridge breakout ═══")
    year = _input("Leaving year (blank=all)") or None
    r = data.russell_group_breakdown(leaving_year=year)
    print(f"  cohort={r.cohort}  RG={r.russell_group} ({r.russell_rate_pct}%)  "
          f"Oxbridge={r.oxbridge} ({r.oxbridge_rate_pct}%)")
    _pause()


def pg_progression_flow() -> None:
    print("\n═══ Postgraduate progression ═══")
    year = _input("Leaving year (blank=all)") or None
    r = data.postgraduate_rate(leaving_year=year)
    print(f"  cohort={r.cohort}  PG={r.pg_count} ({r.pg_rate_pct}%)")
    for p in data.postgraduate_progression(leaving_year=year):
        print(f"   a#{p.alumni_id:<5} {p.full_name:<24} "
              f"{', '.join(p.pg_qualifications)} @ "
              f"{', '.join(p.pg_institutions)}")
    _pause()


def first_gen_flow() -> None:
    print("\n═══ First-generation HE outcomes ═══")
    while True:
        print("\n  1) Flag alumnus  2) Outcome report  0) Back")
        try:
            ch = _input("Select", default="0")
        except _UserAbort:
            return
        if ch == "0":
            return
        try:
            if ch == "1":
                a = _pick_alumnus()
                val = _yes_no("First-generation HE?", default=True)
                data.set_first_gen_he(a.alumni_id, val)
                print("  ✓")
            elif ch == "2":
                year = _input("Leaving year (blank=all)") or None
                for r in data.first_gen_outcomes(leaving_year=year):
                    print(f"   {r.bucket:<16} cohort={r.cohort}  "
                          f"in_HE={r.in_he} ({r.he_rate_pct}%)  "
                          f"RG={r.russell_group} ({r.russell_rate_pct}%)")
        except (ValidationError, ValueError) as e:
            print(f"  ✗ {e}")
        except _UserAbort:
            print("  Cancelled.")


# ── Final cluster (items 41–50) ───────────────────────────────────

def protected_chars_flow() -> None:
    print("\n═══ Protected characteristics ═══")
    print("  1) Set flag  2) Set ethnicity  3) Gap report  0) Back")
    try:
        ch = _input("Select", default="0")
    except _UserAbort:
        return
    if ch == "0":
        return
    try:
        if ch == "1":
            a = _pick_alumnus()
            char = _pick_from("Characteristic", list(PROTECTED_CHARS))
            val = _yes_no("Set true?", default=False)
            data.set_protected_characteristic(a.alumni_id, char, val)
            print("  ✓")
        elif ch == "2":
            a = _pick_alumnus()
            val = _input("Ethnicity (blank=clear)") or None
            data.set_ethnicity(a.alumni_id, val)
            print("  ✓")
        elif ch == "3":
            year = _input("Leaving year (blank=all)") or None
            for r in data.protected_characteristic_gaps(leaving_year=year):
                rate = ("(suppressed)" if r.suppressed
                          else f"{r.he_rate_pct}%")
                print(f"   {r.characteristic:<14} {r.bucket:<8} "
                      f"cohort={r.cohort:<4} HE={rate}")
    except (ValidationError, ValueError) as e:
        print(f"  ✗ {e}")
    _pause()


def hesa_flow() -> None:
    print("\n═══ HESA benchmarks ═══")
    print("  1) List  2) Upsert  3) Compare cohort  0) Back")
    try:
        ch = _input("Select", default="0")
    except _UserAbort:
        return
    if ch == "0":
        return
    try:
        if ch == "1":
            for b in data.list_hesa_benchmarks():
                print(f"   {b.leaving_year}  {b.metric:<18} "
                      f"{b.rate_pct:>5.1f}%  ({b.source or '—'})")
        elif ch == "2":
            year = _input("Leaving year", allow_empty=False)
            metric = _pick_from("Metric",
                ["he_entry", "russell_group", "oxbridge",
                 "postgraduate"])
            rate = float(_input("Rate %", allow_empty=False))
            src = _input("Source (optional)") or None
            data.upsert_hesa_benchmark(year, metric, rate, source=src)
            print("  ✓")
        elif ch == "3":
            year = _input("Leaving year", allow_empty=False)
            for d in data.compare_with_hesa(year):
                sign = "+" if d.delta_pct >= 0 else ""
                print(f"   {d.metric:<18}  school={d.school_rate_pct}%  "
                      f"HESA={d.hesa_rate_pct}%  "
                      f"Δ={sign}{d.delta_pct}%")
    except (ValidationError, ValueError) as e:
        print(f"  ✗ {e}")
    _pause()


def dfe_export_flow() -> None:
    print("\n═══ DfE 16-18 destinations export ═══")
    try:
        year = _input("Leaving year", allow_empty=False)
        path = _input("Output CSV path", allow_empty=False)
    except _UserAbort:
        return
    try:
        n = data.export_dfe_destinations_csv(path, leaving_year=year)
        print(f"  ✓ wrote {n} rows to {path}")
    except (ValidationError, ValueError) as e:
        print(f"  ✗ {e}")
    _pause()


def sar_flow() -> None:
    print("\n═══ SAR bundle ═══")
    try:
        a = _pick_alumnus()
        out_dir = _input("Output directory", allow_empty=False)
    except _UserAbort:
        return
    try:
        path = data.generate_sar_bundle(a.alumni_id, out_dir)
        print(f"  ✓ {path}")
    except (ValidationError, ValueError) as e:
        print(f"  ✗ {e}")
    _pause()


def erasure_flow() -> None:
    print("\n═══ Right-to-erasure workflow ═══")
    while True:
        print("\n  1) Request  2) Review  3) Complete  4) List  0) Back")
        try:
            ch = _input("Select", default="0")
        except _UserAbort:
            return
        if ch == "0":
            return
        try:
            if ch == "1":
                a = _pick_alumnus()
                by = _input("Requested by (staff id)") or None
                reason = _input("Reason (optional)") or None
                req = data.request_erasure(a.alumni_id,
                    requested_by=by, reason=reason)
                print(f"  ✓ request #{req.request_id}")
            elif ch == "2":
                rid = int(_input("Request id", allow_empty=False))
                reviewer = _input("Reviewer", allow_empty=False)
                decision = _pick_from("Decision",
                    ["Approved", "Rejected"])
                notes = _input("Notes (optional)") or None
                data.review_erasure(rid, reviewer=reviewer,
                    decision=decision, review_notes=notes)
                print("  ✓")
            elif ch == "3":
                rid = int(_input("Request id", allow_empty=False))
                if _yes_no("Anonymise now?", default=False):
                    data.complete_erasure(rid)
                    print("  ✓ anonymised")
            elif ch == "4":
                status = _input(
                    "Status filter (blank=all)") or None
                for r in data.list_erasure_requests(status=status):
                    print(f"   #{r.request_id:<3} a#{r.alumni_id:<4} "
                          f"[{r.status}] requested={r.requested_at}")
        except (ValidationError, ValueError) as e:
            print(f"  ✗ {e}")
        except _UserAbort:
            print("  Cancelled.")


def quality_flow() -> None:
    print("\n═══ Data quality dashboard ═══")
    q = data.data_quality_report()
    print(f"  total={q.total}")
    print(f"  email%={q.with_email_pct}  phone%={q.with_phone_pct}  "
          f"address%={q.with_address_pct}")
    print(f"  missing destination%={q.missing_destination_pct}")
    print(f"  stale (24mo)%={q.stale_24mo_pct}  "
          f"bounce%={q.bounce_rate_pct}")
    print(f"  opt-in%={q.opt_in_pct}  "
          f"data-storage consent%={q.consent_data_storage_pct}")
    _pause()


def dedupe_buckets_flow() -> None:
    print("\n═══ Dedupe — confidence buckets ═══")
    b = data.dedupe_buckets()
    def show(label: str, rows) -> None:
        if not rows: return
        print(f"\n  {label} ({len(rows)}):")
        for c in rows:
            print(f"   {c.score:.2f}  keep #{c.keep_id} ⇐ #{c.merge_id}")
    show("Very high (≥0.95)", b.very_high)
    show("High (0.85–0.95)", b.high)
    show("Medium (0.70–0.85)", b.medium)
    if _yes_no("\nBatch-merge all very-high pairs?", default=False):
        pairs = [(c.keep_id, c.merge_id) for c in b.very_high]
        ok, errs = data.batch_confirm_merges(pairs)
        print(f"  ✓ merged {ok}/{len(pairs)}, errors={len(errs)}")
        for e in errs[:5]:
            print(f"    {e}")
    _pause()


def webhooks_flow() -> None:
    print("\n═══ Webhooks ═══")
    while True:
        print("\n  1) List  2) Register  3) Toggle  4) Delete  "
              "5) Recent events  0) Back")
        try:
            ch = _input("Select", default="0")
        except _UserAbort:
            return
        if ch == "0":
            return
        try:
            if ch == "1":
                for w in data.list_webhooks():
                    print(f"   #{w.webhook_id:<3} "
                          f"{'A' if w.active else 'I'}  {w.url}  → "
                          f"{','.join(w.event_types)}")
            elif ch == "2":
                url = _input("URL", allow_empty=False)
                evs = _input(
                    f"Event types (comma-separated; one of: "
                    f"{', '.join(WEBHOOK_EVENT_TYPES)})",
                    allow_empty=False)
                events = [e.strip() for e in evs.split(",") if e.strip()]
                secret = _input("Secret (optional)") or None
                w = data.register_webhook(url, event_types=events,
                                              secret=secret)
                print(f"  ✓ #{w.webhook_id}")
            elif ch == "3":
                wid = int(_input("Webhook id", allow_empty=False))
                active = _yes_no("Active?", default=True)
                data.set_webhook_active(wid, active)
                print("  ✓")
            elif ch == "4":
                wid = int(_input("Webhook id", allow_empty=False))
                if _yes_no(f"Delete webhook #{wid}?", default=False):
                    data.delete_webhook(wid)
                    print("  ✓")
            elif ch == "5":
                for ev in data.list_recent_webhook_events(limit=20):
                    print(f"   #{ev['event_id']:<5} {ev['queued_at']}  "
                          f"{ev['event_type']:<22} "
                          f"delivered={ev['delivered_at'] or '—'}")
        except (ValidationError, ValueError) as e:
            print(f"  ✗ {e}")
        except _UserAbort:
            print("  Cancelled.")


def custom_fields_flow() -> None:
    print("\n═══ Custom fields ═══")
    while True:
        print("\n  1) List  2) Add  3) Delete  4) Set value  "
              "5) Search by value  0) Back")
        try:
            ch = _input("Select", default="0")
        except _UserAbort:
            return
        if ch == "0":
            return
        try:
            if ch == "1":
                for f in data.list_custom_fields():
                    print(f"   #{f.field_id:<3} {f.name:<18} "
                          f"[{f.type}]  {f.label}")
            elif ch == "2":
                name = _input("Name (machine)", allow_empty=False)
                label = _input("Label (display)", allow_empty=False)
                tp = _pick_from("Type", list(CUSTOM_FIELD_TYPES),
                                   default="text")
                data.add_custom_field(name, label, type=tp)
                print("  ✓")
            elif ch == "3":
                fid = int(_input("Field id", allow_empty=False))
                if _yes_no(f"Delete field #{fid}?", default=False):
                    data.delete_custom_field(fid)
                    print("  ✓")
            elif ch == "4":
                a = _pick_alumnus()
                name = _input("Field name", allow_empty=False)
                val = _input("Value (blank=clear)")
                data.set_custom_value(a.alumni_id, name, val)
                print("  ✓")
            elif ch == "5":
                name = _input("Field name", allow_empty=False)
                val = _input("Value", allow_empty=False)
                for x in data.search_by_custom(name, val):
                    print(f"   #{x.alumni_id:<5} {x.full_name}")
        except (ValidationError, ValueError) as e:
            print(f"  ✗ {e}")
        except _UserAbort:
            print("  Cancelled.")


def media_flow() -> None:
    print("\n═══ Media attachments ═══")
    while True:
        print("\n  1) List  2) Attach  3) Set profile  "
          "4) Set consent  5) Delete  0) Back")
        try:
            ch = _input("Select", default="0")
        except _UserAbort:
            return
        if ch == "0":
            return
        try:
            if ch == "1":
                a = _pick_alumnus()
                for m in data.list_media(a.alumni_id):
                    star = " ★" if m.is_profile else "  "
                    print(f"   #{m.media_id:<3}{star} [{m.kind}] "
                          f"consent={'Y' if m.consent_granted else 'N'}  "
                          f"exif_stripped="
                          f"{'Y' if m.exif_stripped else 'N'}  "
                          f"{m.file_path}")
            elif ch == "2":
                a = _pick_alumnus()
                path = _input("File path", allow_empty=False)
                kind = _pick_from("Kind", list(MEDIA_KINDS),
                                     default="photo")
                cap = _input("Caption (optional)") or None
                consent = _yes_no("Consent granted?", default=False)
                strip = _yes_no("Strip EXIF?", default=True)
                profile = _yes_no("Set as profile photo?", default=False)
                m = data.attach_media(a.alumni_id, path, kind=kind,
                    caption=cap, consent_granted=consent,
                    strip_exif=strip, is_profile=profile)
                print(f"  ✓ media #{m.media_id} "
                      f"(exif_stripped={m.exif_stripped})")
            elif ch == "3":
                a = _pick_alumnus()
                mid = int(_input("Media id", allow_empty=False))
                data.set_profile_media(a.alumni_id, mid)
                print("  ✓")
            elif ch == "4":
                mid = int(_input("Media id", allow_empty=False))
                granted = _yes_no("Consent granted?", default=True)
                data.set_media_consent(mid, granted)
                print("  ✓")
            elif ch == "5":
                mid = int(_input("Media id", allow_empty=False))
                delfile = _yes_no("Also delete file from disk?",
                                     default=False)
                data.delete_media(mid, delete_file=delfile)
                print("  ✓")
        except (ValidationError, ValueError) as e:
            print(f"  ✗ {e}")
        except _UserAbort:
            print("  Cancelled.")


_OPS_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Bulk CSV import",         import_csv_flow),
    ("Bulk CSV export",         export_csv_flow),
    ("Duplicate detection",     dedupe_flow),
    ("Merge by id",             merge_flow),
    ("Audit log",               audit_log_flow),
    ("Soft-delete trash",       trash_flow),
    ("Saved searches",          saved_searches_flow),
    ("Surveys",                 surveys_flow),
    ("SAR bundle",              sar_flow),
    ("Right-to-erasure",        erasure_flow),
    ("Dedupe (confidence buckets)", dedupe_buckets_flow),
    ("Webhooks",                webhooks_flow),
]


def ops_flow() -> None:
    data._log_action("cli.menu_entered", menu="alumni.ops")
    while True:
        print("\n── Alumni — Operational quality ──")
        for i, (label, _) in enumerate(_OPS_MENU, 1):
            print(f"  {i:>2}) {label}")
        print("   0) Back")
        try:
            choice = input("  Select: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if choice == "0":
            data._log_action("cli.menu_exited", menu="alumni.ops")
            return
        if not choice.isdigit() or not (
                1 <= int(choice) <= len(_OPS_MENU)):
            print("  Invalid selection.")
            continue
        label, handler = _OPS_MENU[int(choice) - 1]
        data._log_action("cli.menu_select",
                          menu="alumni.ops", option=label)
        try:
            handler()
        except _UserAbort:
            print("\n  Cancelled.")
        except Exception as e:
            logger.exception(
                "Alumni ops handler crashed (option=%s)", label)
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


_REPORTS_MENU: list[tuple[str, Callable[[], None]]] = [
    ("KS5 destinations CSV (DfE-style)", report_ks5_csv),
    ("Sustained destinations (1/3/5y)",   report_sustained),
    ("Cohort comparison",                   report_cohort_comparison),
    ("University success rates",            report_university_success),
    ("Apprenticeship outcomes",             report_apprenticeship_outcomes),
    ("Disadvantage gap",                    report_disadvantage_gap),
    ("Geographic distribution",             report_geographic),
    ("Sector breakdown",                    report_sector_breakdown),
    ("'Where are they now' site",          report_where_are_they_now),
    ("Re-engagement worklist",              re_engagement_flow),
    ("Upcoming milestones",                 milestones_flow),
    ("Lost-contact queue",                  lost_contact_flow),
    ("SOC/NAICS breakdown",                 soc_flow),
    ("Salary band breakdown",               salary_band_report_flow),
    ("Russell Group / Oxbridge breakout",   russell_oxbridge_flow),
    ("Postgraduate progression",            pg_progression_flow),
    ("HESA benchmark comparison",           hesa_flow),
    ("DfE 16-18 destinations export",       dfe_export_flow),
    ("Data quality dashboard",              quality_flow),
]


def reports_flow() -> None:
    data._log_action("cli.menu_entered", menu="alumni.reports")
    while True:
        print("\n── Alumni — Reports ──")
        for i, (label, _) in enumerate(_REPORTS_MENU, 1):
            print(f"  {i:>2}) {label}")
        print("   0) Back")
        try:
            choice = input("  Select: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if choice == "0":
            data._log_action("cli.menu_exited", menu="alumni.reports")
            return
        if not choice.isdigit() or not (
                1 <= int(choice) <= len(_REPORTS_MENU)):
            print("  Invalid selection.")
            continue
        label, handler = _REPORTS_MENU[int(choice) - 1]
        data._log_action("cli.menu_select",
                          menu="alumni.reports", option=label)
        try:
            handler()
        except _UserAbort:
            print("\n  Cancelled.")
        except Exception as e:
            logger.exception(
                "Alumni reports handler crashed (option=%s)", label)
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


# ── Submenu ───────────────────────────────────────────────────────

_MENU: list[tuple[str, Callable[[], None]]] = [
    ("List All",           list_all),
    ("Filter",             filter_alumni),
    ("View",               view_alumnus),
    ("New (manual)",       new_alumnus),
    ("Archive student",    archive_student_flow),
    ("Unarchived leavers", unarchived_leavers_flow),
    ("Edit",               edit_alumnus),
    ("Education history",  education_flow),
    ("Career history",     career_flow),
    ("Emails & phones",    contacts_flow),
    ("Tags",               tags_flow),
    ("Achievements",       achievements_flow),
    ("Communications",     comms_flow),
    ("Send email",         send_email_flow),
    ("Channel prefs",      channel_prefs_flow),
    ("GDPR consent",       consent_flow),
    ("Portal token",       portal_token_flow),
    ("Record contact",     record_contact_flow),
    ("Events",             events_flow),
    ("Mentoring",          mentoring_flow),
    ("Speakers",           speakers_flow),
    ("Work-experience",    work_exp_flow),
    ("References",         references_flow),
    ("Volunteering",       volunteering_flow),
    ("Campaigns",          campaigns_flow),
    ("Donations & pledges", donations_flow),
    ("Social handles",     social_handles_flow),
    ("Connections",        connections_flow),
    ("Chapters",           chapters_flow),
    ("Engagement score",   engagement_flow),
    ("Public directory",   directory_flow),
    ("Skills",             skills_flow),
    ("Promotion timeline", promotion_timeline_flow),
    ("Employers directory", employers_flow),
    ("Job postings",       jobs_flow),
    ("Internships",        internships_flow),
    ("Mentor matching",    mentor_match_flow),
    ("Mentor profile",     mentor_profile_flow),
    ("Mentor session rate", mentor_rate_flow),
    ("Mentor safeguarding", mentor_safeguarding_flow),
    ("Email templates",    templates_flow),
    ("Drip campaigns",     drip_flow),
    ("A/B tests",          ab_flow),
    ("SMS",                sms_flow),
    ("Postal mail merge",  postal_flow),
    ("Newsletters",        newsletter_flow),
    ("Open/click tracking", tracking_flow),
    ("Event ticketing",    ticketing_flow),
    ("Event check-in",     checkin_flow),
    ("Close event + survey", close_event_flow),
    ("Reunion planner",    reunion_planner_flow),
    ("Gift Aid",           gift_aid_flow),
    ("Recurring donations", recurring_flow),
    ("Donor pipeline",     donor_pipeline_flow),
    ("Funds",              funds_flow),
    ("Bequests",           bequests_flow),
    ("Matched giving",     matched_giving_flow),
    ("NEET tracking",      neet_flow),
    ("First-gen HE",       first_gen_flow),
    ("Protected characteristics", protected_chars_flow),
    ("Custom fields",      custom_fields_flow),
    ("Media attachments",  media_flow),
    ("Change status",      set_status_flow),
    ("Retention",          retention_flow),
    ("Delete",             delete_alumnus_flow),
    ("Operational tools",  ops_flow),
    ("Reports",            reports_flow),
    ("Summary",            summary_flow),
]


def run() -> None:
    data._log_action("cli.menu_entered", menu="alumni")
    while True:
        print("\n── Alumni ──")
        for i, (label, _) in enumerate(_MENU, 1):
            print(f"  {i:>2}) {label}")
        print("   0) Back")
        try:
            choice = input("  Select: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            data._log_action("cli.menu_exited", menu="alumni",
                              reason="interrupt")
            return
        if choice == "0":
            data._log_action("cli.menu_exited", menu="alumni")
            return
        if not choice.isdigit() or not (1 <= int(choice) <= len(_MENU)):
            print("  Invalid selection.")
            continue
        label, handler = _MENU[int(choice) - 1]
        data._log_action("cli.menu_select",
                          menu="alumni", option=label)
        try:
            handler()
        except _UserAbort:
            print("\n  Cancelled.")
            data._log_action("cli.handler_cancelled",
                              menu="alumni", option=label)
        except Exception as e:
            logger.exception("Alumni CLI handler crashed (option=%s)",
                              label)
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Alumni":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Alumni CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
