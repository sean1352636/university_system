"""CLI for the academic advising portal."""

from education_system.university_system.infrastructure.database.db import get_connection
from education_system.university_system.modules.domain.advising.services import advising_service


def main():
    """Run the advising CLI menu loop."""
    advising_service.init_db()
    # Seed sample advisors if table is empty
    if advising_service.get_advisor_count() == 0:
        advising_service.seed_sample_advisors()

    while True:
        print("\n===== Academic Advising Portal =====")
        print("1. List Advisors")
        print("2. Schedule Appointment")
        print("3. View My Appointments")
        print("4. Cancel Appointment")
        print("5. View Degree Plan")
        print("6. Create Degree Plan")
        print("7. Check Completed Credits")
        print("0. Back / Exit")

        choice = input("\nSelect an option: ").strip()

        if choice == "1":
            list_advisors()
        elif choice == "2":
            schedule_appointment()
        elif choice == "3":
            view_appointments()
        elif choice == "4":
            cancel_appointment()
        elif choice == "5":
            view_degree_plan()
        elif choice == "6":
            create_degree_plan()
        elif choice == "7":
            check_completed_credits()
        elif choice == "0":
            print("Returning to main menu.")
            break
        else:
            print("Invalid option. Please try again.")


def list_advisors():
    """Display all advisors."""
    try:
        advisors = advising_service.get_all_advisors()
        if not advisors:
            print("No advisors found.")
            return
        print(f"\n{'ID':<10} {'Name':<25} {'Department':<20} {'Office':<10} {'Specialization':<25}")
        print("-" * 90)
        for a in advisors:
            print(
                f"{a['advisor_id']:<10} {a['name']:<25} {a['department']:<20} "
                f"{a['office']:<10} {a['specialization']:<25}"
            )
    except Exception as e:
        print(f"Error: {e}")


def schedule_appointment():
    """Schedule a new advising appointment."""
    try:
        student_id = input("Student ID: ").strip()
        advisor_id = input("Advisor ID: ").strip()
        appointment_date = input("Date (YYYY-MM-DD): ").strip()
        appointment_time = input("Time (HH:MM): ").strip()
        duration = input("Duration in minutes [30]: ").strip() or "30"
        appointment_type = input("Type (general/academic/career) [general]: ").strip() or "general"
        topic = input("Topic: ").strip()
        notes = input("Notes: ").strip()

        advising_service.schedule_appointment(
            student_id=student_id,
            advisor_id=advisor_id,
            appointment_date=appointment_date,
            appointment_time=appointment_time,
            duration_minutes=int(duration),
            appointment_type=appointment_type,
            topic=topic,
            notes=notes,
        )
        print("Appointment scheduled successfully.")
    except Exception as e:
        print(f"Error: {e}")


def view_appointments():
    """View appointments for a student."""
    try:
        student_id = input("Student ID: ").strip()
        status_filter = input("Filter by status (All/scheduled/completed/cancelled) [All]: ").strip() or "All"

        appointments = advising_service.get_appointments(student_id, status_filter)
        if not appointments:
            print("No appointments found.")
            return
        print(
            f"\n{'ID':<6} {'Advisor':<10} {'Date':<12} {'Time':<8} "
            f"{'Type':<12} {'Topic':<20} {'Status':<12}"
        )
        print("-" * 80)
        for a in appointments:
            print(
                f"{a['appointment_id']:<6} {a['advisor_id']:<10} {a['appointment_date']:<12} "
                f"{a['appointment_time']:<8} {a['appointment_type']:<12} "
                f"{a['topic']:<20} {a['status']:<12}"
            )
    except Exception as e:
        print(f"Error: {e}")


def cancel_appointment():
    """Cancel an existing appointment."""
    try:
        appointment_id = input("Appointment ID to cancel: ").strip()
        if advising_service.cancel_appointment(int(appointment_id)):
            print("Appointment cancelled successfully.")
        else:
            print("Appointment not found or already cancelled.")
    except Exception as e:
        print(f"Error: {e}")


def view_degree_plan():
    """View the active degree plan for a student."""
    try:
        student_id = input("Student ID: ").strip()
        plan = advising_service.get_active_degree_plan(student_id)
        if not plan:
            print("No active degree plan found for this student.")
            return
        print(f"\nPlan: {plan['plan_name']}")
        print(f"Target Graduation: {plan['target_graduation'] or 'Not set'}")
        print(f"Credits Required:  {plan['total_credits_required']}")
        print(f"Credits Completed: {plan['credits_completed']}")
        print(f"Status:            {plan['status']}")
        print(f"Notes:             {plan['notes']}")
    except Exception as e:
        print(f"Error: {e}")


def create_degree_plan():
    """Create a new degree plan for a student."""
    try:
        student_id = input("Student ID: ").strip()
        plan_name = input("Plan name: ").strip()
        target_graduation = input("Target graduation date (YYYY-MM-DD) [leave blank]: ").strip() or None
        total_credits = input("Total credits required [120]: ").strip() or "120"
        notes = input("Notes: ").strip()

        advising_service.create_degree_plan(
            student_id=student_id,
            plan_name=plan_name,
            target_graduation=target_graduation,
            total_credits_required=int(total_credits),
            notes=notes,
        )
        print("Degree plan created successfully.")
    except Exception as e:
        print(f"Error: {e}")


def check_completed_credits():
    """Check how many credits a student has completed."""
    try:
        student_id = input("Student ID: ").strip()
        credits = advising_service.get_completed_credits(student_id)
        print(f"Completed credits for {student_id}: {credits}")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
