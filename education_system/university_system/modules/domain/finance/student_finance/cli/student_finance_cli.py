"""
Student Finance CLI Interface

Command-line interface for student finance fee record management
including creating, listing, viewing, updating, and deleting fee records.
"""

from education_system.university_system.modules.domain.finance.student_finance.services.student_finance_service import (
    StudentFinanceService,
)


class StudentFinanceCLI:
    """CLI interface for Student Finance operations."""

    def __init__(self):
        """Initialize the Student Finance CLI."""
        self.service = StudentFinanceService()

    def display_menu(self):
        """Display the main student finance menu and handle user input."""
        while True:
            print("\n" + "=" * 60)
            print(" " * 16 + "STUDENT FINANCE SYSTEM")
            print("=" * 60)

            print("\n[Fee Records]")
            print("  1. Create Fee Record")
            print("  2. List All Fee Records")
            print("  3. List Fee Records with Filters")
            print("  4. View Fee Record by ID")
            print("  5. Update Fee Record")
            print("  6. Delete Fee Record")

            print("\n  0. Back to Main Menu")
            print("=" * 60)

            choice = input("\nEnter your choice: ").strip()

            try:
                if choice == "0":
                    break
                elif choice == "1":
                    self._create_record()
                elif choice == "2":
                    self._list_all()
                elif choice == "3":
                    self._list_filtered()
                elif choice == "4":
                    self._view_record()
                elif choice == "5":
                    self._update_record()
                elif choice == "6":
                    self._delete_record()
                else:
                    print("Invalid choice. Please try again.")
            except Exception as e:
                print(f"\nError: {e}")

    def _create_record(self):
        """Create a new fee record."""
        print("\nEnter fee record details (press Enter to skip optional fields):")
        kwargs = {}

        student_id = input("  Student ID: ").strip()
        if student_id:
            kwargs["student_id"] = student_id

        fee_type = input("  Fee type (e.g. tuition, accommodation, library): ").strip()
        if fee_type:
            kwargs["fee_type"] = fee_type

        amount = input("  Amount (£): ").strip()
        if amount:
            kwargs["amount"] = float(amount)

        due_date = input("  Due date (YYYY-MM-DD): ").strip()
        if due_date:
            kwargs["due_date"] = due_date

        status = input("  Status (e.g. pending, paid, overdue): ").strip()
        if status:
            kwargs["status"] = status

        academic_year = input("  Academic year (e.g. 2025-2026): ").strip()
        if academic_year:
            kwargs["academic_year"] = academic_year

        description = input("  Description (optional): ").strip()
        if description:
            kwargs["description"] = description

        if not kwargs:
            print("No data provided. Record not created.")
            return

        record_id = self.service.create(**kwargs)
        print(f"\nFee record created successfully (ID: {record_id}).")

    def _list_all(self):
        """List all fee records with pagination."""
        limit_input = input("Records per page (default 100): ").strip()
        limit = int(limit_input) if limit_input else 100
        offset_input = input("Offset / skip (default 0): ").strip()
        offset = int(offset_input) if offset_input else 0

        records = self.service.list_all(limit=limit, offset=offset)
        if not records:
            print("\nNo fee records found.")
            return
        self._print_records(records)

    def _list_filtered(self):
        """List fee records with optional filters."""
        print("\nEnter filter values (press Enter to skip):")
        filters = {}

        student_id = input("  Student ID: ").strip()
        if student_id:
            filters["student_id"] = student_id

        fee_type = input("  Fee type: ").strip()
        if fee_type:
            filters["fee_type"] = fee_type

        status = input("  Status: ").strip()
        if status:
            filters["status"] = status

        academic_year = input("  Academic year: ").strip()
        if academic_year:
            filters["academic_year"] = academic_year

        records = self.service.list_all(**filters)
        if not records:
            print("\nNo fee records found matching filters.")
            return
        self._print_records(records)

    def _view_record(self):
        """View a single fee record by ID."""
        record_id = int(input("Fee record ID: ").strip())
        record = self.service.get(record_id)
        if not record:
            print("Fee record not found.")
            return
        print(f"\n--- Fee Record #{record_id} ---")
        for key, value in record.items():
            print(f"  {key}: {value}")

    def _print_records(self, records):
        """Print a list of fee records."""
        if not records:
            return
        # Determine columns from first record
        columns = list(records[0].keys())
        # Print header
        header = "  ".join(f"{col:<15}" for col in columns[:6])
        print(f"\n{header}")
        print("-" * min(len(header), 90))
        for r in records:
            row = "  ".join(f"{str(r.get(col, '')):<15}" for col in columns[:6])
            print(row)
        print(f"\n{len(records)} record(s) displayed.")

    def _update_record(self):
        """Update an existing fee record."""
        record_id = int(input("Fee record ID to update: ").strip())
        record = self.service.get(record_id)
        if not record:
            print("Fee record not found.")
            return
        print(f"Current record: {record}")

        print("\nEnter new values (press Enter to keep current):")
        updates = {}

        amount = input(f"  Amount (current: {record.get('amount')}): ").strip()
        if amount:
            updates["amount"] = float(amount)

        status = input(f"  Status (current: {record.get('status')}): ").strip()
        if status:
            updates["status"] = status

        due_date = input(f"  Due date (current: {record.get('due_date')}): ").strip()
        if due_date:
            updates["due_date"] = due_date

        description = input(f"  Description (current: {record.get('description')}): ").strip()
        if description:
            updates["description"] = description

        if not updates:
            print("No changes made.")
            return

        if self.service.update(record_id, **updates):
            print("Fee record updated successfully.")
        else:
            print("Failed to update fee record.")

    def _delete_record(self):
        """Delete a fee record."""
        record_id = int(input("Fee record ID to delete: ").strip())
        record = self.service.get(record_id)
        if not record:
            print("Fee record not found.")
            return
        print(f"Record to delete: {record}")
        confirm = input("Are you sure? (yes/no): ").strip().lower()
        if confirm != "yes":
            print("Deletion cancelled.")
            return

        if self.service.delete(record_id):
            print("Fee record deleted successfully.")
        else:
            print("Failed to delete fee record.")


def main():
    """Entry point for the Student Finance CLI."""
    cli = StudentFinanceCLI()
    cli.display_menu()


if __name__ == "__main__":
    main()
