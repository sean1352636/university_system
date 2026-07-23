"""
International Student Visa Sponsorship & Compliance — interactive CLI.

Wired to the module functions in
``international_compliance.services.visa_service``, which read/write the
shared ``student_records.db`` — the same database the Visa Sponsorship GUI
(``visa_compliance_gui.py``) and the read-only ``my_visa_status_gui.py`` use.
Anything created here is visible in the GUI and vice-versa.

Covers the Student-Route sponsor duties the service exposes:
Visa Records, CAS Issuance, Right-to-Study Checks, Engagement Checks,
Changes of Circumstance (10-day UKVI clock), ATAS Clearance, and
Visa/BRP Expiry Alerts.
"""

from __future__ import annotations

from typing import Optional

from education_system.post_18.university_system.modules.domain.student_affairs.international_compliance.services import (
    visa_service as vs,
)


# --------------------------------------------------------------------------- #
# Input helpers
# --------------------------------------------------------------------------- #
def _prompt(text: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{text}{suffix}: ").strip()
    return value or default


def _prompt_int(text: str, *, allow_blank: bool = True) -> Optional[int]:
    while True:
        raw = input(f"{text}: ").strip()
        if not raw:
            if allow_blank:
                return None
            print("A value is required.")
            continue
        try:
            return int(raw)
        except ValueError:
            print("Please enter a whole number.")


def _prompt_float(text: str, *, allow_blank: bool = True) -> Optional[float]:
    while True:
        raw = input(f"{text}: ").strip()
        if not raw:
            if allow_blank:
                return None
            print("A value is required.")
            continue
        try:
            return float(raw)
        except ValueError:
            print("Please enter a number.")


def _prompt_bool(text: str, default: bool = False) -> bool:
    d = "Y/n" if default else "y/N"
    raw = input(f"{text} ({d}): ").strip().lower()
    if not raw:
        return default
    return raw in ("y", "yes", "true", "1")


def _pause() -> None:
    input("\nPress Enter to continue...")


def _header(title: str) -> None:
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def _current_username(auth) -> str:
    try:
        user = getattr(auth, "current_user", None)
        if isinstance(user, dict):
            return user.get("username") or user.get("name") or "cli-user"
    except Exception:
        pass
    return "cli-user"


def _current_user_id(auth) -> Optional[int]:
    """Best-effort integer user id for 'recorded_by' / 'issued_by' fields."""
    try:
        user = getattr(auth, "current_user", None)
        if isinstance(user, dict):
            raw = user.get("id") or user.get("user_id")
            if raw not in (None, ""):
                return int(raw)
    except (TypeError, ValueError):
        pass
    return None


# --------------------------------------------------------------------------- #
# 1. Visa Records
# --------------------------------------------------------------------------- #
def _list_visa_records() -> None:
    status = _prompt("Status filter (pending/active/expired/withdrawn/"
                     "curtailed/completed, blank = all)")
    records = vs.list_visa_records(status=status or None)
    if not records:
        print("\nNo visa records found.")
        return
    print(f"\n{'ID':<5}{'Student':<14}{'Nationality':<16}{'Type':<16}"
          f"{'Visa Expiry':<13}Status")
    print("-" * 78)
    for r in records:
        print(f"{r['id']:<5}{(r.get('student_id') or '')[:13]:<14}"
              f"{(r.get('nationality') or '-')[:15]:<16}"
              f"{(r.get('visa_type') or '')[:15]:<16}"
              f"{(r.get('visa_expiry_date') or '-')[:12]:<13}"
              f"{r.get('status') or ''}")


def _view_visa_record() -> None:
    sid = _prompt("Student id", )
    if not sid:
        print("Student id is required.")
        return
    record = vs.get_visa_record(sid)
    if not record:
        print(f"\nNo visa record for student {sid}.")
        return
    print(f"\n--- Visa record for {sid} ---")
    for key in ("nationality", "passport_number", "passport_expiry",
                "visa_type", "visa_number", "visa_start_date",
                "visa_expiry_date", "brp_number", "brp_expiry_date",
                "sponsor_licence_ref", "atas_required", "status", "notes",
                "created_at", "updated_at"):
        print(f"  {key:<20}: {record.get(key) if record.get(key) is not None else '-'}")
    rts = vs.has_passing_right_to_study(sid)
    print(f"\n  Right-to-study on file : {'PASS' if rts else 'MISSING'}")
    cas = vs.list_cas_for_student(sid)
    print(f"  CAS records            : {len(cas)}")
    checks = vs.list_engagement_checks(sid)
    print(f"  Engagement checks      : {len(checks)}")


def _save_visa_record() -> None:
    sid = _prompt("Student id")
    if not sid:
        print("Student id is required.")
        return
    existing = vs.get_visa_record(sid)
    if existing:
        print("  (Existing record found — blank fields keep current values.)")

    def _f(field: str, prompt_text: str) -> Optional[str]:
        current = (existing or {}).get(field)
        val = _prompt(prompt_text, default=str(current) if current else "")
        return val or None

    nationality = _f("nationality", "Nationality")
    passport_number = _f("passport_number", "Passport number")
    passport_expiry = _f("passport_expiry", "Passport expiry (YYYY-MM-DD)")
    visa_type = _prompt("Visa type",
                        default=(existing or {}).get("visa_type") or "student_route")
    visa_number = _f("visa_number", "Visa number")
    visa_start = _f("visa_start_date", "Visa start date (YYYY-MM-DD)")
    visa_expiry = _f("visa_expiry_date", "Visa expiry date (YYYY-MM-DD)")
    brp_number = _f("brp_number", "BRP number")
    brp_expiry = _f("brp_expiry_date", "BRP expiry date (YYYY-MM-DD)")
    sponsor_ref = _f("sponsor_licence_ref", "Sponsor licence ref")
    atas_required = _prompt_bool(
        "ATAS clearance required?",
        default=bool((existing or {}).get("atas_required")))
    status = _prompt("Status (pending/active/expired/withdrawn/curtailed/"
                     "completed)", default=(existing or {}).get("status") or "pending")
    notes = _f("notes", "Notes")
    try:
        rec = vs.VisaRecord(
            student_id=sid, nationality=nationality,
            passport_number=passport_number, passport_expiry=passport_expiry,
            visa_type=visa_type, visa_number=visa_number,
            visa_start_date=visa_start, visa_expiry_date=visa_expiry,
            brp_number=brp_number, brp_expiry_date=brp_expiry,
            sponsor_licence_ref=sponsor_ref, atas_required=atas_required,
            status=status, notes=notes,
        )
        row_id = vs.upsert_visa_record(rec)
        verb = "Updated" if existing else "Created"
        print(f"\n✓ {verb} visa record for {sid} (id={row_id}).")
    except Exception as e:
        print(f"\n✗ {e}")


def _list_expiring_visas() -> None:
    within = _prompt_int("Expiring within N days (default 90)") or 90
    rows = vs.list_expiring_visas(within_days=within)
    if not rows:
        print(f"\nNo visas/BRPs expiring within {within} days.")
        return
    print(f"\n{'Student':<14}{'Visa Expiry':<14}{'BRP Expiry':<14}{'Status'}")
    print("-" * 55)
    for r in rows:
        print(f"{(r.get('student_id') or '')[:13]:<14}"
              f"{(r.get('visa_expiry_date') or '-')[:13]:<14}"
              f"{(r.get('brp_expiry_date') or '-')[:13]:<14}"
              f"{r.get('status') or ''}")


def _visa_records_menu(auth) -> None:
    while True:
        _header("Visa Records")
        print("[1] List visa records")
        print("[2] View visa record (+ compliance summary)")
        print("[3] Save / update visa record")
        print("[4] List expiring visas/BRPs")
        print("[0] Back")
        choice = input("\nChoice: ").strip()
        if choice == "1":
            _list_visa_records()
        elif choice == "2":
            _view_visa_record()
        elif choice == "3":
            _save_visa_record()
        elif choice == "4":
            _list_expiring_visas()
        elif choice == "0":
            return
        else:
            print("Invalid choice.")
            continue
        _pause()


# --------------------------------------------------------------------------- #
# 2. CAS Issuance
# --------------------------------------------------------------------------- #
def _list_cas() -> None:
    sid = _prompt("Student id")
    if not sid:
        print("Student id is required.")
        return
    rows = vs.list_cas_for_student(sid)
    if not rows:
        print(f"\nNo CAS records for student {sid}.")
        return
    print(f"\n{'CAS Number':<20}{'Programme':<22}{'Fee £':<12}{'Paid £':<12}Status")
    print("-" * 78)
    for c in rows:
        fee = c.get("tuition_fee_gbp")
        paid = c.get("tuition_fee_paid_gbp")
        print(f"{(c.get('cas_number') or '')[:19]:<20}"
              f"{(c.get('programme') or '')[:21]:<22}"
              f"{(f'{fee:.2f}' if fee is not None else '-'):<12}"
              f"{(f'{paid:.2f}' if paid is not None else '-'):<12}"
              f"{c.get('status') or ''}")


def _issue_cas(auth) -> None:
    sid = _prompt("Student id")
    programme = _prompt("Programme")
    if not sid or not programme:
        print("Student id and programme are required.")
        return
    start = _prompt("Course start date (YYYY-MM-DD)")
    end = _prompt("Course end date (YYYY-MM-DD)")
    tuition = _prompt_float("Tuition fee (GBP)", allow_blank=False)
    living = _prompt_float("Living costs (GBP, optional)") or 0
    cas_number = _prompt("CAS number (blank = auto-generate)")
    try:
        cas = vs.issue_cas(
            sid, programme, start, end, tuition, living_costs_gbp=living,
            issued_by=_current_user_id(auth), cas_number=cas_number or None)
        print(f"\n✓ Issued CAS {cas.get('cas_number')} for student {sid}.")
    except Exception as e:
        print(f"\n✗ {e}")


def _withdraw_cas() -> None:
    cas_number = _prompt("CAS number to withdraw")
    if not cas_number:
        print("CAS number is required.")
        return
    reason = _prompt("Withdrawal reason")
    try:
        if vs.withdraw_cas(cas_number, reason):
            print(f"\n✓ Withdrew CAS {cas_number}.")
        else:
            print(f"\nNo issuable CAS with number {cas_number} (already withdrawn?).")
    except Exception as e:
        print(f"\n✗ {e}")


def _cas_menu(auth) -> None:
    while True:
        _header("CAS Issuance")
        print("[1] List CAS records for a student")
        print("[2] Issue CAS")
        print("[3] Withdraw CAS")
        print("[0] Back")
        choice = input("\nChoice: ").strip()
        if choice == "1":
            _list_cas()
        elif choice == "2":
            _issue_cas(auth)
        elif choice == "3":
            _withdraw_cas()
        elif choice == "0":
            return
        else:
            print("Invalid choice.")
            continue
        _pause()


# --------------------------------------------------------------------------- #
# 3. Right-to-Study Checks
# --------------------------------------------------------------------------- #
def _record_rts(auth) -> None:
    sid = _prompt("Student id")
    if not sid:
        print("Student id is required.")
        return
    method = _prompt("Method (e.g. share_code/in_person/document)", default="share_code")
    documents = _prompt("Documents seen")
    outcome = _prompt("Outcome (pass/fail)", default="pass")
    notes = _prompt("Notes (optional)")
    try:
        rid = vs.record_right_to_study_check(
            sid, method, documents, outcome=outcome, notes=notes or None,
            checked_by=_current_user_id(auth))
        print(f"\n✓ Recorded right-to-study check {rid} for {sid} ({outcome}).")
    except Exception as e:
        print(f"\n✗ {e}")


def _check_rts() -> None:
    sid = _prompt("Student id")
    if not sid:
        print("Student id is required.")
        return
    try:
        ok = vs.has_passing_right_to_study(sid)
        print(f"\n{sid}: right-to-study {'PASS on file ✓' if ok else 'MISSING ✗'}")
    except Exception as e:
        print(f"\n✗ {e}")


def _rts_menu(auth) -> None:
    while True:
        _header("Right-to-Study Checks")
        print("[1] Record a right-to-study check")
        print("[2] Check a student's right-to-study status")
        print("[0] Back")
        choice = input("\nChoice: ").strip()
        if choice == "1":
            _record_rts(auth)
        elif choice == "2":
            _check_rts()
        elif choice == "0":
            return
        else:
            print("Invalid choice.")
            continue
        _pause()


# --------------------------------------------------------------------------- #
# 4. Engagement Checks
# --------------------------------------------------------------------------- #
def _list_engagement() -> None:
    sid = _prompt("Student id")
    if not sid:
        print("Student id is required.")
        return
    rows = vs.list_engagement_checks(sid)
    if not rows:
        print(f"\nNo engagement checks for student {sid}.")
        return
    print(f"\n{'ID':<5}{'Date':<12}{'Term':<12}{'Method':<20}Outcome")
    print("-" * 62)
    for c in rows:
        print(f"{c['id']:<5}{(c.get('check_date') or '')[:11]:<12}"
              f"{(c.get('term') or '-')[:11]:<12}"
              f"{(c.get('method') or '')[:19]:<20}"
              f"{c.get('outcome') or ''}")


def _record_engagement(auth) -> None:
    sid = _prompt("Student id")
    if not sid:
        print("Student id is required.")
        return
    term = _prompt("Term (e.g. Term 1)")
    method = _prompt("Method (e.g. attendance/tutorial/submission)", default="attendance")
    outcome = _prompt("Outcome (engaged/partial/missed)", default="engaged")
    evidence = _prompt("Evidence (optional)")
    check_date = _prompt("Check date (YYYY-MM-DD, blank = today)")
    try:
        cid = vs.record_engagement_check(
            sid, term, method, outcome=outcome, evidence=evidence or None,
            recorded_by=_current_user_id(auth), check_date=check_date or None)
        print(f"\n✓ Recorded engagement check {cid} for {sid} ({outcome}).")
        if outcome == "missed":
            print("  (A 'missed_engagement' change-of-circumstance was auto-raised.)")
    except Exception as e:
        print(f"\n✗ {e}")


def _list_overdue_engagement() -> None:
    days = _prompt_int("Overdue if last check older than N days (default 90)") or 90
    try:
        ids = vs.students_with_overdue_engagement(days_since=days)
    except Exception as e:
        print(f"\n✗ {e}")
        return
    if not ids:
        print(f"\nNo active-visa students overdue by {days} days.")
        return
    print(f"\n{len(ids)} student(s) overdue for an engagement check:")
    for sid in ids:
        print(f"  - {sid}")


def _list_at_risk() -> None:
    min_pct = _prompt_float("At-risk attendance threshold % (default 80)") or 80.0
    try:
        rows = vs.get_attendance_at_risk(min_pct=min_pct)
    except Exception as e:
        print(f"\n✗ {e}")
        return
    if not rows:
        print("\nNo at-risk students (or attendance module not installed).")
        return
    print(f"\n{'Student':<14}{'Name':<26}{'Attend %':<10}Missed")
    print("-" * 58)
    for r in rows:
        pct = r.get("attendance_pct")
        print(f"{(str(r.get('student_id') or ''))[:13]:<14}"
              f"{(r.get('name') or '')[:25]:<26}"
              f"{(f'{pct:.1f}' if pct is not None else '-'):<10}"
              f"{r.get('missed_sessions') if r.get('missed_sessions') is not None else '-'}")


def _import_engagement() -> None:
    sid = _prompt("Student id filter (blank = all)")
    since = _prompt("Only events since (YYYY-MM-DD, optional)")
    try:
        n = vs.import_attendance_engagement_events(
            student_id=sid or None, since=since or None)
        print(f"\n✓ Mirrored {n} attendance engagement event(s).")
    except Exception as e:
        print(f"\n✗ {e}")


def _engagement_menu(auth) -> None:
    while True:
        _header("Engagement Checks")
        print("[1] List engagement checks for a student")
        print("[2] Record an engagement check")
        print("[3] List students with overdue engagement")
        print("[4] List attendance at-risk students")
        print("[5] Import engagement events from attendance pipeline")
        print("[0] Back")
        choice = input("\nChoice: ").strip()
        if choice == "1":
            _list_engagement()
        elif choice == "2":
            _record_engagement(auth)
        elif choice == "3":
            _list_overdue_engagement()
        elif choice == "4":
            _list_at_risk()
        elif choice == "5":
            _import_engagement()
        elif choice == "0":
            return
        else:
            print("Invalid choice.")
            continue
        _pause()


# --------------------------------------------------------------------------- #
# 5. Changes of Circumstance (10-day UKVI clock)
# --------------------------------------------------------------------------- #
def _list_pending_coc() -> None:
    only_overdue = _prompt_bool("Only overdue reports?", default=False)
    rows = vs.list_pending_coc(only_overdue=only_overdue)
    if not rows:
        print("\nNo pending changes of circumstance.")
        return
    print(f"\n{'ID':<5}{'Student':<14}{'Type':<20}{'Occurred':<12}Report Due")
    print("-" * 66)
    for c in rows:
        print(f"{c['id']:<5}{(c.get('student_id') or '')[:13]:<14}"
              f"{(c.get('change_type') or '')[:19]:<20}"
              f"{(c.get('occurred_on') or '')[:11]:<12}"
              f"{c.get('ukvi_report_due') or '-'}")


def _log_coc(auth) -> None:
    sid = _prompt("Student id")
    print(f"  Valid change types: {', '.join(vs.COC_TYPES)}")
    change_type = _prompt("Change type")
    if not sid or not change_type:
        print("Student id and change type are required.")
        return
    details = _prompt("Details (optional)")
    occurred = _prompt("Occurred on (YYYY-MM-DD, blank = today)")
    try:
        cid = vs.log_change_of_circumstance(
            sid, change_type, details=details or None,
            occurred_on=occurred or None, recorded_by=_current_user_id(auth))
        print(f"\n✓ Opened change-of-circumstance {cid} (UKVI 10-day clock started).")
    except Exception as e:
        print(f"\n✗ {e}")


def _mark_coc_reported() -> None:
    coc_id = _prompt_int("Change-of-circumstance id", allow_blank=False)
    reference = _prompt("UKVI report reference")
    if not reference:
        print("A UKVI reference is required.")
        return
    try:
        if vs.mark_coc_reported(coc_id, reference):
            print(f"\n✓ Marked CoC {coc_id} reported (ref {reference}).")
        else:
            print(f"\nNo change-of-circumstance with id {coc_id}.")
    except Exception as e:
        print(f"\n✗ {e}")


def _coc_menu(auth) -> None:
    while True:
        _header("Changes of Circumstance")
        print("[1] List pending changes (optionally overdue only)")
        print("[2] Log a change of circumstance")
        print("[3] Mark a change reported to UKVI")
        print("[0] Back")
        choice = input("\nChoice: ").strip()
        if choice == "1":
            _list_pending_coc()
        elif choice == "2":
            _log_coc(auth)
        elif choice == "3":
            _mark_coc_reported()
        elif choice == "0":
            return
        else:
            print("Invalid choice.")
            continue
        _pause()


# --------------------------------------------------------------------------- #
# 6. ATAS Clearance
# --------------------------------------------------------------------------- #
def _record_atas() -> None:
    sid = _prompt("Student id")
    if not sid:
        print("Student id is required.")
        return
    module_code = _prompt("Module code (optional)")
    certificate = _prompt("Certificate number (optional)")
    issued_on = _prompt("Issued on (YYYY-MM-DD, optional)")
    expires_on = _prompt("Expires on (YYYY-MM-DD, optional)")
    status = _prompt("Status (cleared/pending/rejected)", default="cleared")
    notes = _prompt("Notes (optional)")
    try:
        aid = vs.record_atas_clearance(
            sid, module_code or None, certificate or None,
            issued_on or None, expires_on or None,
            status=status, notes=notes or None)
        print(f"\n✓ Recorded ATAS clearance {aid} for {sid} ({status}).")
    except Exception as e:
        print(f"\n✗ {e}")


def _check_atas() -> None:
    sid = _prompt("Student id")
    if not sid:
        print("Student id is required.")
        return
    module_code = _prompt("Module code (blank = any)")
    try:
        ok = vs.has_valid_atas(sid, module_code=module_code or None)
        scope = f" for {module_code}" if module_code else ""
        print(f"\n{sid}: valid ATAS{scope}: {'YES ✓' if ok else 'NO ✗'}")
    except Exception as e:
        print(f"\n✗ {e}")


def _atas_menu(auth) -> None:
    while True:
        _header("ATAS Clearance")
        print("[1] Record an ATAS clearance")
        print("[2] Check a student's ATAS validity")
        print("[0] Back")
        choice = input("\nChoice: ").strip()
        if choice == "1":
            _record_atas()
        elif choice == "2":
            _check_atas()
        elif choice == "0":
            return
        else:
            print("Invalid choice.")
            continue
        _pause()


# --------------------------------------------------------------------------- #
# 7. Expiry Alerts
# --------------------------------------------------------------------------- #
def _run_expiry_alerts() -> None:
    threshold = _prompt_int("Alert threshold days (default 90)") or 90
    if not _prompt_bool(
            f"Send visa-expiry warning emails for visas expiring within "
            f"{threshold} days?", default=False):
        print("Cancelled.")
        return
    try:
        sent = vs.run_visa_expiry_alerts(threshold_days=threshold)
        print(f"\n✓ Sent {sent} visa-expiry warning email(s).")
    except Exception as e:
        print(f"\n✗ {e}")


def _run_scheduled_alerts() -> None:
    if not _prompt_bool(
            "Run the daily de-duplicated expiry alert sweep now?", default=False):
        print("Cancelled.")
        return
    try:
        sent = vs.run_scheduled_visa_expiry_alerts()
        print(f"\n✓ Daily sweep sent {sent} email(s).")
    except Exception as e:
        print(f"\n✗ {e}")


def _alerts_menu(auth) -> None:
    while True:
        _header("Visa/BRP Expiry Alerts")
        print("[1] List expiring visas/BRPs")
        print("[2] Send expiry warning emails (threshold)")
        print("[3] Run daily de-duplicated alert sweep")
        print("[0] Back")
        choice = input("\nChoice: ").strip()
        if choice == "1":
            _list_expiring_visas()
        elif choice == "2":
            _run_expiry_alerts()
        elif choice == "3":
            _run_scheduled_alerts()
        elif choice == "0":
            return
        else:
            print("Invalid choice.")
            continue
        _pause()


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def run_visa_compliance_menu(auth) -> None:
    """Run the International Student Visa Sponsorship & Compliance CLI loop."""
    while True:
        print("\n" + "=" * 50)
        print("    INTERNATIONAL VISA SPONSORSHIP & COMPLIANCE")
        print("=" * 50)
        print("1. Visa Records")
        print("2. CAS Issuance")
        print("3. Right-to-Study Checks")
        print("4. Engagement Checks")
        print("5. Changes of Circumstance")
        print("6. ATAS Clearance")
        print("7. Visa/BRP Expiry Alerts")
        print("8. Return to Main Menu")
        print("=" * 50)

        try:
            choice = input("\nEnter your choice (1-8): ").strip()
        except (KeyboardInterrupt, EOFError):
            print()
            return

        try:
            if choice == "1":
                _visa_records_menu(auth)
            elif choice == "2":
                _cas_menu(auth)
            elif choice == "3":
                _rts_menu(auth)
            elif choice == "4":
                _engagement_menu(auth)
            elif choice == "5":
                _coc_menu(auth)
            elif choice == "6":
                _atas_menu(auth)
            elif choice == "7":
                _alerts_menu(auth)
            elif choice == "8":
                print("Returning to main menu...")
                return
            else:
                print("❌ Invalid choice.")
        except KeyboardInterrupt:
            print("\nCancelled.")
        except Exception as e:  # keep the menu resilient
            print(f"❌ Error: {e}")
