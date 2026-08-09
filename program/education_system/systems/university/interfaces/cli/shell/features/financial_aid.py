"""Component extracted from the legacy menu router."""
from __future__ import annotations
from ..bootstrap.integrations import (
    FinancialAidManager,
    ValidationError,
    display_language_menu_option,
    get_text,
)

def _finaid_manage_scholarships(auth):
    """Manage scholarships sub-menu"""
    from education_system.systems.university.domain.finance.services.financial_aid.scholarship_manager import ScholarshipManager
    print("\n--- Manage Scholarships ---")
    print("1. Create scholarship")
    print("2. View available scholarships")
    print("3. Submit scholarship application")
    print("4. Return")
    sub = input("Choice: ").strip()
    try:
        sm = ScholarshipManager()
        if sub == '1':
            name = input("Scholarship name: ").strip()
            amount = float(input("Amount: ").strip())
            scholarship_type = input("Type (merit/need/athletic/departmental) [merit]: ").strip() or "merit"
            description = input("Description (optional): ").strip() or None
            min_gpa_str = input("Minimum GPA (optional): ").strip()
            min_gpa = float(min_gpa_str) if min_gpa_str else None
            deadline_str = input("Deadline (YYYY-MM-DD, optional): ").strip()
            deadline = None
            if deadline_str:
                from datetime import date as _date
                deadline = _date.fromisoformat(deadline_str)
            sid = sm.create_scholarship(
                name=name, amount=amount, scholarship_type=scholarship_type,
                description=description, min_gpa=min_gpa, deadline=deadline
            )
            if sid:
                print(f"✅ Scholarship created! ID: {sid}")
            else:
                print("❌ Failed to create scholarship.")
        elif sub == '2':
            scholarships = sm.get_available_scholarships()
            if scholarships:
                for s in scholarships:
                    print(f"  ID: {s['id']}, Name: {s.get('name', 'N/A')}, Amount: £{s.get('amount', 0):.2f}, Type: {s.get('scholarship_type', 'N/A')}")
            else:
                print("No scholarships available.")
        elif sub == '3':
            scholarship_id = int(input("Scholarship ID: ").strip())
            student_id = int(input("Student ID: ").strip())
            essay = input("Essay text (optional): ").strip() or None
            gpa_str = input("GPA (optional): ").strip()
            gpa = float(gpa_str) if gpa_str else None
            app_id = sm.submit_application(
                scholarship_id=scholarship_id, student_id=student_id,
                essay_text=essay, gpa=gpa
            )
            if app_id:
                print(f"✅ Application submitted! Application ID: {app_id}")
            else:
                print("❌ Failed to submit application.")
    except (ValueError, TypeError, ValidationError) as e:
        print(f"❌ Error: {e}")

def _finaid_disbursement_management(auth):
    """Disbursement management sub-menu"""
    print("\n--- Disbursement Management ---")
    print("1. Create disbursement")
    print("2. View pending disbursements")
    print("3. Process disbursement")
    print("4. Return")
    sub = input("Choice: ").strip()
    try:
        aid_mgr = FinancialAidManager()
        if sub == '1':
            student_id = int(input("Student ID: ").strip())
            amount = float(input("Amount: ").strip())
            from datetime import date as _date
            date_str = input("Disbursement date (YYYY-MM-DD): ").strip()
            disb_date = _date.fromisoformat(date_str)
            disb_type = input("Type (tuition/housing/books/stipend): ").strip()
            term = input("Academic term (e.g., Fall 2025): ").strip()
            did = aid_mgr.create_disbursement(
                student_id=student_id, amount=amount,
                disbursement_date=disb_date, disbursement_type=disb_type,
                academic_term=term
            )
            if did:
                print(f"✅ Disbursement created! ID: {did}")
            else:
                print("❌ Failed to create disbursement.")
        elif sub == '2':
            term = input("Academic term (or Enter for all): ").strip() or None
            pending = aid_mgr.get_pending_disbursements(academic_term=term)
            if pending:
                for d in pending:
                    print(f"  ID: {d['id']}, Student: {d.get('student_id')}, Amount: £{d.get('amount', 0):.2f}, Type: {d.get('disbursement_type', 'N/A')}")
            else:
                print("No pending disbursements.")
        elif sub == '3':
            disb_id = int(input("Disbursement ID: ").strip())
            processed_by = auth.current_user['user_id']
            txn_id = input("Transaction ID (optional): ").strip() or None
            if aid_mgr.process_disbursement(disb_id, processed_by=processed_by, transaction_id=txn_id):
                print("✅ Disbursement processed successfully!")
            else:
                print("❌ Failed to process disbursement.")
    except (ValueError, TypeError, ValidationError) as e:
        print(f"❌ Error: {e}")

def display_financial_aid_menu(auth):
    """Display the financial aid & scholarships CLI menu"""
    print("\n" + "="*50)
    print(f"    {get_text('finaid.title', default='FINANCIAL AID & SCHOLARSHIP MANAGEMENT')}")
    print("="*50)
    print(f"1. {get_text('finaid.menu.view_applications', default='View Financial Aid Applications')}")
    print(f"2. {get_text('finaid.menu.submit_fafsa', default='Submit FAFSA Data')}")
    print(f"3. {get_text('finaid.menu.create_package', default='Create Aid Package')}")
    print(f"4. {get_text('finaid.menu.manage_scholarships', default='Manage Scholarships')}")
    print(f"5. {get_text('finaid.menu.review_applications', default='Review Scholarship Applications')}")
    print(f"6. {get_text('finaid.menu.award_scholarship', default='Award Scholarship')}")
    print(f"7. {get_text('finaid.menu.disbursement', default='Disbursement Management')}")
    print(f"8. {get_text('finaid.menu.compliance', default='Compliance Reports')}")
    print(f"9. {get_text('finaid.menu.language', default='Language')}")
    print(f"10. {get_text('finaid.menu.return_main', default='Return to Main Menu')}")
    print("="*50)

    while True:
        try:
            choice = input(f"\n{get_text('finaid.prompt.choice', default='Enter your choice (1-10)')}: ").strip()

            if choice == '1':
                # View Financial Aid Applications
                try:
                    student_id = int(input(get_text('finaid.prompt.student_id', default="Enter student ID: ")).strip())
                    academic_year = input(get_text('finaid.prompt.academic_year', default="Enter academic year (e.g., 2024-2025): ")).strip()
                    aid_mgr = FinancialAidManager()
                    package = aid_mgr.get_aid_package(student_id, academic_year)
                    if package:
                        print(f"\n--- Aid Package for Student {student_id} ({academic_year}) ---")
                        for k, v in package.items():
                            print(f"  {k}: {v}")
                    else:
                        fafsa = aid_mgr.get_fafsa_data(student_id, academic_year)
                        if fafsa:
                            print(f"\n--- FAFSA Data for Student {student_id} ({academic_year}) ---")
                            for k, v in fafsa.items():
                                print(f"  {k}: {v}")
                        else:
                            print("No financial aid data found for this student and academic year.")
                except (ValueError, TypeError, ValidationError) as e:
                    print(get_text('finaid.error.applications', default='Error viewing applications: {error}').format(error=e))
            elif choice == '2':
                # Submit FAFSA Data
                try:
                    student_id = int(input(get_text('finaid.prompt.student_id', default="Enter student ID: ")).strip())
                    academic_year = input(get_text('finaid.prompt.academic_year', default="Enter academic year (e.g., 2024-2025): ")).strip()
                    efc = float(input(get_text('finaid.prompt.efc', default="Enter Expected Family Contribution (EFC): ")).strip())

                    aid_mgr = FinancialAidManager()
                    from datetime import date
                    aid_mgr.import_fafsa_data(
                        student_id=student_id,
                        academic_year=academic_year,
                        efc=efc,
                        submission_date=date.today()
                    )
                    print(get_text('finaid.success.fafsa', default='FAFSA data imported successfully!'))
                except (ValueError, TypeError, ValidationError) as e:
                    print(get_text('finaid.error.fafsa', default='Error importing FAFSA data: {error}').format(error=e))
            elif choice == '3':
                # Create Aid Package
                try:
                    student_id = int(input(get_text('finaid.prompt.student_id', default="Enter student ID: ")).strip())
                    academic_year = input(get_text('finaid.prompt.academic_year', default="Enter academic year (e.g., 2024-2025): ")).strip()
                    aid_mgr = FinancialAidManager()
                    pkg_id = aid_mgr.create_aid_package(
                        student_id=student_id, academic_year=academic_year,
                        created_by=auth.current_user['user_id']
                    )
                    if pkg_id:
                        print(f"✅ Aid package created! Package ID: {pkg_id}")
                        add_component = input("Add a component now? (y/n): ").strip().lower()
                        while add_component == 'y':
                            aid_type = input("Aid type (grant/loan/scholarship/work_study): ").strip()
                            name = input("Component name: ").strip()
                            amount = float(input("Amount: ").strip())
                            source = input("Source (federal/state/institutional) [institutional]: ").strip() or "institutional"
                            comp_id = aid_mgr.add_aid_component(
                                package_id=pkg_id, aid_type=aid_type,
                                name=name, amount=amount, source=source
                            )
                            if comp_id:
                                print(f"✅ Component added! Component ID: {comp_id}")
                            else:
                                print("❌ Failed to add component.")
                            add_component = input("Add another component? (y/n): ").strip().lower()
                    else:
                        print("❌ Failed to create aid package.")
                except (ValueError, TypeError, ValidationError) as e:
                    print(get_text('finaid.error.package', default='Error creating aid package: {error}').format(error=e))
            elif choice == '4':
                _finaid_manage_scholarships(auth)
            elif choice == '5':
                # Review Scholarship Applications
                try:
                    from education_system.systems.university.domain.finance.services.financial_aid.scholarship_manager import ScholarshipManager
                    app_id = int(input("Enter application ID: ").strip())
                    status = input("Decision (approved/denied/waitlisted): ").strip()
                    score_str = input("Review score (0-100, optional): ").strip()
                    score = float(score_str) if score_str else None
                    comments = input("Review comments (optional): ").strip() or None
                    sm = ScholarshipManager()
                    if sm.review_application(
                        app_id=app_id, reviewer_id=auth.current_user['user_id'],
                        status=status, review_score=score, review_comments=comments
                    ):
                        print("✅ Application reviewed successfully!")
                    else:
                        print("❌ Failed to review application.")
                except (ValueError, TypeError, ValidationError) as e:
                    print(get_text('finaid.error.review', default='Error reviewing application: {error}').format(error=e))
            elif choice == '6':
                # Award Scholarship
                try:
                    from education_system.systems.university.domain.finance.services.financial_aid.scholarship_manager import ScholarshipManager
                    scholarship_id = int(input("Enter scholarship ID: ").strip())
                    student_id = int(input("Enter student ID: ").strip())
                    academic_year = input("Academic year (e.g., 2024-2025): ").strip()
                    amount = float(input("Award amount: ").strip())
                    renewable_str = input("Is renewable? (y/n) [n]: ").strip().lower()
                    is_renewable = renewable_str == 'y'
                    sm = ScholarshipManager()
                    award_id = sm.award_scholarship(
                        scholarship_id=scholarship_id, student_id=student_id,
                        academic_year=academic_year, amount=amount,
                        is_renewable=is_renewable
                    )
                    if award_id:
                        print(f"✅ Scholarship awarded! Award ID: {award_id}")
                    else:
                        print("❌ Failed to award scholarship.")
                except (ValueError, TypeError, ValidationError) as e:
                    print(get_text('finaid.error.award', default='Error awarding scholarship: {error}').format(error=e))
            elif choice == '7':
                _finaid_disbursement_management(auth)
            elif choice == '8':
                # Compliance Reports
                try:
                    from education_system.systems.university.domain.finance.services.financial_aid.scholarship_manager import ScholarshipManager
                    student_id = int(input("Enter student ID: ").strip())
                    sm = ScholarshipManager()
                    awards = sm.get_student_awards(student_id)
                    if awards:
                        print(f"\n--- Scholarship Awards for Student {student_id} ---")
                        for a in awards:
                            print(f"  ID: {a.get('id', 'N/A')}, Name: {a.get('scholarship_name', a.get('name', 'N/A'))}, Amount: £{a.get('amount', 0):.2f}, Year: {a.get('academic_year', 'N/A')}")
                    else:
                        print("No scholarship awards found.")
                    aid_mgr = FinancialAidManager()
                    pending = aid_mgr.get_pending_disbursements()
                    if pending:
                        print("\n--- Pending Disbursements ---")
                        for d in pending:
                            print(f"  ID: {d['id']}, Student: {d.get('student_id')}, Amount: £{d.get('amount', 0):.2f}, Type: {d.get('disbursement_type', 'N/A')}")
                    else:
                        print("No pending disbursements.")
                except (ValueError, TypeError, ValidationError) as e:
                    print(get_text('finaid.error.compliance', default='Error generating compliance report: {error}').format(error=e))
            elif choice == '9':
                display_language_menu_option()
            elif choice == '10':
                print(get_text('finaid.returning', default='Returning to main menu...'))
                break
            else:
                print(get_text('finaid.invalid_choice', default='Invalid choice. Please enter a number between 1 and 10.'))

        except KeyboardInterrupt:
            print(get_text('finaid.exiting', default='\n\nExiting financial aid menu...'))
            break
        except (ValueError, TypeError, ValidationError) as e:
            print(get_text('finaid.error', default='Error: {error}').format(error=e))
