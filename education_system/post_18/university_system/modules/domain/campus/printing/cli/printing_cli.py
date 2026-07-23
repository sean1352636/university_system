"""CLI for the print-quota system."""

from education_system.post_18.university_system.infrastructure.database.db import get_connection
from education_system.post_18.university_system.modules.domain.campus.printing.services import printing_service


def main():
    """Run the printing CLI menu loop."""
    printing_service.init_db()

    while True:
        print("\n===== Print Quota System =====")
        print("1. View Print Quota")
        print("2. Submit Print Job")
        print("3. View Print History")
        print("4. View Credit Transactions")
        print("5. Purchase Print Credits")
        print("6. Calculate Print Cost")
        print("0. Back / Exit")

        choice = input("\nSelect an option: ").strip()

        if choice == "1":
            view_quota()
        elif choice == "2":
            submit_print_job()
        elif choice == "3":
            view_print_history()
        elif choice == "4":
            view_transactions()
        elif choice == "5":
            purchase_credits()
        elif choice == "6":
            calculate_cost()
        elif choice == "0":
            print("Returning to main menu.")
            break
        else:
            print("Invalid option. Please try again.")


def view_quota():
    """Display the print quota for a student."""
    try:
        student_id = input("Student ID: ").strip()
        quota = printing_service.get_quota(student_id)
        remaining = quota["total_pages"] - quota["used_pages"]
        print(f"\nTotal pages:       {quota['total_pages']}")
        print(f"Used pages:        {quota['used_pages']}")
        print(f"Remaining pages:   {remaining}")
        print(f"Color pages used:  {quota['color_pages_used']}")
        print(f"Last reset:        {quota['last_reset']}")
    except Exception as e:
        print(f"Error: {e}")


def submit_print_job():
    """Submit a new print job."""
    try:
        student_id = input("Student ID: ").strip()
        file_name = input("File name: ").strip()
        pages = input("Number of pages: ").strip()
        copies = input("Number of copies [1]: ").strip() or "1"
        color_input = input("Color printing? (y/n) [n]: ").strip().lower()
        color = color_input == "y"
        double_input = input("Double-sided? (y/n) [y]: ").strip().lower()
        double_sided = double_input != "n"
        paper_size = input("Paper size [A4]: ").strip() or "A4"
        printer_location = input("Printer location: ").strip()

        cost = printing_service.submit_print_job(
            student_id=student_id,
            file_name=file_name,
            pages=int(pages),
            copies=int(copies),
            color=color,
            double_sided=double_sided,
            paper_size=paper_size,
            printer_location=printer_location,
        )
        print(f"Print job submitted successfully. Credits deducted: {cost}")
    except Exception as e:
        print(f"Error: {e}")


def view_print_history():
    """View print job history for a student."""
    try:
        student_id = input("Student ID: ").strip()
        jobs = printing_service.get_print_history(student_id)
        if not jobs:
            print("No print jobs found.")
            return
        print(
            f"\n{'ID':<6} {'File':<25} {'Pages':<7} {'Copies':<8} "
            f"{'Color':<7} {'Cost':<6} {'Status':<10} {'Submitted':<20}"
        )
        print("-" * 89)
        for j in jobs:
            color_str = "Yes" if j["color"] else "No"
            print(
                f"{j['job_id']:<6} {j['file_name']:<25} {j['pages']:<7} "
                f"{j['copies']:<8} {color_str:<7} {j['cost_credits']:<6} "
                f"{j['status']:<10} {j['submitted_at']:<20}"
            )
    except Exception as e:
        print(f"Error: {e}")


def view_transactions():
    """View credit transactions for a student."""
    try:
        student_id = input("Student ID: ").strip()
        transactions = printing_service.get_transactions(student_id)
        if not transactions:
            print("No transactions found.")
            return
        print(f"\n{'ID':<6} {'Type':<10} {'Amount':<8} {'Description':<40} {'Date':<20}")
        print("-" * 84)
        for t in transactions:
            print(
                f"{t['transaction_id']:<6} {t['transaction_type']:<10} "
                f"{t['amount']:<8} {t['description']:<40} {t['created_at']:<20}"
            )
    except Exception as e:
        print(f"Error: {e}")


def purchase_credits():
    """Purchase additional print credits."""
    try:
        student_id = input("Student ID: ").strip()
        pages = input("Number of page credits to purchase: ").strip()
        price = input("Price (e.g. 4.50): ").strip()

        printing_service.purchase_credits(student_id, int(pages), price)
        print(f"Successfully purchased {pages} print credits.")
    except Exception as e:
        print(f"Error: {e}")


def calculate_cost():
    """Calculate the cost of a hypothetical print job."""
    try:
        pages = input("Number of pages: ").strip()
        copies = input("Number of copies: ").strip()
        color_input = input("Color printing? (y/n) [n]: ").strip().lower()
        color = color_input == "y"
        double_input = input("Double-sided? (y/n) [y]: ").strip().lower()
        double_sided = double_input != "n"

        cost = printing_service.calculate_cost(int(pages), int(copies), color, double_sided)
        print(f"Estimated cost: {cost} credits")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
