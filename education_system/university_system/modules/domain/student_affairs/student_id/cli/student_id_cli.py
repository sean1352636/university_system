"""CLI for the digital student ID card system."""

from education_system.university_system.infrastructure.database.db import get_connection
from education_system.university_system.modules.domain.student_affairs.student_id.services import student_id_service


def main():
    """Run the student ID CLI menu loop."""
    student_id_service.init_db()

    while True:
        print("\n===== Student ID Card System =====")
        print("1. View My ID Card")
        print("2. View Student Details")
        print("3. Report Lost Card")
        print("0. Back / Exit")

        choice = input("\nSelect an option: ").strip()

        if choice == "1":
            view_card()
        elif choice == "2":
            view_student_details()
        elif choice == "3":
            report_lost_card()
        elif choice == "0":
            print("Returning to main menu.")
            break
        else:
            print("Invalid option. Please try again.")


def view_card():
    """View or auto-generate the student ID card."""
    try:
        student_id = input("Student ID: ").strip()
        card = student_id_service.get_or_create_card(student_id)
        print(f"\nCard Number:  {card['card_number']}")
        print(f"Issue Date:   {card['issue_date']}")
        print(f"Expiry Date:  {card['expiry_date']}")
        print(f"Status:       {card['status']}")
    except Exception as e:
        print(f"Error: {e}")


def view_student_details():
    """View student demographic information."""
    try:
        student_id = input("Student ID: ").strip()
        details = student_id_service.get_student_details(student_id)
        print(f"\nName:       {details['name']}")
        print(f"Email:      {details['email']}")
        print(f"Course:     {details['course']}")
        print(f"Department: {details['department']}")
        print(f"Year:       {details['year']}")
    except Exception as e:
        print(f"Error: {e}")


def report_lost_card():
    """Report a lost card and receive a replacement."""
    try:
        student_id = input("Student ID: ").strip()
        confirm = input("Are you sure you want to report your card as lost? (y/n): ").strip().lower()
        if confirm != "y":
            print("Operation cancelled.")
            return
        new_card_number = student_id_service.report_lost_card(student_id)
        print(f"Card reported as lost. New card number: {new_card_number}")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
