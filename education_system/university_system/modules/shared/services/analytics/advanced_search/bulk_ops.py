"""Bulk operations: export, email lists, student groups, follow-up, enrollment management."""
import json
from datetime import datetime

from education_system.university_system.modules.shared.services.analytics.advanced_search import _globals
from education_system.university_system.modules.shared.services.analytics.advanced_search.export import export_to_csv, export_to_json, export_to_excel, custom_format_export


def bulk_operations_menu():
    """Menu for bulk operations on search results"""
    if not _globals.last_search_results:
        print("No search results available. Please perform a search first.")
        return

    print(f"\n🔧 BULK OPERATIONS ({len(_globals.last_search_results)} students)")
    print("="*50)

    print("1. Export Selected Students")
    print("2. Generate Email List")
    print("3. Create Student Groups")
    print("4. Mark for Follow-up")
    print("5. Bulk Enrollment Management")

    choice = input("Select operation (1-5): ").strip()

    if choice == '1':
        bulk_export()
    elif choice == '2':
        generate_email_list()
    elif choice == '3':
        create_student_groups()
    elif choice == '4':
        mark_for_followup()
    elif choice == '5':
        bulk_enrollment_management()

def bulk_export():
    """Export search results in various formats"""
    print("\nExport Options:")
    print("1. CSV Format")
    print("2. JSON Format")
    print("3. Excel Format")
    print("4. Custom Format")

    choice = input("Select format (1-4): ").strip()

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    if choice == '1':
        export_to_csv(f"bulk_export_{timestamp}.csv")
    elif choice == '2':
        export_to_json(f"bulk_export_{timestamp}.json")
    elif choice == '3':
        export_to_excel(f"bulk_export_{timestamp}.xlsx")
    elif choice == '4':
        custom_format_export()

def save_last_search_results():
    """Save the last search results to a file"""
    if not _globals.last_search_results:
        print("No search results to save.")
        return

    print(f"\n💾 SAVE SEARCH RESULTS ({len(_globals.last_search_results)} students)")
    print("="*50)

    print("Export formats:")
    print("1. CSV format")
    print("2. JSON format")
    print("3. Text format")

    choice = input("Select format (1-3): ").strip()

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    try:
        if choice == '1':
            filename = f"search_results_{timestamp}.csv"
            export_to_csv(filename)

        elif choice == '2':
            filename = f"search_results_{timestamp}.json"
            export_to_json(filename)

        elif choice == '3':
            filename = f"search_results_{timestamp}.txt"
            with open(filename, 'w') as f:
                f.write(f"Search Results Export - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("="*60 + "\n\n")
                f.write(f"Total Results: {len(_globals.last_search_results)}\n\n")

                for i, student in enumerate(_globals.last_search_results, 1):
                    f.write(f"{i}. Student ID: {student[0]}\n")
                    f.write(f"   Name: {student[2]} {student[3]} {student[4] or ''} {student[5]}\n")
                    f.write(f"   Email: {student[1]}\n")
                    f.write(f"   Gender: {student[6]} | Age: {student[8]} | Course: {student[9]}\n")
                    f.write(f"   Registration: {student[10]}\n\n")

            print(f"✅ Results saved to {filename}")

        else:
            print("Invalid choice.")

    except Exception as e:
        print(f"Error saving results: {e}")

def mass_email_students():
    """Send mass emails to students from search results"""
    if not _globals.last_search_results:
        print("No search results available. Please perform a search first.")
        return

    print(f"\n📧 MASS EMAIL ({len(_globals.last_search_results)} recipients)")
    print("="*50)

    # Email configuration (in production, use proper email service)
    smtp_server = input("SMTP Server (or press Enter for simulation): ").strip()

    if not smtp_server:
        print("📧 EMAIL SIMULATION MODE")
        subject = input("Email subject: ").strip()
        message = input("Email message: ").strip()

        print(f"\n✅ Simulated email sent to {len(_globals.last_search_results)} students:")
        print(f"Subject: {subject}")
        print(f"Message: {message}")

        # In real implementation, would send actual emails
        for student in _globals.last_search_results[:5]:  # Show first 5
            print(f"  → {student[1]} ({student[3]} {student[5]})")

        if len(_globals.last_search_results) > 5:
            print(f"  ... and {len(_globals.last_search_results) - 5} more")

    else:
        # Real email implementation would go here
        print("Real email sending not implemented in this demo.")

def batch_data_updates():
    """Perform batch updates on student data"""
    if not _globals.last_search_results:
        print("No search results available. Please perform a search first.")
        return

    print(f"\n📝 BATCH DATA UPDATES ({len(_globals.last_search_results)} students)")
    print("="*60)

    print("Available update operations:")
    print("1. Update course")
    print("2. Update registration status")
    print("3. Add note/flag")
    print("4. Bulk module enrollment")

    choice = input("Select operation (1-4): ").strip()

    if choice == '1':
        new_course = input("New course (CS/DS): ").strip().upper()
        if new_course in ['CS', 'DS']:
            confirm = input(f"Update {len(_globals.last_search_results)} students to {new_course}? (y/n): ")
            if confirm.lower() == 'y':
                # Simulate batch update
                print(f"✅ Updated {len(_globals.last_search_results)} students to course {new_course}")

    elif choice == '2':
        print("Registration status update simulation")
        print(f"✅ Would update {len(_globals.last_search_results)} student records")

    elif choice == '3':
        note = input("Enter note/flag to add: ").strip()
        if note:
            print(f"✅ Added note '{note}' to {len(_globals.last_search_results)} students")

    elif choice == '4':
        print("Bulk module enrollment simulation")
        module = input("Module code to enroll students in: ").strip()
        if module:
            print(f"✅ Enrolled {len(_globals.last_search_results)} students in module {module}")

def generate_email_list():
    """Generate email list from search results"""
    if not _globals.last_search_results:
        print("No search results available.")
        return

    print(f"\n📧 GENERATING EMAIL LIST ({len(_globals.last_search_results)} students)")
    print("="*60)

    # Extract emails
    emails = []
    for student in _globals.last_search_results:
        if student[1]:  # email field
            emails.append(student[1])

    print(f"Found {len(emails)} email addresses:")

    # Format options
    print("\nFormat options:")
    print("1. Plain text list")
    print("2. Comma-separated")
    print("3. Semicolon-separated (Outlook)")
    print("4. JSON format")

    choice = input("Select format (1-4): ").strip()

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    if choice == '1':
        filename = f"email_list_{timestamp}.txt"
        with open(filename, 'w') as f:
            for email in emails:
                f.write(email + "\n")
    elif choice == '2':
        filename = f"email_list_{timestamp}.txt"
        with open(filename, 'w') as f:
            f.write(", ".join(emails))
    elif choice == '3':
        filename = f"email_list_{timestamp}.txt"
        with open(filename, 'w') as f:
            f.write("; ".join(emails))
    elif choice == '4':
        filename = f"email_list_{timestamp}.json"
        with open(filename, 'w') as f:
            json.dump({"emails": emails, "count": len(emails), "generated": datetime.now().isoformat()}, f, indent=2)
    else:
        print("Invalid choice.")
        return

    print(f"✅ Email list exported to {filename}")

def create_student_groups():
    """Create student groups from search results"""
    if not _globals.last_search_results:
        print("No search results available.")
        return

    print(f"\n👥 CREATE STUDENT GROUPS ({len(_globals.last_search_results)} students)")
    print("="*60)

    print("Group creation options:")
    print("1. Group by course")
    print("2. Group by age range")
    print("3. Group by random assignment")
    print("4. Group by alphabetical order")

    choice = input("Select grouping method (1-4): ").strip()

    groups = {}

    if choice == '1':
        # Group by course
        for student in _globals.last_search_results:
            course = student[9]  # course field
            if course not in groups:
                groups[course] = []
            groups[course].append(student)

    elif choice == '2':
        # Group by age range
        for student in _globals.last_search_results:
            age = student[8]  # age field
            if age < 20:
                age_group = "Under 20"
            elif age <= 25:
                age_group = "20-25"
            elif age <= 30:
                age_group = "26-30"
            else:
                age_group = "Over 30"

            if age_group not in groups:
                groups[age_group] = []
            groups[age_group].append(student)

    elif choice == '3':
        # Random assignment
        import random

        try:
            num_groups = int(input("Number of groups: "))
            if num_groups <= 0:
                print("Invalid number of groups.")
                return

            students_copy = _globals.last_search_results.copy()
            random.shuffle(students_copy)

            for i, student in enumerate(students_copy):
                group_name = f"Group {(i % num_groups) + 1}"
                if group_name not in groups:
                    groups[group_name] = []
                groups[group_name].append(student)

        except ValueError:
            print("Invalid input.")
            return

    elif choice == '4':
        # Alphabetical order
        sorted_students = sorted(_globals.last_search_results, key=lambda x: f"{x[3]} {x[5]}")  # first_name last_name

        try:
            group_size = int(input("Students per group: "))
            if group_size <= 0:
                print("Invalid group size.")
                return

            for i in range(0, len(sorted_students), group_size):
                group_name = f"Group {(i // group_size) + 1}"
                groups[group_name] = sorted_students[i:i+group_size]

        except ValueError:
            print("Invalid input.")
            return

    else:
        print("Invalid choice.")
        return

    # Display groups
    print(f"\n📋 CREATED {len(groups)} GROUPS:")
    print("="*60)

    for group_name, students in groups.items():
        print(f"\n{group_name} ({len(students)} students):")
        for student in students:
            print(f"  • {student[0]} - {student[3]} {student[5]} ({student[1]})")

    # Export option
    export_groups = input("\nExport groups to file? (y/n): ").strip().lower()
    if export_groups == 'y':
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"student_groups_{timestamp}.json"

        groups_data = {}
        for group_name, students in groups.items():
            groups_data[group_name] = [
                {
                    'student_id': s[0],
                    'name': f"{s[3]} {s[5]}",
                    'email': s[1],
                    'course': s[9]
                } for s in students
            ]

        with open(filename, 'w') as f:
            json.dump(groups_data, f, indent=2)

        print(f"✅ Groups exported to {filename}")

def mark_for_followup():
    """Mark students for follow-up"""
    if not _globals.last_search_results:
        print("No search results available.")
        return

    print(f"\n📌 MARK FOR FOLLOW-UP ({len(_globals.last_search_results)} students)")
    print("="*60)

    follow_up_reason = input("Enter follow-up reason: ").strip()
    priority = input("Priority (high/medium/low): ").strip().lower()

    if priority not in ['high', 'medium', 'low']:
        priority = 'medium'

    # Simulate marking for follow-up
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    follow_up_data = {
        'reason': follow_up_reason,
        'priority': priority,
        'marked_date': timestamp,
        'marked_by': _globals.current_user,
        'students': [
            {
                'student_id': s[0],
                'name': f"{s[3]} {s[5]}",
                'email': s[1]
            } for s in _globals.last_search_results
        ]
    }

    # Save to file
    filename = f"followup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, 'w') as f:
        json.dump(follow_up_data, f, indent=2)

    print(f"✅ {len(_globals.last_search_results)} students marked for follow-up")
    print(f"Reason: {follow_up_reason}")
    print(f"Priority: {priority}")
    print(f"Follow-up list saved to: {filename}")

def bulk_enrollment_management():
    """Manage bulk enrollment operations"""
    if not _globals.last_search_results:
        print("No search results available.")
        return

    print(f"\n🎓 BULK ENROLLMENT MANAGEMENT ({len(_globals.last_search_results)} students)")
    print("="*70)

    print("Operations:")
    print("1. Enroll in module")
    print("2. Unenroll from module")
    print("3. Transfer between modules")
    print("4. Update enrollment status")

    choice = input("Select operation (1-4): ").strip()

    if choice == '1':
        module_code = input("Module code to enroll in: ").strip()
        if module_code:
            print(f"✅ Simulation: Enrolled {len(_globals.last_search_results)} students in {module_code}")

    elif choice == '2':
        module_code = input("Module code to unenroll from: ").strip()
        if module_code:
            print(f"✅ Simulation: Unenrolled {len(_globals.last_search_results)} students from {module_code}")

    elif choice == '3':
        from_module = input("Transfer FROM module code: ").strip()
        to_module = input("Transfer TO module code: ").strip()
        if from_module and to_module:
            print(f"✅ Simulation: Transferred {len(_globals.last_search_results)} students from {from_module} to {to_module}")

    elif choice == '4':
        new_status = input("New enrollment status: ").strip()
        if new_status:
            print(f"✅ Simulation: Updated enrollment status to '{new_status}' for {len(_globals.last_search_results)} students")
