"""
Equality & Diversity — interactive CLI.

Wired to ``equality_diversity.access`` (records + incidents), ``reports_engine``
(cross-tabs, attainment gap, trends, benchmarks) and ``integrations`` (SAR
export, right-to-erasure), which all read/write the shared
``student_records.db`` via ``schema.get_connection`` — the same database the
E&D GUI (``gui/entrypoints.open_equality_diversity_gui``) uses. Anything created
here is visible in the GUI and vice-versa.

Covers: Monitoring Records, Incidents, Reports & Analytics, and Data Protection
(SAR export / right-to-erasure / deletion approvals).
"""

from __future__ import annotations

from typing import Optional

from education_system.post_18.university_system.modules.domain.student_affairs.equality_diversity import (
    access,
    integrations,
    reports_engine,
)
from education_system.post_18.university_system.modules.domain.student_affairs.equality_diversity.schema import (
    DEMOGRAPHIC_FIELDS,
    migrate,
)


# --------------------------------------------------------------------------- #
# Small input helpers
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


def _prompt_field(text: str, default: str = "gender") -> str:
    """Prompt for one of the allow-listed demographic fields."""
    print(f"  fields: {', '.join(DEMOGRAPHIC_FIELDS)}")
    while True:
        val = _prompt(text, default)
        if val in DEMOGRAPHIC_FIELDS:
            return val
        print("Please choose one of the listed fields.")


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


# --------------------------------------------------------------------------- #
# 1. Monitoring Records
# --------------------------------------------------------------------------- #
def _list_records() -> None:
    search = _prompt("Search ref/department/type/ethnicity (optional)")
    records = access.list_records(search=search)
    if not records:
        print("\nNo records found.")
        return
    print(f"\n{'ID':<6}{'Ref':<16}{'Type':<10}{'Dept':<18}{'Gender':<12}Ethnicity")
    print("-" * 84)
    for r in records:
        print(f"{r['id']:<6}{(r.get('ref_code') or '')[:15]:<16}"
              f"{(r.get('person_type') or '')[:9]:<10}"
              f"{(r.get('department') or '')[:17]:<18}"
              f"{(r.get('gender') or '')[:11]:<12}"
              f"{(r.get('ethnicity') or '')[:24]}")


def _add_record(auth) -> None:
    ref = _prompt("Reference code (unique)")
    ptype = _prompt("Person type (Student/Staff)", default="Student")
    if not ref or not ptype:
        print("Reference code and person type are required.")
        return
    department = _prompt("Department (optional)")
    age_group = _prompt("Age group (optional)")
    gender = _prompt("Gender (optional)")
    ethnicity = _prompt("Ethnicity (optional)")
    disability = _prompt("Disability (optional)")
    religion = _prompt("Religion (optional)")
    orientation = _prompt("Sexual orientation (optional)")
    nationality = _prompt("Nationality (optional)")
    salary = _prompt_float("Salary (optional, staff)")
    accommodations = _prompt("Accommodations (optional)")
    try:
        rid = access.create_record(
            ref, ptype, department=department or None, age_group=age_group or None,
            gender=gender or None, ethnicity=ethnicity or None,
            disability=disability or None, religion=religion or None,
            sexual_orientation=orientation or None, nationality=nationality or None,
            salary=salary, accommodations=accommodations or None,
            created_by=_current_username(auth))
        print(f"\n✓ Created record '{ref}' (id={rid}).")
        hit = integrations.sync_link(rid, ref)
        if hit:
            print(f"  Linked to {hit['kind']} {hit.get('name', '')}.")
    except Exception as e:
        print(f"\n✗ {e}")


def _view_record(auth) -> None:
    rid = _prompt_int("Record id", allow_blank=False)
    record = access.get_record(rid)
    if not record:
        print(f"\nNo record with id {rid}.")
        return
    print(f"\n--- Record {rid} ---")
    for key in ("ref_code", "person_type", "department", "age_group", "gender",
                "ethnicity", "disability", "religion", "sexual_orientation",
                "nationality", "salary", "accommodations", "student_id",
                "staff_id", "course", "year_of_study", "programme_level",
                "date_added", "updated_at", "deleted_at"):
        if key in record:
            print(f"  {key:<20}: {record.get(key) if record.get(key) is not None else '-'}")
    try:
        access.record_view("person", rid, _current_username(auth))
    except Exception:
        pass


def _edit_record(auth) -> None:
    rid = _prompt_int("Record id", allow_blank=False)
    record = access.get_record(rid)
    if not record:
        print(f"\nNo record with id {rid}.")
        return
    print("Leave a field blank to keep the current value.")
    updates: dict = {}
    for field_name in access.RECORD_EDITABLE_FIELDS:
        current = record.get(field_name)
        new_val = _prompt(f"{field_name} (current: {current if current is not None else '-'})")
        if new_val:
            if field_name == "salary":
                try:
                    updates[field_name] = float(new_val)
                except ValueError:
                    print(f"  Skipping salary — '{new_val}' is not a number.")
                    continue
            else:
                updates[field_name] = new_val
    if not updates:
        print("Nothing to update.")
        return
    try:
        if access.update_record(rid, updates, updated_by=_current_username(auth)):
            print(f"\n✓ Updated record {rid} ({', '.join(updates)}).")
        else:
            print(f"\nNo changes applied to record {rid}.")
    except Exception as e:
        print(f"\n✗ {e}")


def _request_delete_record(auth) -> None:
    rid = _prompt_int("Record id to request deletion", allow_blank=False)
    if not _prompt_bool(f"Soft-delete record {rid} and queue for approval?", default=False):
        print("Cancelled.")
        return
    try:
        qid = access.soft_delete_record(rid, requested_by=_current_username(auth))
        if qid is None:
            print(f"\nNo record with id {rid}.")
        else:
            print(f"\n✓ Record {rid} soft-deleted and queued for approval (#{qid}).")
    except Exception as e:
        print(f"\n✗ {e}")


def _records_menu(auth) -> None:
    while True:
        _header("Monitoring Records")
        print("[1] List records")
        print("[2] Add record")
        print("[3] View record")
        print("[4] Edit record")
        print("[5] Request delete (soft-delete + approval queue)")
        print("[0] Back")
        choice = input("\nChoice: ").strip()
        if choice == "1":
            _list_records()
        elif choice == "2":
            _add_record(auth)
        elif choice == "3":
            _view_record(auth)
        elif choice == "4":
            _edit_record(auth)
        elif choice == "5":
            _request_delete_record(auth)
        elif choice == "0":
            return
        else:
            print("Invalid choice.")
            continue
        _pause()


# --------------------------------------------------------------------------- #
# 2. Incidents
# --------------------------------------------------------------------------- #
def _list_incidents() -> None:
    status = _prompt("Status filter (Open/Under investigation/Resolved/Closed, blank = all)")
    incidents = access.list_incidents(status=status or None)
    if not incidents:
        print("\nNo incidents found.")
        return
    print(f"\n{'ID':<5}{'Date':<12}{'Category':<26}{'Sev':<10}{'Status':<20}Assignee")
    print("-" * 92)
    for i in incidents:
        print(f"{i['id']:<5}{(i.get('date_reported') or '')[:10]:<12}"
              f"{(i.get('category') or '')[:25]:<26}"
              f"{(i.get('severity') or '')[:9]:<10}"
              f"{(i.get('status') or '')[:19]:<20}"
              f"{i.get('assigned_to') or '-'}")


def _submit_incident(auth) -> None:
    category = _prompt("Category (e.g. Harassment, Racial discrimination)")
    if not category:
        print("Category is required.")
        return
    department = _prompt("Department (optional)")
    severity = _prompt("Severity (Low/Medium/High/Critical)", default="Medium")
    description = _prompt("Description")
    if not description:
        print("Description is required.")
        return
    respondent = _prompt("Respondent ref (optional)")
    witnesses = _prompt("Witnesses (comma-separated refs, optional)")
    anonymous = _prompt_bool("Report anonymously?", default=False)
    try:
        iid = access.create_incident(
            category, department=department or None, description=description,
            severity=severity, reported_by=_current_username(auth),
            respondent=respondent or None, witnesses=witnesses or None,
            anonymous=anonymous)
        print(f"\n✓ Submitted incident {iid} ({category}, {severity}).")
    except Exception as e:
        print(f"\n✗ {e}")


def _view_incident(auth) -> None:
    iid = _prompt_int("Incident id", allow_blank=False)
    incident = access.get_incident(iid)
    if not incident:
        print(f"\nNo incident with id {iid}.")
        return
    print(f"\n--- Incident {iid} ---")
    for key in ("date_reported", "category", "department", "severity", "status",
                "sla_deadline", "reported_by", "assigned_to", "respondent",
                "witnesses", "outcome", "resolution_category", "referred_to"):
        if key in incident:
            print(f"  {key:<20}: {incident.get(key) if incident.get(key) is not None else '-'}")
    print(f"\n  description        : {incident.get('description') or '-'}")
    try:
        access.record_view("incident", iid, _current_username(auth))
    except Exception:
        pass


def _update_incident_status(auth) -> None:
    iid = _prompt_int("Incident id", allow_blank=False)
    status = _prompt("New status (Open/Under investigation/Resolved/Closed)")
    if not status:
        print("Status is required.")
        return
    try:
        if access.update_incident_status(iid, status, actor=_current_username(auth)):
            print(f"\n✓ Updated incident {iid} → {status}.")
        else:
            print(f"\nNo incident with id {iid}.")
    except Exception as e:
        print(f"\n✗ {e}")


def _assign_incident(auth) -> None:
    iid = _prompt_int("Incident id", allow_blank=False)
    assignee = _prompt("Assignee username")
    if not assignee:
        print("Assignee is required.")
        return
    try:
        if access.assign_incident(iid, assignee, actor=_current_username(auth)):
            print(f"\n✓ Assigned incident {iid} to {assignee}.")
        else:
            print(f"\nNo incident with id {iid}.")
    except Exception as e:
        print(f"\n✗ {e}")


def _refer_incident(auth) -> None:
    iid = _prompt_int("Incident id", allow_blank=False)
    reason = _prompt("Reason for safeguarding referral")
    if not reason:
        print("Reason is required.")
        return
    try:
        ok = integrations.refer_to_safeguarding(iid, _current_username(auth), reason)
        print("\n✓ Referred to safeguarding." if ok
              else "\n✗ Safeguarding module unavailable.")
    except Exception as e:
        print(f"\n✗ {e}")


def _incidents_menu(auth) -> None:
    while True:
        _header("Incidents")
        print("[1] List incidents")
        print("[2] Submit incident")
        print("[3] View incident")
        print("[4] Update status")
        print("[5] Assign incident")
        print("[6] Refer to safeguarding")
        print("[0] Back")
        choice = input("\nChoice: ").strip()
        if choice == "1":
            _list_incidents()
        elif choice == "2":
            _submit_incident(auth)
        elif choice == "3":
            _view_incident(auth)
        elif choice == "4":
            _update_incident_status(auth)
        elif choice == "5":
            _assign_incident(auth)
        elif choice == "6":
            _refer_incident(auth)
        elif choice == "0":
            return
        else:
            print("Invalid choice.")
            continue
        _pause()


# --------------------------------------------------------------------------- #
# 3. Reports & Analytics
# --------------------------------------------------------------------------- #
def _report_cross_tab() -> None:
    row_field = _prompt_field("Row field", default="gender")
    col_field = _prompt_field("Column field", default="ethnicity")
    try:
        table = reports_engine.cross_tab(row_field, col_field)
    except Exception as e:
        print(f"\n✗ {e}")
        return
    col_keys = table["col_keys"]
    cells = table["cells"]
    if not table["row_keys"]:
        print("\nNo data (or all cells suppressed for n < 5).")
        return
    print(f"\n{row_field} \\ {col_field}  (cells with n<5 suppressed to 0)")
    header = f"{'':<20}" + "".join(f"{(c or '(blank)')[:12]:<14}" for c in col_keys)
    print(header)
    print("-" * len(header))
    for r in table["row_keys"]:
        line = f"{(r or '(blank)')[:19]:<20}"
        line += "".join(f"{cells.get((r, c), 0):<14}" for c in col_keys)
        print(line)


def _report_attainment_gap() -> None:
    field = _prompt_field("Group by field", default="ethnicity")
    try:
        rows = reports_engine.attainment_gap(field)
    except Exception as e:
        print(f"\n✗ {e}")
        return
    if not rows:
        print("\nNo attainment data (needs a linked 'grades' table; n<5 suppressed).")
        return
    print(f"\n{'Category':<32}{'Mean score':<14}Students")
    print("-" * 58)
    for cat, mean, n in rows:
        print(f"{(cat or '(blank)')[:31]:<32}{mean:<14.1f}{n}")


def _report_trend() -> None:
    field = _prompt_field("Field for year-on-year trend", default="gender")
    try:
        rows = reports_engine.yearly_trend(field)
    except Exception as e:
        print(f"\n✗ {e}")
        return
    if not rows:
        print("\nNo trend data (n<5 suppressed).")
        return
    print(f"\n{'Year':<8}{'Category':<32}Count")
    print("-" * 48)
    for yr, cat, n in rows:
        print(f"{(yr or '?'):<8}{(cat or '(blank)')[:31]:<32}{n}")


def _report_benchmark() -> None:
    field = _prompt_field("Field to compare vs baseline", default="gender")
    try:
        rows = reports_engine.benchmark_comparison(field)
    except Exception as e:
        print(f"\n✗ {e}")
        return
    if not rows:
        print("\nNo data to compare.")
        return
    print(f"\n{'Category':<28}{'Observed %':<12}{'Baseline %':<12}Delta pp")
    print("-" * 62)
    for cat, obs, base, delta in rows:
        print(f"{(cat or '(blank)')[:27]:<28}{obs:<12.1f}{base:<12.1f}{delta:+.1f}")


def _report_pay_gap() -> None:
    field = _prompt_field("Group pay gap by field", default="gender")
    try:
        rows = reports_engine.pay_gap(field)
    except Exception as e:
        print(f"\n✗ {e}")
        return
    if not rows:
        print("\nNo staff salary data (n<5 suppressed).")
        return
    print(f"\n{'Group':<28}{'Mean salary':<16}Staff (n)")
    print("-" * 54)
    for group, mean, n in rows:
        print(f"{(group or '(blank)')[:27]:<28}£{mean:<15.2f}{n}")


def _report_data_quality() -> None:
    dq = reports_engine.data_quality()
    print(f"\nTotal records : {dq['total_records']}")
    print(f"Linked to roster : {dq['linked']}")
    print(f"Open incidents : {dq['incidents_open']}")
    print(f"\n{'Field':<20}{'Missing':<10}Total")
    print("-" * 40)
    for f, (missing, total) in dq["per_field_missing"].items():
        print(f"{f:<20}{missing:<10}{total}")


def _reports_menu(auth) -> None:
    while True:
        _header("Reports & Analytics")
        print("[1] Cross-tab (two demographic fields)")
        print("[2] Attainment gap (mean grade by demographic)")
        print("[3] Year-on-year trend")
        print("[4] Benchmark vs baseline")
        print("[5] Pay gap (staff)")
        print("[6] Data quality dashboard")
        print("[0] Back")
        choice = input("\nChoice: ").strip()
        if choice == "1":
            _report_cross_tab()
        elif choice == "2":
            _report_attainment_gap()
        elif choice == "3":
            _report_trend()
        elif choice == "4":
            _report_benchmark()
        elif choice == "5":
            _report_pay_gap()
        elif choice == "6":
            _report_data_quality()
        elif choice == "0":
            return
        else:
            print("Invalid choice.")
            continue
        _pause()


# --------------------------------------------------------------------------- #
# 4. Data Protection & Rights
# --------------------------------------------------------------------------- #
def _sar_export() -> None:
    ref = _prompt("Reference code (ref_code) to export")
    if not ref:
        print("Reference code is required.")
        return
    result = integrations.sar_export(ref)
    if not result.get("found"):
        print(f"\nNo record held for '{ref}'.")
        return
    record = result["record"]
    print(f"\n--- Subject Access Report: {ref} ---")
    print(f"  person id   : {record.get('id')}")
    print(f"  person_type : {record.get('person_type')}")
    print(f"  department  : {record.get('department') or '-'}")
    for f in DEMOGRAPHIC_FIELDS:
        print(f"  {f:<20}: {record.get(f) or '-'}")
    print(f"\n  Incidents linked : {len(result.get('incidents', []))}")
    print(f"  View-log entries : {len(result.get('view_log', []))}")
    consent = result.get("consent")
    print(f"  Consent on file  : {consent['flags'] if consent else '-'}")


def _erase_person(auth) -> None:
    ref = _prompt("Reference code (ref_code) to ERASE permanently")
    if not ref:
        print("Reference code is required.")
        return
    if not _prompt_bool(f"Permanently erase all data for '{ref}'? This cannot be undone",
                        default=False):
        print("Cancelled.")
        return
    try:
        rows = integrations.erase_person(ref, _current_username(auth))
        if rows:
            print(f"\n✓ Erased '{ref}' — {rows} row(s) affected.")
        else:
            print(f"\nNo record held for '{ref}'.")
    except Exception as e:
        print(f"\n✗ {e}")


def _list_pending_deletions() -> None:
    rows = access.list_pending_deletions()
    if not rows:
        print("\nNo deletions pending approval.")
        return
    print(f"\n{'QueueID':<9}{'Entity':<10}{'EntityID':<10}{'Requested by':<20}Requested at")
    print("-" * 70)
    for qid, entity, entity_id, requested_by, requested_at in rows:
        print(f"{qid:<9}{(entity or '')[:9]:<10}{str(entity_id):<10}"
              f"{(requested_by or '')[:19]:<20}{requested_at or ''}")


def _approve_deletion(auth) -> None:
    qid = _prompt_int("Deletion queue id to approve", allow_blank=False)
    approver = _current_username(auth)
    try:
        result = access.approve_deletion(qid, approver)
        if result is None:
            print("\n✗ Cannot approve (already approved, not found, or self-approval).")
        else:
            entity, entity_id, _snap = result
            print(f"\n✓ Approved deletion #{qid} for {entity} {entity_id}.")
    except Exception as e:
        print(f"\n✗ {e}")


def _data_protection_menu(auth) -> None:
    while True:
        _header("Data Protection & Rights")
        print("[1] Subject Access Request (SAR) export")
        print("[2] Right-to-erasure (hard delete)")
        print("[3] List pending deletions")
        print("[4] Approve a pending deletion")
        print("[0] Back")
        choice = input("\nChoice: ").strip()
        if choice == "1":
            _sar_export()
        elif choice == "2":
            _erase_person(auth)
        elif choice == "3":
            _list_pending_deletions()
        elif choice == "4":
            _approve_deletion(auth)
        elif choice == "0":
            return
        else:
            print("Invalid choice.")
            continue
        _pause()


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def run_equality_diversity_menu(auth) -> None:
    """Run the Equality & Diversity CLI loop."""
    try:
        migrate()
    except Exception as e:
        print(f"⚠ Could not verify E&D schema: {e}")

    while True:
        print("\n" + "=" * 50)
        print("    EQUALITY & DIVERSITY")
        print("=" * 50)
        print("1. Monitoring Records")
        print("2. Incidents")
        print("3. Reports & Analytics")
        print("4. Data Protection & Rights")
        print("5. Return to Main Menu")
        print("=" * 50)

        try:
            choice = input("\nEnter your choice (1-5): ").strip()
        except (KeyboardInterrupt, EOFError):
            print()
            return

        try:
            if choice == "1":
                _records_menu(auth)
            elif choice == "2":
                _incidents_menu(auth)
            elif choice == "3":
                _reports_menu(auth)
            elif choice == "4":
                _data_protection_menu(auth)
            elif choice == "5":
                print("Returning to main menu...")
                return
            else:
                print("❌ Invalid choice.")
        except KeyboardInterrupt:
            print("\nCancelled.")
        except Exception as e:  # keep the menu resilient
            print(f"❌ Error: {e}")
