"""Funding & ILR CLI module."""

from education_system.college_system.modules.shared.cli.cli_main import (
    print_header, print_menu, get_choice,
)
from education_system.college_system.modules.domain.funding.services.funding_service import FundingService
from education_system.college_system.infrastructure.auth.core import UserAuth


def funding_menu(auth: UserAuth):
    """Funding & ILR management menu."""
    svc = FundingService(auth._db_path)

    while True:
        print_header("Funding & ILR")
        options = [
            ("1", "Funding Records"),
            ("2", "New Funding Record"),
            ("3", "Complete Record"),
            ("4", "Withdraw Record"),
            ("5", "Hours Summary"),
            ("6", "ILR Export"),
            ("7", "Evidence"),
            ("8", "Add Evidence"),
            ("9", "Funding Rules"),
            ("A", "New Rule"),
            ("B", "Resit Tracking"),
            ("C", "New Resit"),
            ("D", "Resit Summary"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice().upper()
        if choice == "1":
            _list_records(svc)
        elif choice == "2":
            _new_record(svc)
        elif choice == "3":
            _complete_record(svc)
        elif choice == "4":
            _withdraw_record(svc)
        elif choice == "5":
            _hours_summary(svc)
        elif choice == "6":
            _ilr_export(svc)
        elif choice == "7":
            _list_evidence(svc)
        elif choice == "8":
            _add_evidence(svc)
        elif choice == "9":
            _list_rules(svc)
        elif choice == "A":
            _new_rule(svc)
        elif choice == "B":
            _list_resits(svc)
        elif choice == "C":
            _new_resit(svc)
        elif choice == "D":
            _resit_summary(svc)
        elif choice == "0":
            break
        else:
            print("\n  Invalid option.")


def _list_records(svc):
    print_header("Funding Records")
    try:
        records = svc.list_funding_records()
        if not records:
            print("\n  No funding records found.")
            return
        print(f"\n  {'ID':<5} {'Student':<8} {'Aim':<20} {'Model':<8} {'Hours':<12} {'Status'}")
        print(f"  {'-'*58}")
        for r in records:
            hours = f"{r['actual_hours']}/{r['planned_hours']}"
            print(f"  {r['id']:<5} {r['student_id']:<8} {(r.get('learning_aim') or '-'):<20} "
                  f"{r['funding_model']:<8} {hours:<12} {r['completion_status']}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _new_record(svc):
    print_header("New Funding Record")
    try:
        student_id = int(input("  Student PK: ").strip())
        learning_aim = input("  Learning Aim: ").strip() or None
        aim_type = input("  Aim Type: ").strip() or None
        funding_model = input("  Funding Model [16-19]: ").strip() or "16-19"
        planned_hours = int(input("  Planned Hours [0]: ").strip() or "0")
        start_date = input("  Start Date (YYYY-MM-DD): ").strip() or None
        end_date = input("  Planned End Date (YYYY-MM-DD): ").strip() or None

        record = svc.create_funding_record(student_id, learning_aim, aim_type,
                                            funding_model, planned_hours,
                                            start_date, end_date)
        print(f"\n  Funding record created (ID: {record['id']}).")
    except Exception as e:
        print(f"\n  Error: {e}")


def _complete_record(svc):
    try:
        record_id = int(input("  Record ID: ").strip())
        outcome = input("  Outcome (achieved/not_achieved/partial) [achieved]: ").strip() or "achieved"
        svc.complete_funding_record(record_id, outcome)
        print("\n  Record completed.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _withdraw_record(svc):
    try:
        record_id = int(input("  Record ID: ").strip())
        svc.withdraw_funding_record(record_id)
        print("\n  Record withdrawn.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _hours_summary(svc):
    try:
        student_id = int(input("  Student PK: ").strip())
        summary = svc.get_hours_summary(student_id)
        print(f"\n  Planned Hours: {summary['total_planned']}")
        print(f"  Actual Hours: {summary['total_actual']}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _ilr_export(svc):
    print_header("ILR Export Data")
    try:
        data = svc.export_ilr_data()
        if not data:
            print("\n  No data to export.")
            return
        print(f"\n  {len(data)} records found.")
        for r in data[:20]:
            print(f"  {r.get('sid', '-')} {r.get('first_name', '')} {r.get('last_name', '')} - "
                  f"{r.get('learning_aim', '-')} ({r['completion_status']})")
        if len(data) > 20:
            print(f"\n  ... and {len(data) - 20} more records.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _list_evidence(svc):
    print_header("Funding Evidence")
    try:
        evidence = svc.list_evidence()
        if not evidence:
            print("\n  No evidence found.")
            return
        for e in evidence:
            verified = "Verified" if e["verified"] else "Unverified"
            print(f"  [{e['id']}] Record {e['funding_record_id']} - {e['evidence_type']} ({verified})")
    except Exception as e:
        print(f"\n  Error: {e}")


def _add_evidence(svc):
    try:
        record_id = int(input("  Funding Record ID: ").strip())
        etype = input("  Type (enrollment_form/learning_agreement/attendance_evidence/completion_evidence/other): ").strip()
        file_path = input("  File Path (optional): ").strip() or None
        ev = svc.add_evidence(record_id, etype, file_path)
        print(f"\n  Evidence added (ID: {ev['id']}).")
    except Exception as e:
        print(f"\n  Error: {e}")


def _list_rules(svc):
    print_header("Funding Rules")
    try:
        rules = svc.list_rules()
        if not rules:
            print("\n  No rules found.")
            return
        for r in rules:
            print(f"  [{r['id']}] {r['rule_code']} - {r.get('description', '-')} ({r['rule_type']})")
    except Exception as e:
        print(f"\n  Error: {e}")


def _new_rule(svc):
    try:
        code = input("  Rule Code: ").strip()
        desc = input("  Description: ").strip() or None
        rtype = input("  Type (eligibility/hours/completion/withdrawal) [eligibility]: ").strip() or "eligibility"
        rule = svc.create_rule(code, desc, rtype)
        print(f"\n  Rule created (ID: {rule['id']}).")
    except Exception as e:
        print(f"\n  Error: {e}")


def _list_resits(svc):
    print_header("Resit Tracking")
    try:
        resits = svc.list_resits()
        if not resits:
            print("\n  No resits found.")
            return
        print(f"\n  {'ID':<5} {'Student':<8} {'Subject':<10} {'Entry':<8} {'Status':<10} {'Result'}")
        print(f"  {'-'*50}")
        for r in resits:
            print(f"  {r['id']:<5} {r['student_id']:<8} {r['subject']:<10} "
                  f"{(r.get('gcse_grade_on_entry') or '-'):<8} {r['status']:<10} "
                  f"{(r.get('latest_result') or '-')}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _new_resit(svc):
    try:
        student_id = int(input("  Student PK: ").strip())
        subject = input("  Subject (english/maths): ").strip().lower()
        entry_grade = input("  GCSE Grade on Entry: ").strip() or None
        target = input("  Target Grade: ").strip() or None

        resit = svc.create_resit(student_id, subject, entry_grade, target_grade=target)
        print(f"\n  Resit created (ID: {resit['id']}).")
    except Exception as e:
        print(f"\n  Error: {e}")


def _resit_summary(svc):
    print_header("Resit Summary")
    try:
        summary = svc.get_resit_summary()
        for s in summary.get("subjects", []):
            print(f"\n  {s['subject'].upper()}: {s['total']} total, "
                  f"{s['achieved']} achieved, {s['active']} active")
    except Exception as e:
        print(f"\n  Error: {e}")
