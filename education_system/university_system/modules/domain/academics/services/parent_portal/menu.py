import datetime


def display_parent_portal_menu(auth):
    """Display the enhanced parent portal menu"""
    from education_system.university_system.modules.domain.academics.services.parent_portal.portal import ParentPortal
    if not auth or not auth.current_user:
        print("You must be logged in to access the parent portal.")
        return

    if auth.current_user.get('role') not in ('parent', 'admin'):
        print("This function is only available for parent accounts and administrators.")
        return

    portal = ParentPortal(auth)
    is_admin = auth.current_user.get('role') == 'admin'

    while True:
        print("\n" + "=" * 60)
        print("ENHANCED PARENT PORTAL")
        print("=" * 60)

        if is_admin:
            print("ADMINISTRATOR MODE")
            print("\nParent Management:")
            print("1. Create Parent Account")
            print("2. Link Student to Parent")
            print("3. View Parent Dashboard")
            print("4. Return to Main Menu")

            choice = input("\nEnter your choice (1-4): ")

            if choice == '1':
                portal.create_parent_account()
            elif choice == '2':
                portal.link_student_to_parent()
            elif choice == '3':
                portal.view_parent_dashboard()
            elif choice == '4':
                return
            else:
                print("Invalid choice. Please try again.")
        else:
            # Enhanced parent menu
            print("\n\U0001f3e0 MAIN DASHBOARD")
            print("1. Dashboard Overview")
            print("2. Quick Actions")

            print("\n\U0001f465 MY CHILDREN")
            print("3. View Children")
            print("4. Academic Records")
            print("5. Attendance & Behavior")
            print("6. Health & Safety")

            print("\n\U0001f4ac COMMUNICATION")
            print("7. Messages & Announcements")
            print("8. Schedule Meetings")
            print("9. Report Issues")

            print("\n\U0001f4b0 FINANCIAL")
            print("10. Fees & Payments")
            print("11. Meal Accounts")
            print("12. Fundraising")

            print("\n\U0001f4da ACADEMIC SUPPORT")
            print("13. Homework & Assignments")
            print("14. Academic Goals")
            print("15. Grade Analytics")

            print("\n\u2699\ufe0f SETTINGS & TOOLS")
            print("16. Notification Preferences")
            print("17. Document Management")
            print("18. Calendar Integration")
            print("19. Account Settings")

            print("\n0. Logout")

            choice = input("\nEnter your choice (0-19): ")

            # Log the menu access
            portal.log_activity("menu_access", f"Selected option: {choice}")

            if choice == '0':
                return
            elif choice == '1':
                portal.view_parent_dashboard()
            elif choice == '2':
                portal.quick_actions_menu()
            elif choice == '3':
                children = portal.view_children()
                if children:
                    print("\nYour children:")
                    for i, child in enumerate(children):
                        print(f"{i+1}. {child[1]} {child[3]} (ID: {child[0]}, Course: {child[4]})")
                else:
                    print("You have no children registered in the system.")
            elif choice == '4':
                print("\nAcademic Records:")
                print("1. View Grades")
                print("2. View Teacher Reports")
                print("3. View Timetable")

                sub_choice = input("Select option: ")
                if sub_choice == '1':
                    portal.view_child_grades()
                elif sub_choice == '2':
                    portal.view_teacher_reports()
                elif sub_choice == '3':
                    portal.view_child_timetable()

            elif choice == '5':
                print("\nAttendance & Behavior:")
                print("1. View Attendance")
                print("2. View Behavior Reports")
                print("3. Report Absence")

                sub_choice = input("Select option: ")
                if sub_choice == '1':
                    portal.view_child_attendance()
                elif sub_choice == '2':
                    portal.view_behavior_reports()
                elif sub_choice == '3':
                    portal.report_absence()

            elif choice == '6':
                print("\nHealth & Safety:")
                print("1. Medical Information")
                print("2. Transportation")
                print("3. Pickup Authorization")
                print("4. Photo Permissions")

                sub_choice = input("Select option: ")
                if sub_choice == '1':
                    portal.view_medical_information()
                elif sub_choice == '2':
                    portal.view_transportation_info()
                elif sub_choice == '3':
                    portal.manage_pickup_authorization()
                elif sub_choice == '4':
                    portal.manage_photo_permissions()

            elif choice == '7':
                print("\nCommunication:")
                print("1. View Messages")
                print("2. Send Message to Teacher")
                print("3. Send Group Message")
                print("4. School Announcements")

                sub_choice = input("Select option: ")
                if sub_choice == '1':
                    portal.view_messages()
                elif sub_choice == '2':
                    portal.send_message_to_teacher()
                elif sub_choice == '3':
                    portal.send_group_message()
                elif sub_choice == '4':
                    portal.view_school_announcements()

            elif choice == '8':
                portal.schedule_parent_teacher_meeting()

            elif choice == '9':
                # Report Issues
                portal.report_issue()

            elif choice == '10':
                portal.view_student_fees()

            elif choice == '11':
                portal.manage_meal_account()

            elif choice == '12':
                portal.view_fundraising_campaigns()

            elif choice == '13':
                print("\nHomework & Assignments:")
                print("1. View Homework")
                print("2. View Assignments")
                print("3. View Library Account")
                print("4. Extracurricular Activities")

                sub_choice = input("Select option: ")
                if sub_choice == '1':
                    portal.view_homework_tracking()
                elif sub_choice == '2':
                    portal.view_child_assignments()
                elif sub_choice == '3':
                    portal.view_library_account()
                elif sub_choice == '4':
                    portal.view_extracurricular_activities()

            elif choice == '14':
                portal.manage_academic_goals()

            elif choice == '15':
                portal.view_grade_analytics()

            elif choice == '16':
                print("\nNotification Preferences:")
                print("1. Basic Preferences")
                print("2. Advanced Preferences")

                sub_choice = input("Select option: ")
                if sub_choice == '1':
                    portal.update_notification_preferences()
                elif sub_choice == '2':
                    portal.advanced_notification_preferences()

            elif choice == '17':
                portal.manage_documents()

            elif choice == '18':
                print("\nCalendar & Events:")
                print("1. View School Calendar")
                print("2. Family Calendar Integration")

                sub_choice = input("Select option: ")
                if sub_choice == '1':
                    portal.view_school_calendar()
                elif sub_choice == '2':
                    portal.family_calendar_integration()

            elif choice == '19':
                print("\nAccount Settings:")
                print("1. Update Contact Information")
                print("2. Emergency Contact Update")
                print("3. Generate QR Code")
                print("4. View Activity Log")

                sub_choice = input("Select option: ")
                if sub_choice == '1':
                    portal.update_contact_info()
                elif sub_choice == '2':
                    portal.emergency_contact_update()
                elif sub_choice == '3':
                    portal.generate_qr_code()
                elif sub_choice == '4':
                    portal.view_activity_log()

            else:
                print("Invalid choice. Please try again.")

            # Pause before showing menu again
            input("\nPress Enter to continue...")
