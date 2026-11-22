"""Alumni CLI: core record flows + education/career/contacts/tags/achievements.

Split out of ``alumni_cli`` (2026-10-22); that module re-exports every name.
"""

from __future__ import annotations

from ._helpers import (
    ACHIEVEMENT_CATEGORIES,
    Alumnus,
    Any,
    DEFAULT_DESTINATION,
    DEFAULT_EDUCATION_STATUS,
    DEFAULT_LEAVING_REASON,
    DEFAULT_STATUS,
    DESTINATION_TYPES,
    EDUCATION_STATUSES,
    EMAIL_LABELS,
    GENDER_OPTIONS,
    LEAVING_REASONS,
    PHONE_LABELS,
    SALARY_BANDS,
    SECTORS,
    STATUSES,
    ValidationError,
    _UserAbort,
    _date,
)
from education_system.systems.sixth_form.domain.learners.alumni import (
    linking as alumni_linking,
    models as alumni_models,
    profile as alumni_profile,
    records as alumni_records,
)
from ._helpers import (  # noqa: F401
    _input,
    _pause,
    _pick_alumnus,
    _pick_from,
    _pick_student,
    _print_alumni,
    _yes_no,
)


# ── Flows ──────────────────────────────────────────────────────────

def list_all() -> None:
    print("\n═══ All Alumni ═══")
    _print_alumni(alumni_records.list_alumni())
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
        rows = alumni_records.list_alumni(
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
    tags = alumni_profile.list_tags_for(a.alumni_id)
    if tags:
        print(f"    Tags                : "
              f"{', '.join(t.name for t in tags)}")
    emails = alumni_profile.list_emails(a.alumni_id)
    if emails:
        print("\n    Emails:")
        for e in emails:
            star = "*" if e.is_primary else " "
            print(f"     {star} #{e.email_id} [{e.label}] {e.email}")
    phones = alumni_profile.list_phones(a.alumni_id)
    if phones:
        print("\n    Phones:")
        for ph in phones:
            star = "*" if ph.is_primary else " "
            print(f"     {star} #{ph.phone_id} [{ph.label}] {ph.phone}")
    edu = alumni_profile.list_education(a.alumni_id)
    if edu:
        print("\n    Education:")
        for e in edu:
            span = f"{e.start_date or '?'} → {e.end_date or '…'}"
            print(f"      #{e.education_id} {e.qualification}"
                  f"{(' ' + e.subject) if e.subject else ''} "
                  f"@ {e.institution}  ({span})  "
                  f"[{e.status}{', ' + e.grade if e.grade else ''}]")
    career = alumni_profile.list_career(a.alumni_id)
    if career:
        print("\n    Career:")
        for c in career:
            span = f"{c.start_date or '?'} → " + (
                "present" if c.is_current else (c.end_date or '?'))
            sect = f" / {c.sector}" if c.sector else ""
            print(f"      #{c.career_id} {c.role} @ {c.employer}"
                  f"{sect}  ({span})"
                  + (f"  [{c.salary_band}]" if c.salary_band else ""))
    ach = alumni_profile.list_achievements(a.alumni_id)
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
        a = alumni_records.create_alumnus(payload)
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
        alumni_records.update_alumnus(a.alumni_id, payload)
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
        a = alumni_linking.archive_student_enriched(sid, **kwargs)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Archived {sid} as alumnus #{a.alumni_id}")
    edu = alumni_profile.list_education(a.alumni_id)
    if edu:
        print(f"    Seeded {len(edu)} education row(s) "
               "from exam results")
    tags = alumni_profile.list_tags_for(a.alumni_id)
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
        alumni_records.record_contact(a.alumni_id, when=when)
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
        alumni_records.set_status(a.alumni_id, new_status)
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
            f"  Recoverable for {alumni_models.SOFT_DELETE_UNDO_DAYS} days "
            "via Trash. Type 'yes'",
            default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if alumni_records.delete_alumnus(a.alumni_id):
        print(f"\n  ✓ Soft-deleted #{a.alumni_id}")
    _pause()


def summary_flow() -> None:
    print("\n═══ Alumni Summary ═══")
    summ = alumni_records.summary()
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
        rows = alumni_profile.list_education(a.alumni_id)
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
                alumni_profile.add_education(a.alumni_id, payload)
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
                alumni_profile.update_education(eid, payload)
            elif choice == "d":
                eid = int(_input("Delete #id", allow_empty=False))
                if alumni_profile.delete_education(eid):
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
        rows = alumni_profile.list_career(a.alumni_id)
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
                alumni_profile.add_career(a.alumni_id, payload)
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
                alumni_profile.update_career(cid, payload)
            elif choice == "d":
                cid = int(_input("Delete #id", allow_empty=False))
                if alumni_profile.delete_career(cid):
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
        emails = alumni_profile.list_emails(a.alumni_id)
        phones = alumni_profile.list_phones(a.alumni_id)
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
                alumni_profile.add_email(a.alumni_id, addr,
                                 label=label, is_primary=is_p)
            elif choice == "ap":
                num = _input("Phone", allow_empty=False)
                label = _pick_from("Label", list(PHONE_LABELS),
                                     default="Mobile")
                is_p = _yes_no("Make primary?",
                                default=not phones)
                alumni_profile.add_phone(a.alumni_id, num,
                                 label=label, is_primary=is_p)
            elif choice == "pe":
                eid = int(_input("Email #id", allow_empty=False))
                alumni_profile.set_primary_email(eid)
            elif choice == "pp":
                pid = int(_input("Phone #id", allow_empty=False))
                alumni_profile.set_primary_phone(pid)
            elif choice == "de":
                eid = int(_input("Email #id", allow_empty=False))
                if alumni_profile.delete_email(eid):
                    print("    ✓ Deleted")
            elif choice == "dp":
                pid = int(_input("Phone #id", allow_empty=False))
                if alumni_profile.delete_phone(pid):
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
        tags = alumni_profile.list_tags_for(a.alumni_id)
        print(f"\n  Tags on #{a.alumni_id} {a.full_name}:")
        if not tags:
            print("    (none)")
        for t in tags:
            print(f"    #{t.tag_id:<3} {t.name}")
        all_tags = alumni_profile.list_all_tags()
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
                t = alumni_profile.add_tag(a.alumni_id, name)
                print(f"    ✓ Tagged with '{t.name}'")
            elif choice == "r":
                tid = int(_input("Tag #id to remove from alumnus",
                                    allow_empty=False))
                if alumni_profile.remove_tag(a.alumni_id, tid):
                    print("    ✓ Removed")
            elif choice == "x":
                tid = int(_input("Tag #id to delete globally",
                                    allow_empty=False))
                if _yes_no("Delete this tag from all alumni?",
                             default=False):
                    if alumni_profile.delete_tag(tid):
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
        rows = alumni_profile.list_achievements(a.alumni_id)
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
                alumni_profile.add_achievement(a.alumni_id, {
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
                alumni_profile.update_achievement(aid, {
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
                if alumni_profile.delete_achievement(aid):
                    print("    ✓ Deleted")
        except _UserAbort:
            print("    Cancelled.")
        except (ValidationError, ValueError) as ex:
            print(f"    ✗ {ex}")
