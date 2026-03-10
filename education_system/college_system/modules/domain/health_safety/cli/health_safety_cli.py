"""Health & Safety CLI module."""

from education_system.college_system.modules.shared.cli.cli_main import (
    print_header, print_menu, get_choice,
)
from education_system.college_system.modules.domain.health_safety.services.health_safety_service import (
    HealthSafetyService,
)
from education_system.college_system.infrastructure.auth.core import UserAuth


def health_safety_menu(auth: UserAuth):
    """Health & Safety management menu."""
    svc = HealthSafetyService(auth._db_path)

    while True:
        print_header("Health & Safety")
        options = [
            ("1", "List Incidents"),
            ("2", "View Incident"),
            ("3", "Report Incident"),
            ("4", "Update Incident"),
            ("5", "Close Incident"),
            ("6", "Delete Incident"),
            ("7", "List Inspections"),
            ("8", "New Inspection"),
            ("9", "Update Inspection"),
            ("10", "List Risk Assessments"),
            ("11", "New Risk Assessment"),
            ("12", "Update Risk Assessment"),
            ("13", "List Compliance Checks"),
            ("14", "New Compliance Check"),
            ("15", "Update Compliance Check"),
            ("16", "Overdue Checks"),
            ("17", "Statistics"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "0":
            break
        elif choice == "1":
            _list_incidents(svc)
        elif choice == "2":
            _view_incident(svc)
        elif choice == "3":
            _report_incident(svc)
        elif choice == "4":
            _update_incident(svc)
        elif choice == "5":
            _close_incident(svc)
        elif choice == "6":
            _delete_incident(svc)
        elif choice == "7":
            _list_inspections(svc)
        elif choice == "8":
            _new_inspection(svc)
        elif choice == "9":
            _update_inspection(svc)
        elif choice == "10":
            _list_risk_assessments(svc)
        elif choice == "11":
            _new_risk_assessment(svc)
        elif choice == "12":
            _update_risk_assessment(svc)
        elif choice == "13":
            _list_compliance_checks(svc)
        elif choice == "14":
            _new_compliance_check(svc)
        elif choice == "15":
            _update_compliance_check(svc)
        elif choice == "16":
            _overdue_checks(svc)
        elif choice == "17":
            _show_statistics(svc)
        else:
            print("\n  Invalid option.")


# ── Incidents ─────────────────────────────────────────────────────────────────


def _list_incidents(svc):
    print_header("List Incidents")
    try:
        status_filter = input("  Filter by status (open/investigating/action_required/closed) [all]: ").strip() or None
        type_filter = input("  Filter by type (accident/near_miss/...) [all]: ").strip() or None
        riddor = input("  RIDDOR only? (y/n) [n]: ").strip().lower() == "y"
        items = svc.list_incidents(status=status_filter, incident_type=type_filter, riddor_only=riddor)
        if not items:
            print("\n  No incidents found.")
            return
        print(f"\n  {'ID':<6}{'Date':<12}{'Type':<20}{'Location':<15}{'RIDDOR':<8}{'Status':<15}")
        print(f"  {'-' * 76}")
        for item in items:
            riddor_str = "Yes" if item.get("riddor_reportable") else "No"
            print(f"  {str(item['id']):<6}{str(item.get('incident_date', '') or ''):<12}"
                  f"{str(item.get('incident_type', '') or '')[:18]:<20}"
                  f"{str(item.get('location', '') or '')[:13]:<15}"
                  f"{riddor_str:<8}{str(item.get('status', '') or ''):<15}")
        print(f"\n  Total: {len(items)} incident(s)")
    except Exception as e:
        print(f"\n  Error: {e}")


def _view_incident(svc):
    print_header("View Incident")
    try:
        pk = int(input("  Enter incident ID: ").strip())
        item = svc.get_incident(pk)
        if not item:
            print("\n  Incident not found.")
            return
        print()
        for k, v in item.items():
            print(f"  {k}: {v}")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _report_incident(svc):
    print_header("Report New Incident")
    try:
        incident_date = input("  Date (YYYY-MM-DD): ").strip()
        description = input("  Description: ").strip()
        if not incident_date or not description:
            print("\n  Date and description are required.")
            return
        data = {}
        for field in ["reported_by", "location", "incident_type", "persons_involved",
                       "injury_details"]:
            val = input(f"  {field}: ").strip()
            if val:
                data[field] = val
        fa = input("  First aid given? (y/n) [n]: ").strip().lower()
        if fa == "y":
            data["first_aid_given"] = 1
        riddor = input("  RIDDOR reportable? (y/n) [n]: ").strip().lower()
        if riddor == "y":
            data["riddor_reportable"] = 1
            ref = input("  RIDDOR reference: ").strip()
            if ref:
                data["riddor_reference"] = ref
        item = svc.create_incident(incident_date, description, **data)
        print(f"\n  Incident created with ID: {item['id']}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _update_incident(svc):
    print_header("Update Incident")
    try:
        pk = int(input("  Enter incident ID: ").strip())
        item = svc.get_incident(pk)
        if not item:
            print("\n  Incident not found.")
            return
        data = {}
        for field in ["incident_date", "reported_by", "location", "incident_type",
                       "description", "persons_involved", "injury_details",
                       "investigation_notes", "status"]:
            current = item.get(field, "")
            val = input(f"  {field} [{current}]: ").strip()
            if val:
                data[field] = val
        if data:
            svc.update_incident(pk, **data)
            print("\n  Incident updated.")
        else:
            print("\n  No changes made.")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _close_incident(svc):
    print_header("Close Incident")
    try:
        pk = int(input("  Enter incident ID: ").strip())
        item = svc.get_incident(pk)
        if not item:
            print("\n  Incident not found.")
            return
        root_cause = input("  Root cause: ").strip()
        corrective_actions = input("  Corrective actions: ").strip()
        if not root_cause or not corrective_actions:
            print("\n  Both root cause and corrective actions are required.")
            return
        svc.close_incident(pk, root_cause, corrective_actions)
        print("\n  Incident closed.")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _delete_incident(svc):
    print_header("Delete Incident")
    try:
        pk = int(input("  Enter incident ID: ").strip())
        confirm = input(f"  Delete incident {pk}? (y/n): ").strip().lower()
        if confirm == "y":
            svc.delete_incident(pk)
            print("\n  Incident deleted.")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


# ── Inspections ───────────────────────────────────────────────────────────────


def _list_inspections(svc):
    print_header("List Inspections")
    try:
        status_filter = input("  Filter by status (passed/failed/conditional/pending) [all]: ").strip() or None
        items = svc.list_inspections(status=status_filter)
        if not items:
            print("\n  No inspections found.")
            return
        print(f"\n  {'ID':<6}{'Type':<18}{'Area':<14}{'Inspector':<14}{'Date':<12}{'Next Due':<12}{'Status':<10}")
        print(f"  {'-' * 86}")
        for item in items:
            print(f"  {str(item['id']):<6}{str(item.get('inspection_type', '') or '')[:16]:<18}"
                  f"{str(item.get('area', '') or '')[:12]:<14}"
                  f"{str(item.get('inspector', '') or '')[:12]:<14}"
                  f"{str(item.get('inspection_date', '') or ''):<12}"
                  f"{str(item.get('next_due_date', '') or ''):<12}"
                  f"{str(item.get('status', '') or ''):<10}")
        print(f"\n  Total: {len(items)} inspection(s)")
    except Exception as e:
        print(f"\n  Error: {e}")


def _new_inspection(svc):
    print_header("New Inspection")
    try:
        inspection_type = input("  Inspection type: ").strip()
        inspection_date = input("  Date (YYYY-MM-DD): ").strip()
        if not inspection_type or not inspection_date:
            print("\n  Type and date are required.")
            return
        data = {}
        for field in ["area", "inspector", "next_due_date", "findings",
                       "actions_required", "certificate_ref", "status"]:
            val = input(f"  {field}: ").strip()
            if val:
                data[field] = val
        item = svc.create_inspection(inspection_type, inspection_date, **data)
        print(f"\n  Inspection created with ID: {item['id']}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _update_inspection(svc):
    print_header("Update Inspection")
    try:
        pk = int(input("  Enter inspection ID: ").strip())
        item = svc.get_inspection(pk)
        if not item:
            print("\n  Inspection not found.")
            return
        data = {}
        for field in ["inspection_type", "area", "inspector", "inspection_date",
                       "next_due_date", "findings", "actions_required",
                       "certificate_ref", "status"]:
            current = item.get(field, "")
            val = input(f"  {field} [{current}]: ").strip()
            if val:
                data[field] = val
        if data:
            svc.update_inspection(pk, **data)
            print("\n  Inspection updated.")
        else:
            print("\n  No changes made.")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


# ── Risk Assessments ──────────────────────────────────────────────────────────


def _list_risk_assessments(svc):
    print_header("List Risk Assessments")
    try:
        status_filter = input("  Filter by status (active/review_due/archived) [all]: ").strip() or None
        rating_filter = input("  Filter by rating (low/medium/high/very_high) [all]: ").strip() or None
        items = svc.list_risk_assessments(status=status_filter, risk_rating=rating_filter)
        if not items:
            print("\n  No risk assessments found.")
            return
        print(f"\n  {'ID':<6}{'Activity':<20}{'Location':<14}{'Assessor':<14}{'Date':<12}{'Rating':<10}{'Status':<10}")
        print(f"  {'-' * 86}")
        for item in items:
            print(f"  {str(item['id']):<6}{str(item.get('activity', '') or '')[:18]:<20}"
                  f"{str(item.get('location', '') or '')[:12]:<14}"
                  f"{str(item.get('assessor', '') or '')[:12]:<14}"
                  f"{str(item.get('assessment_date', '') or ''):<12}"
                  f"{str(item.get('risk_rating', '') or ''):<10}"
                  f"{str(item.get('status', '') or ''):<10}")
        print(f"\n  Total: {len(items)} assessment(s)")
    except Exception as e:
        print(f"\n  Error: {e}")


def _new_risk_assessment(svc):
    print_header("New Risk Assessment")
    try:
        activity = input("  Activity: ").strip()
        assessment_date = input("  Date (YYYY-MM-DD): ").strip()
        if not activity or not assessment_date:
            print("\n  Activity and date are required.")
            return
        data = {}
        for field in ["location", "assessor", "hazards", "persons_at_risk",
                       "existing_controls", "risk_rating", "additional_controls",
                       "review_date", "status"]:
            val = input(f"  {field}: ").strip()
            if val:
                data[field] = val
        item = svc.create_risk_assessment(activity, assessment_date, **data)
        print(f"\n  Risk assessment created with ID: {item['id']}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _update_risk_assessment(svc):
    print_header("Update Risk Assessment")
    try:
        pk = int(input("  Enter risk assessment ID: ").strip())
        item = svc.get_risk_assessment(pk)
        if not item:
            print("\n  Risk assessment not found.")
            return
        data = {}
        for field in ["activity", "location", "assessor", "assessment_date",
                       "hazards", "persons_at_risk", "existing_controls",
                       "risk_rating", "additional_controls", "review_date", "status"]:
            current = item.get(field, "")
            val = input(f"  {field} [{current}]: ").strip()
            if val:
                data[field] = val
        if data:
            svc.update_risk_assessment(pk, **data)
            print("\n  Risk assessment updated.")
        else:
            print("\n  No changes made.")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


# ── Compliance Checks ─────────────────────────────────────────────────────────


def _list_compliance_checks(svc):
    print_header("List Compliance Checks")
    try:
        status_filter = input("  Filter by status (current/due/overdue/expired) [all]: ").strip() or None
        items = svc.list_compliance_checks(status=status_filter)
        if not items:
            print("\n  No compliance checks found.")
            return
        print(f"\n  {'ID':<6}{'Type':<20}{'Responsible':<16}{'Frequency':<12}{'Last Done':<12}{'Next Due':<12}{'Status':<10}")
        print(f"  {'-' * 88}")
        for item in items:
            print(f"  {str(item['id']):<6}{str(item.get('check_type', '') or '')[:18]:<20}"
                  f"{str(item.get('responsible_person', '') or '')[:14]:<16}"
                  f"{str(item.get('frequency', '') or ''):<12}"
                  f"{str(item.get('last_completed', '') or ''):<12}"
                  f"{str(item.get('next_due', '') or ''):<12}"
                  f"{str(item.get('status', '') or ''):<10}")
        print(f"\n  Total: {len(items)} check(s)")
    except Exception as e:
        print(f"\n  Error: {e}")


def _new_compliance_check(svc):
    print_header("New Compliance Check")
    try:
        check_type = input("  Check type: ").strip()
        if not check_type:
            print("\n  Check type is required.")
            return
        data = {}
        for field in ["description", "responsible_person", "frequency",
                       "last_completed", "next_due", "certificate_ref",
                       "provider", "status", "notes"]:
            val = input(f"  {field}: ").strip()
            if val:
                data[field] = val
        item = svc.create_compliance_check(check_type, **data)
        print(f"\n  Compliance check created with ID: {item['id']}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _update_compliance_check(svc):
    print_header("Update Compliance Check")
    try:
        pk = int(input("  Enter compliance check ID: ").strip())
        item = svc.get_compliance_check(pk)
        if not item:
            print("\n  Compliance check not found.")
            return
        data = {}
        for field in ["check_type", "description", "responsible_person", "frequency",
                       "last_completed", "next_due", "certificate_ref",
                       "provider", "status", "notes"]:
            current = item.get(field, "")
            val = input(f"  {field} [{current}]: ").strip()
            if val:
                data[field] = val
        if data:
            svc.update_compliance_check(pk, **data)
            print("\n  Compliance check updated.")
        else:
            print("\n  No changes made.")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _overdue_checks(svc):
    print_header("Overdue Compliance Checks")
    try:
        items = svc.get_overdue_checks()
        if not items:
            print("\n  No overdue compliance checks.")
            return
        print(f"\n  {'ID':<6}{'Type':<20}{'Responsible':<16}{'Next Due':<12}{'Status':<10}")
        print(f"  {'-' * 64}")
        for item in items:
            print(f"  {str(item['id']):<6}{str(item.get('check_type', '') or '')[:18]:<20}"
                  f"{str(item.get('responsible_person', '') or '')[:14]:<16}"
                  f"{str(item.get('next_due', '') or ''):<12}"
                  f"{str(item.get('status', '') or ''):<10}")
        print(f"\n  Total: {len(items)} overdue check(s)")
    except Exception as e:
        print(f"\n  Error: {e}")


# ── Statistics ────────────────────────────────────────────────────────────────


def _show_statistics(svc):
    print_header("Health & Safety Statistics")
    try:
        stats = svc.get_stats()
        print(f"\n  --- Incidents ---")
        print(f"  Total Incidents:       {stats.get('total_incidents', 0)}")
        print(f"  Open Incidents:        {stats.get('open_incidents', 0)}")
        print(f"  RIDDOR Reportable:     {stats.get('riddor_count', 0)}")
        by_type = stats.get("by_type", {})
        if by_type:
            print(f"\n  --- By Incident Type ---")
            for k, v in by_type.items():
                print(f"    {k}: {v}")
        print(f"\n  --- Inspections ---")
        print(f"  Total Inspections:     {stats.get('total_inspections', 0)}")
        print(f"  Failed Inspections:    {stats.get('failed_inspections', 0)}")
        print(f"\n  --- Risk Assessments ---")
        print(f"  Total Assessments:     {stats.get('total_risk_assessments', 0)}")
        print(f"  High/Very High Risk:   {stats.get('high_risk_count', 0)}")
        print(f"\n  --- Compliance ---")
        print(f"  Total Checks:          {stats.get('total_compliance', 0)}")
        print(f"  Overdue Checks:        {stats.get('overdue_compliance', 0)}")
    except Exception as e:
        print(f"\n  Error: {e}")
