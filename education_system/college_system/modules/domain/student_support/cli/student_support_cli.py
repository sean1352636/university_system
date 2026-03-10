"""Student Support CLI module."""

from education_system.college_system.modules.shared.cli.cli_main import (
    print_header, print_menu, get_choice,
)
from education_system.college_system.modules.domain.student_support.services.student_support_service import StudentSupportService
from education_system.college_system.infrastructure.auth.core import UserAuth


def student_support_menu(auth: UserAuth):
    """Student support management menu."""
    svc = StudentSupportService(auth._db_path)

    while True:
        print_header("Student Support")
        options = [
            ("1", "List Interventions"),
            ("2", "New Intervention"),
            ("3", "Update Intervention"),
            ("4", "Record Session Attended"),
            ("5", "Impact Report"),
            ("6", "List Risks"),
            ("7", "New Risk"),
            ("8", "Resolve Risk"),
            ("9", "Escalate Risk"),
            ("A", "Student Risk Profile"),
            ("B", "List Documents"),
            ("C", "Upload Document"),
            ("D", "Verify Document"),
            ("E", "Expiring Documents"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice().upper()
        if choice == "1":
            _list_interventions(svc)
        elif choice == "2":
            _new_intervention(svc, auth)
        elif choice == "3":
            _update_intervention(svc)
        elif choice == "4":
            _record_session(svc)
        elif choice == "5":
            _impact_report(svc)
        elif choice == "6":
            _list_risks(svc)
        elif choice == "7":
            _new_risk(svc, auth)
        elif choice == "8":
            _resolve_risk(svc)
        elif choice == "9":
            _escalate_risk(svc)
        elif choice == "A":
            _student_profile(svc)
        elif choice == "B":
            _list_documents(svc)
        elif choice == "C":
            _upload_document(svc, auth)
        elif choice == "D":
            _verify_document(svc, auth)
        elif choice == "E":
            _expiring_docs(svc)
        elif choice == "0":
            break
        else:
            print("\n  Invalid option.")


def _list_interventions(svc):
    print_header("Interventions")
    try:
        items = svc.list_interventions()
        if not items:
            print("\n  No interventions found.")
            return
        print(f"\n  {'ID':<5} {'Student':<8} {'Type':<12} {'Status':<10} {'Sessions'}")
        print(f"  {'-'*45}")
        for i in items:
            print(f"  {i['id']:<5} {i['student_id']:<8} {i['intervention_type']:<12} "
                  f"{i['status']:<10} {i['sessions_attended']}/{i['sessions_planned']}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _new_intervention(svc, auth):
    print_header("New Intervention")
    try:
        student_id = int(input("  Student PK: ").strip())
        staff_id = int(input("  Staff ID: ").strip())
        itype = input("  Type (academic/attendance/behaviour/wellbeing/mentoring) [academic]: ").strip() or "academic"
        targets = input("  Targets: ").strip() or None
        sessions = int(input("  Sessions Planned [0]: ").strip() or "0")

        item = svc.create_intervention(student_id, staff_id, itype, targets, sessions)
        print(f"\n  Intervention created (ID: {item['id']}).")
    except Exception as e:
        print(f"\n  Error: {e}")


def _update_intervention(svc):
    print_header("Update Intervention")
    try:
        iid = int(input("  Intervention ID: ").strip())
        print("  (Leave blank to keep current)")
        status = input("  Status (planned/active/completed/cancelled): ").strip() or None
        outcome = input("  Outcome: ").strip() or None
        impact = input("  Impact (none/some/significant): ").strip() or None

        updates = {}
        if status:
            updates["status"] = status
        if outcome:
            updates["outcome"] = outcome
        if impact:
            updates["impact_rating"] = impact

        item = svc.update_intervention(iid, **updates)
        print(f"\n  Intervention {item['id']} updated.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _record_session(svc):
    try:
        iid = int(input("  Intervention ID: ").strip())
        item = svc.record_session_attended(iid)
        print(f"\n  Sessions attended: {item['sessions_attended']}/{item['sessions_planned']}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _impact_report(svc):
    print_header("Intervention Impact Report")
    try:
        report = svc.get_intervention_impact_report()
        if not report:
            print("\n  No data.")
            return
        print(f"\n  {'Type':<15} {'Total':<8} {'Significant':<12} {'Some':<8} {'None':<8} {'Completed'}")
        print(f"  {'-'*60}")
        for r in report:
            print(f"  {r['intervention_type']:<15} {r['total']:<8} {r['significant']:<12} "
                  f"{r['some_impact']:<8} {r['no_impact']:<8} {r['completed']}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _list_risks(svc):
    print_header("Risk Register")
    try:
        risks = svc.list_risks()
        if not risks:
            print("\n  No risks found.")
            return
        print(f"\n  {'ID':<5} {'Student':<8} {'Type':<15} {'Level':<10} {'Status'}")
        print(f"  {'-'*48}")
        for r in risks:
            print(f"  {r['id']:<5} {r['student_id']:<8} {r['risk_type']:<15} "
                  f"{r['risk_level']:<10} {r['status']}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _new_risk(svc, auth):
    print_header("New Risk")
    try:
        student_id = int(input("  Student PK: ").strip())
        risk_type = input("  Type (academic/attendance/behaviour/wellbeing/safeguarding/financial/neet): ").strip()
        risk_level = input("  Level (low/medium/high/critical): ").strip()
        mitigations = input("  Mitigations: ").strip() or None
        identified_by = auth.current_user.get("user_id", 0)

        risk = svc.create_risk(student_id, risk_type, risk_level, identified_by, mitigations)
        print(f"\n  Risk created (ID: {risk['id']}).")
    except Exception as e:
        print(f"\n  Error: {e}")


def _resolve_risk(svc):
    try:
        risk_id = int(input("  Risk ID: ").strip())
        svc.resolve_risk(risk_id)
        print("\n  Risk resolved.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _escalate_risk(svc):
    try:
        risk_id = int(input("  Risk ID: ").strip())
        svc.escalate_risk(risk_id)
        print("\n  Risk escalated.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _student_profile(svc):
    print_header("Student Risk Profile")
    try:
        student_id = int(input("  Student PK: ").strip())
        profile = svc.get_student_risk_profile(student_id)
        print(f"\n  Total Risks: {profile['total_risks']}")
        print(f"  Open Risks: {profile['open_risks']}")
        print(f"  Interventions: {len(profile['interventions'])}")
        print(f"  Documents: {len(profile['documents'])}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _list_documents(svc):
    print_header("Student Documents")
    try:
        docs = svc.list_documents()
        if not docs:
            print("\n  No documents found.")
            return
        print(f"\n  {'ID':<5} {'Student':<8} {'Type':<15} {'Title':<25} {'Verified'}")
        print(f"  {'-'*58}")
        for d in docs:
            verified = "Yes" if d["verified"] else "No"
            print(f"  {d['id']:<5} {d['student_id']:<8} {d['document_type']:<15} "
                  f"{d['title']:<25} {verified}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _upload_document(svc, auth):
    print_header("Upload Document")
    try:
        student_id = int(input("  Student PK: ").strip())
        doc_type = input("  Type (consent_form/id_document/ehcp/medical/reference/other): ").strip()
        title = input("  Title: ").strip()
        file_path = input("  File Path (optional): ").strip() or None
        expiry = input("  Expiry Date (YYYY-MM-DD, optional): ").strip() or None

        doc = svc.upload_document(student_id, doc_type, title,
                                  auth.current_user.get("user_id", 0),
                                  file_path, expiry)
        print(f"\n  Document uploaded (ID: {doc['id']}).")
    except Exception as e:
        print(f"\n  Error: {e}")


def _verify_document(svc, auth):
    try:
        doc_id = int(input("  Document ID: ").strip())
        svc.verify_document(doc_id, auth.current_user.get("user_id", 0))
        print("\n  Document verified.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _expiring_docs(svc):
    print_header("Expiring Documents")
    try:
        docs = svc.get_expiring_documents()
        if not docs:
            print("\n  No expiring documents.")
            return
        for d in docs:
            name = f"{d.get('first_name', '')} {d.get('last_name', '')}"
            print(f"  [{d['id']}] {name} - {d['title']} (expires: {d['expiry_date']})")
    except Exception as e:
        print(f"\n  Error: {e}")
