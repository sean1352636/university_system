"""Component extracted from the legacy menu router."""
from __future__ import annotations
from ..bootstrap.integrations import display_export_menu

def display_data_document_management_menu(auth):
    """Consolidated data and document management menu"""
    if not auth or not auth.current_user:
        print("You must be logged in to access data management.")
        return

    while True:
        print("\n" + "="*60)
        print("        DATA & DOCUMENT MANAGEMENT SYSTEM")
        print("="*60)
        print(f"Logged in as: {auth.current_user['username']} ({auth.current_user['role']})")

        print("\n📄 Document Management:")
        print("1. Document Management System")

        print("\n💾 Data Operations:")
        print("2. Export Options")
        print("3. Data Backup and Restore")

        print("\n↩️ Navigation:")
        print("4. Return to Main Menu")
        print("="*60)

        choice = input("\nEnter your choice (1-4): ").strip()

        if choice == '1':
            # Document Management
            from education_system.systems.university.infrastructure.utils.document_manager import display_document_management_menu
            display_document_management_menu()
        elif choice == '2':
            # Export Options
            display_export_menu()
        elif choice == '3':
            # Data Backup and Restore
            from education_system.systems.university.infrastructure.database.data_backup import display_backup_menu
            display_backup_menu()
        elif choice == '4':
            # Return to main menu
            break
        else:
            print("Invalid choice. Please try again.")
