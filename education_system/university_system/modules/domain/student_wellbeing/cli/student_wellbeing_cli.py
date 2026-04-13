"""
Student Wellbeing CLI Interface

Command-line interface for student wellbeing referral management
including creating, listing, viewing, updating, and deleting referrals.
"""

from education_system.university_system.modules.domain.student_wellbeing.services.wellbeing_service import (
    WellbeingService,
)


class StudentWellbeingCLI:
    """CLI interface for Student Wellbeing operations."""

    def __init__(self):
        """Initialize the Student Wellbeing CLI."""
        self.service = WellbeingService()

    def display_menu(self):
        """Display the main student wellbeing menu and handle user input."""
        while True:
            print("\n" + "=" * 60)
            print(" " * 14 + "STUDENT WELLBEING SYSTEM")
            print("=" * 60)

            print("\n[Wellbeing Referrals]")
            print("  1. Create Wellbeing Referral")
            print("  2. List All Referrals")
            print("  3. List Referrals with Filters")
            print("  4. View Referral by ID")
            print("  5. Update Referral")
            print("  6. Delete Referral")

            print("\n  0. Back to Main Menu")
            print("=" * 60)

            choice = input("\nEnter your choice: ").strip()

            try:
                if choice == "0":
                    break
                elif choice == "1":
                    self._create_referral()
                elif choice == "2":
                    self._list_all()
                elif choice == "3":
                    self._list_filtered()
                elif choice == "4":
                    self._view_referral()
                elif choice == "5":
                    self._update_referral()
                elif choice == "6":
                    self._delete_referral()
                else:
                    print("Invalid choice. Please try again.")
            except Exception as e:
                print(f"\nError: {e}")

    def _create_referral(self):
        """Create a new wellbeing referral."""
        print("\nEnter referral details (press Enter to skip optional fields):")
        kwargs = {}

        student_id = input("  Student ID: ").strip()
        if student_id:
            kwargs["student_id"] = student_id

        student_name = input("  Student name: ").strip()
        if student_name:
            kwargs["student_name"] = student_name

        referral_type = input("  Referral type (e.g. mental_health, academic, financial, personal): ").strip()
        if referral_type:
            kwargs["referral_type"] = referral_type

        urgency = input("  Urgency (low/medium/high/critical): ").strip()
        if urgency:
            kwargs["urgency"] = urgency

        referred_by = input("  Referred by (staff name/ID): ").strip()
        if referred_by:
            kwargs["referred_by"] = referred_by

        description = input("  Description of concern: ").strip()
        if description:
            kwargs["description"] = description

        assigned_to = input("  Assigned to (counsellor name/ID, optional): ").strip()
        if assigned_to:
            kwargs["assigned_to"] = assigned_to

        status = input("  Status (e.g. open, in_progress, resolved, closed; default: open): ").strip()
        if status:
            kwargs["status"] = status

        if not kwargs:
            print("No data provided. Referral not created.")
            return

        record_id = self.service.create(**kwargs)
        print(f"\nWellbeing referral created successfully (ID: {record_id}).")

    def _list_all(self):
        """List all wellbeing referrals with pagination."""
        limit_input = input("Records per page (default 100): ").strip()
        limit = int(limit_input) if limit_input else 100
        offset_input = input("Offset / skip (default 0): ").strip()
        offset = int(offset_input) if offset_input else 0

        records = self.service.list_all(limit=limit, offset=offset)
        if not records:
            print("\nNo wellbeing referrals found.")
            return
        self._print_records(records)

    def _list_filtered(self):
        """List referrals with optional filters."""
        print("\nEnter filter values (press Enter to skip):")
        filters = {}

        student_id = input("  Student ID: ").strip()
        if student_id:
            filters["student_id"] = student_id

        referral_type = input("  Referral type: ").strip()
        if referral_type:
            filters["referral_type"] = referral_type

        urgency = input("  Urgency: ").strip()
        if urgency:
            filters["urgency"] = urgency

        status = input("  Status: ").strip()
        if status:
            filters["status"] = status

        assigned_to = input("  Assigned to: ").strip()
        if assigned_to:
            filters["assigned_to"] = assigned_to

        records = self.service.list_all(**filters)
        if not records:
            print("\nNo referrals found matching filters.")
            return
        self._print_records(records)

    def _view_referral(self):
        """View a single wellbeing referral by ID."""
        record_id = int(input("Referral ID: ").strip())
        record = self.service.get(record_id)
        if not record:
            print("Referral not found.")
            return
        print(f"\n--- Wellbeing Referral #{record_id} ---")
        for key, value in record.items():
            print(f"  {key}: {value}")

    def _print_records(self, records):
        """Print a list of referral records."""
        if not records:
            return
        columns = list(records[0].keys())
        header = "  ".join(f"{col:<15}" for col in columns[:6])
        print(f"\n{header}")
        print("-" * min(len(header), 90))
        for r in records:
            row = "  ".join(f"{str(r.get(col, '')):<15}" for col in columns[:6])
            print(row)
        print(f"\n{len(records)} record(s) displayed.")

    def _update_referral(self):
        """Update an existing wellbeing referral."""
        record_id = int(input("Referral ID to update: ").strip())
        record = self.service.get(record_id)
        if not record:
            print("Referral not found.")
            return
        print(f"Current record: {record}")

        print("\nEnter new values (press Enter to keep current):")
        updates = {}

        status = input(f"  Status (current: {record.get('status')}): ").strip()
        if status:
            updates["status"] = status

        urgency = input(f"  Urgency (current: {record.get('urgency')}): ").strip()
        if urgency:
            updates["urgency"] = urgency

        assigned_to = input(f"  Assigned to (current: {record.get('assigned_to')}): ").strip()
        if assigned_to:
            updates["assigned_to"] = assigned_to

        description = input(f"  Description (current: {record.get('description')}): ").strip()
        if description:
            updates["description"] = description

        notes = input("  Additional notes: ").strip()
        if notes:
            updates["notes"] = notes

        if not updates:
            print("No changes made.")
            return

        if self.service.update(record_id, **updates):
            print("Referral updated successfully.")
        else:
            print("Failed to update referral.")

    def _delete_referral(self):
        """Delete a wellbeing referral."""
        record_id = int(input("Referral ID to delete: ").strip())
        record = self.service.get(record_id)
        if not record:
            print("Referral not found.")
            return
        print(f"Record to delete: {record}")
        confirm = input("Are you sure? (yes/no): ").strip().lower()
        if confirm != "yes":
            print("Deletion cancelled.")
            return

        if self.service.delete(record_id):
            print("Referral deleted successfully.")
        else:
            print("Failed to delete referral.")


def main():
    """Entry point for the Student Wellbeing CLI."""
    cli = StudentWellbeingCLI()
    cli.display_menu()


if __name__ == "__main__":
    main()
